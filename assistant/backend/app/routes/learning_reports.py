from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, load_only
from app.core.database import get_db
from app.core.security import current_user
from app.api import course_access, user_dict
from app.models import User, Enrollment, LearningReport

router = APIRouter(prefix='/api')

METADATA = load_only(*(getattr(LearningReport,name) for name in (
    'id','course_id','student_id','requested_by','active_key','status','phase','progress',
    'created_at','snapshot_at','completed_at','counts','models','error')))


def iso(value):
    return value.isoformat() + 'Z' if value else None


def report_dict(job, detail=False):
    data = {'id': job.id, 'course_id': job.course_id, 'student_id': job.student_id,
            'status': job.status, 'phase': job.phase, 'progress': job.progress,
            'created_at': iso(job.created_at), 'snapshot_at': iso(job.snapshot_at),
            'completed_at': iso(job.completed_at), 'counts': job.counts,
            'models': job.models, 'error': job.error}
    if detail:
        data['content'] = job.content if job.status == 'completed' else ''
        data['evidence'] = [{'id': e['id'], 'kind': e['kind'], 'at': e['at'].replace(' ', 'T') + 'Z',
                             'topic_id': e.get('topic_id')} for e in job.snapshot.get('evidence', [])]
        data['topics'] = job.snapshot.get('topics', [])
    return data


def student_access(db, user, course_id, student_id):
    course_access(db, user, course_id, teacher_only=True)
    if not db.scalar(select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.student_id == student_id)):
        raise HTTPException(404, 'دانشجو عضو این درس نیست.')


def enqueue(db, course_id, student_id, teacher_id):
    key = f'{course_id}:{student_id}'
    existing = db.scalar(select(LearningReport).options(METADATA).where(LearningReport.active_key == key))
    if existing:
        return existing
    job = LearningReport(course_id=course_id, student_id=student_id, requested_by=teacher_id, active_key=key)
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        return db.scalar(select(LearningReport).options(METADATA).where(LearningReport.active_key == key)) or db.scalar(
            select(LearningReport).options(METADATA).where(LearningReport.course_id == course_id,
                LearningReport.student_id == student_id).order_by(LearningReport.id.desc()).limit(1))
    return job


@router.post('/courses/{course_id}/students/{student_id}/learning-reports', status_code=202)
def create_report(course_id: int, student_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    student_access(db, user, course_id, student_id)
    job = enqueue(db, course_id, student_id, user.id)
    db.commit()
    return report_dict(job)


@router.post('/courses/{course_id}/learning-reports/batch', status_code=202)
def create_class_reports(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    student_ids = db.scalars(select(Enrollment.student_id).where(Enrollment.course_id == course_id).order_by(Enrollment.student_id)).all()
    jobs = [enqueue(db, course_id, student_id, user.id) for student_id in student_ids]
    db.commit()
    return {'reports': [report_dict(job) for job in jobs]}


@router.get('/courses/{course_id}/learning-reports')
def class_reports(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    users = db.scalars(select(User).join(Enrollment, Enrollment.student_id == User.id)
                      .where(Enrollment.course_id == course_id).order_by(User.id)).all()
    def latest_for(condition):
        newest = select(func.max(LearningReport.id)).where(LearningReport.course_id == course_id, condition).group_by(LearningReport.student_id)
        return {job.student_id: report_dict(job) for job in db.scalars(select(LearningReport).options(METADATA).where(LearningReport.id.in_(newest)))}
    latest = latest_for(True)
    completed = latest_for(LearningReport.status == 'completed')
    active = latest_for(LearningReport.status.in_(['queued', 'running']))
    return {'students': [{'student': user_dict(u), 'latest': latest.get(u.id), 'completed': completed.get(u.id),
                          'active': active.get(u.id)} for u in users]}


@router.get('/courses/{course_id}/students/{student_id}/learning-reports')
def history(course_id: int, student_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    student_access(db, user, course_id, student_id)
    jobs = db.scalars(select(LearningReport).options(METADATA).where(LearningReport.course_id == course_id,
        LearningReport.student_id == student_id).order_by(LearningReport.id.desc()).limit(30)).all()
    return {'reports': [report_dict(job) for job in jobs]}


def owned_report(db, user, report_id):
    job = db.get(LearningReport, report_id)
    if not job:
        raise HTTPException(404, 'گزارش پیدا نشد.')
    student_access(db, user, job.course_id, job.student_id)
    return job


@router.get('/learning-reports/{report_id}')
def read_report(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = owned_report(db, user, report_id)
    result = report_dict(job, True)
    result['student'] = user_dict(db.get(User, job.student_id))
    return result


@router.post('/learning-reports/{report_id}/retry', status_code=202)
def retry_report(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = owned_report(db, user, report_id)
    if job.status != 'failed':
        raise HTTPException(409, 'فقط گزارش ناموفق قابل ادامه است.')
    key = f'{job.course_id}:{job.student_id}'
    active = db.scalar(select(LearningReport).options(METADATA).where(LearningReport.active_key == key))
    if active:
        return report_dict(active)
    try:
        job.checkpoint = {**job.checkpoint, '__worker_retry':0}
        job.lease_until = None
        job.active_key, job.status, job.error, job.phase = key, 'queued', '', 'در صف ادامهٔ گزارش'
        db.commit()
    except IntegrityError:
        db.rollback()
        job = db.scalar(select(LearningReport).options(METADATA).where(LearningReport.active_key == key))
    return report_dict(job)


@router.get('/learning-reports/{report_id}/export')
def export_report(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = owned_report(db, user, report_id)
    if job.status != 'completed':
        raise HTTPException(409, 'گزارش هنوز آماده نیست.')
    student = db.get(User, job.student_id)
    text = f'# گزارش یادگیری {student.first_name} {student.last_name}\n\n'
    text += f'تاریخ ثبت داده‌ها: {iso(job.snapshot_at)}\n\n' + job.content
    text += '\n\n## فهرست شواهد بررسی‌شده\n\n' + '\n'.join(
        f'- [{e["id"]}] {e["kind"]} — {e["at"]}' for e in job.snapshot.get('evidence', []))
    return Response(text, media_type='text/markdown; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="student-{job.student_id}-report-{job.id}.md"'})
