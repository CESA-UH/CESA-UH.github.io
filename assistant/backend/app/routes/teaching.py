import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user
from app.services.permissions import can_edit_course
from app.api import course_access, topic_access, role_required, user_dict
from app.models import (User, Topic, Enrollment, SelfReport, ReportForm, ReportFormEntry,
                        Quiz, QuizQuestion, QuizAttempt, QuizAnswer)
from app.schemas import (TopicInput, TopicBatchInput, ReportFormInput, FormReportInput,
                         QuizInput, QuizAnswerInput, QuizGradeInput)
from app.services.analytics import report_dict
from app.services import quiz_grading
from app.services.quiz_grading import questions, finalize, expire

router = APIRouter(prefix='/api')


def now():
    return quiz_grading.now()


def iso(value):
    return value.isoformat() + 'Z' if value else None


def utc(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, TypeError):
        raise HTTPException(422, 'زمان باید تاریخ معتبر و دارای منطقهٔ زمانی باشد.')


@router.post('/courses/{course_id}/topics/bulk', status_code=201)
def bulk_topics(course_id: int, data: TopicBatchInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    rows = [Topic(course_id=course_id, **item.model_dump()) for item in data.topics]
    db.add_all(rows)
    db.commit()
    return [{'id': t.id, 'name': t.name, 'description': t.description} for t in rows]


@router.put('/courses/{course_id}/topics/{topic_id}')
def edit_topic(course_id: int, topic_id: int, data: TopicInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    topic = topic_access(db, course_id, topic_id)
    topic.name, topic.description = data.name, data.description
    db.commit()
    return {'id': topic.id, 'name': topic.name, 'description': topic.description}


def form_dict(form):
    return {'id': form.id, 'title': form.title, 'instructions': form.instructions,
            'topic_ids': form.topic_ids, 'fields': form.fields, 'published': form.published}


def owned_form(db, user, form_id):
    form = db.get(ReportForm, form_id)
    if not form:
        raise HTTPException(404, 'فرم پیدا نشد.')
    course_access(db, user, form.course_id, teacher_only=True)
    return form


@router.get('/courses/{course_id}/report-forms')
def list_forms(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = course_access(db, user, course_id)
    stmt = select(ReportForm).where(ReportForm.course_id == course_id).order_by(ReportForm.id.desc())
    if not can_edit_course(db, user, course):
        stmt = stmt.where(ReportForm.published.is_(True))
    return [form_dict(f) for f in db.scalars(stmt)]


@router.post('/courses/{course_id}/report-forms', status_code=201)
def create_form(course_id: int, data: ReportFormInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    for topic_id in set(data.topic_ids):
        topic_access(db, course_id, topic_id)
    for field in data.fields:
        if field.kind == 'choice' and len(field.options) < 2:
            raise HTTPException(422, 'پرسش انتخابی حداقل دو گزینه نیاز دارد.')
        if field.kind != 'choice' and field.options:
            raise HTTPException(422, 'گزینه فقط برای پرسش انتخابی مجاز است.')
    form = ReportForm(course_id=course_id, title=data.title, instructions=data.instructions,
                      topic_ids=list(dict.fromkeys(data.topic_ids)),
                      fields=[{'id': secrets.token_hex(6), **f.model_dump()} for f in data.fields])
    db.add(form)
    db.commit()
    return form_dict(form)


@router.post('/report-forms/{form_id}/publish')
def publish_form(form_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    form = owned_form(db, user, form_id)
    form.published = True
    db.commit()
    return form_dict(form)


@router.post('/report-forms/{form_id}/responses', status_code=201)
def respond_form(form_id: int, data: FormReportInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, 'student')
    form = db.get(ReportForm, form_id)
    if not form:
        raise HTTPException(404, 'فرم پیدا نشد.')
    course_access(db, user, form.course_id)
    if not form.published:
        raise HTTPException(409, 'فرم منتشر نشده است.')
    if data.topic_id not in form.topic_ids:
        raise HTTPException(422, 'مبحث در این فرم وجود ندارد.')
    topic = topic_access(db, form.course_id, data.topic_id)
    fields = {field['id']: field for field in form.fields}
    if set(data.answers) - set(fields):
        raise HTTPException(422, 'پرسش ناشناخته در پاسخ فرم.')
    for key, field in fields.items():
        value = data.answers.get(key)
        if value is None or value == '':
            if field['required']:
                raise HTTPException(422, f"پاسخ «{field['label']}» لازم است.")
            continue
        if field['kind'] == 'scale' and (type(value) is not int or not 1 <= value <= 5):
            raise HTTPException(422, 'امتیاز پرسش باید بین ۱ و ۵ باشد.')
        if field['kind'] == 'choice' and value not in field['options']:
            raise HTTPException(422, 'گزینهٔ انتخاب‌شده معتبر نیست.')
        if field['kind'] == 'text' and (not isinstance(value, str) or len(value) > 2000):
            raise HTTPException(422, 'پاسخ متنی حداکثر ۲۰۰۰ نویسه است.')
    report = SelfReport(student_id=user.id, **data.model_dump(exclude={'answers'}))
    db.add(report)
    db.flush()
    db.add(ReportFormEntry(report_id=report.id, form_id=form.id, answers=data.answers))
    db.commit()
    return report_dict(report, topic)


@router.get('/report-forms/{form_id}/responses')
def form_responses(form_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    form = owned_form(db, user, form_id)
    rows = db.execute(select(ReportFormEntry, SelfReport, Topic, User)
        .join(SelfReport, SelfReport.id == ReportFormEntry.report_id)
        .join(Topic, Topic.id == SelfReport.topic_id).join(User, User.id == SelfReport.student_id)
        .where(ReportFormEntry.form_id == form.id).order_by(SelfReport.id.desc())).all()
    return {'form': form_dict(form), 'responses': [
        {'student': user_dict(u), 'report': report_dict(r, t), 'answers': entry.answers} for entry, r, t, u in rows]}


def quiz_access(db, user, quiz_id, teacher=False):
    quiz = db.get(Quiz, quiz_id)
    if not quiz:
        raise HTTPException(404, 'کوییز پیدا نشد.')
    course_access(db, user, quiz.course_id, teacher_only=teacher)
    return quiz


def question_dict(question, teacher=False):
    result = {'id': question.id, 'topic_id': question.topic_id, 'text': question.text,
              'kind': question.kind, 'options': question.options, 'points': question.points}
    if teacher:
        result['correct_choice'] = question.correct_choice
    return result


def quiz_dict(db, quiz, teacher=False):
    result = {'id': quiz.id, 'title': quiz.title, 'instructions': quiz.instructions,
              'starts_at': iso(quiz.starts_at), 'ends_at': iso(quiz.ends_at),
              'duration_minutes': quiz.duration_minutes, 'published': quiz.published,
              'question_count': db.scalar(select(func.count()).select_from(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)),
              'server_now': iso(now())}
    if teacher:
        result['questions'] = [question_dict(q, True) for q in questions(db, quiz.id)]
    return result


@router.post('/courses/{course_id}/quizzes', status_code=201)
def create_quiz(course_id: int, data: QuizInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    start, end = utc(data.starts_at), utc(data.ends_at)
    if end <= start:
        raise HTTPException(422, 'پایان کوییز باید بعد از شروع آن باشد.')
    for q in data.questions:
        topic_access(db, course_id, q.topic_id)
        if q.kind == 'choice':
            if not 2 <= len(q.options) <= 8 or any(not o.strip() or len(o) > 1000 for o in q.options) or len(set(q.options)) != len(q.options):
                raise HTTPException(422, 'سؤال تستی به ۲ تا ۸ گزینهٔ غیرخالی و بدون تکرار نیاز دارد.')
            if q.correct_choice is None or q.correct_choice >= len(q.options):
                raise HTTPException(422, 'پاسخ صحیح سؤال تستی را مشخص کنید.')
        elif q.options or q.correct_choice is not None:
            raise HTTPException(422, 'سؤال تشریحی گزینه یا پاسخ تستی ندارد.')
    quiz = Quiz(course_id=course_id, title=data.title, instructions=data.instructions,
                starts_at=start, ends_at=end, duration_minutes=data.duration_minutes)
    db.add(quiz)
    db.flush()
    db.add_all([QuizQuestion(quiz_id=quiz.id, position=i, **q.model_dump()) for i, q in enumerate(data.questions)])
    db.commit()
    return quiz_dict(db, quiz, True)


@router.post('/quizzes/{quiz_id}/publish')
def publish_quiz(quiz_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    quiz = quiz_access(db, user, quiz_id, True)
    if quiz.ends_at <= now():
        raise HTTPException(422, 'زمان کوییز تمام شده است.')
    quiz.published = True
    db.commit()
    return quiz_dict(db, quiz, True)


def attempt_dict(db, attempt, teacher=False):
    quiz = db.get(Quiz, attempt.quiz_id)
    qs = questions(db, quiz.id)
    answers = {a.question_id: a for a in db.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id))}
    pending = attempt.submitted_at is not None and any(a.score is None for a in answers.values())
    return {'id': attempt.id, 'quiz_id': quiz.id, 'title': quiz.title, 'instructions': quiz.instructions,
            'started_at': iso(attempt.started_at), 'deadline': iso(attempt.deadline), 'server_now': iso(now()),
            'submitted_at': iso(attempt.submitted_at), 'expired': attempt.expired,
            'pending_grading': pending, 'score': None if attempt.submitted_at is None or pending else sum(a.score or 0 for a in answers.values()),
            'max_score': sum(q.points for q in qs), 'questions': [question_dict(q, teacher) for q in qs],
            'answers': [{'question_id': a.question_id, 'value': a.value,
                         'score': a.score if attempt.submitted_at else None, 'feedback': a.feedback} for a in answers.values()]}


@router.get('/courses/{course_id}/quizzes')
def list_quizzes(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = course_access(db, user, course_id)
    teacher = can_edit_course(db, user, course)
    stmt = select(Quiz).where(Quiz.course_id == course_id).order_by(Quiz.id.desc())
    if not teacher:
        stmt = stmt.where(Quiz.published.is_(True))
    result = []
    for quiz in db.scalars(stmt):
        item = quiz_dict(db, quiz, teacher)
        if not teacher:
            attempt = db.scalar(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == user.id).with_for_update())
            if attempt:
                expire(db, attempt)
                item['attempt'] = attempt_dict(db, attempt)
        result.append(item)
    db.commit()
    return result


@router.post('/quizzes/{quiz_id}/start')
def start_quiz(quiz_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, 'student')
    quiz = quiz_access(db, user, quiz_id)
    if not quiz.published:
        raise HTTPException(409, 'کوییز منتشر نشده است.')
    attempt = db.scalar(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == user.id).with_for_update())
    if attempt:
        expire(db, attempt)
        db.commit()
        return attempt_dict(db, attempt)
    timestamp = now()
    if not quiz.starts_at <= timestamp < quiz.ends_at:
        raise HTTPException(409, 'کوییز در این زمان قابل شروع نیست.')
    attempt = QuizAttempt(quiz_id=quiz.id, student_id=user.id, started_at=timestamp,
                          deadline=min(timestamp + timedelta(minutes=quiz.duration_minutes), quiz.ends_at))
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        attempt = db.scalar(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == user.id))
        if attempt is None:
            raise
    return attempt_dict(db, attempt)


def student_attempt(db, user, attempt_id):
    role_required(user, 'student')
    attempt = db.scalar(select(QuizAttempt).where(QuizAttempt.id == attempt_id).with_for_update())
    if not attempt or attempt.student_id != user.id:
        raise HTTPException(404, 'پاسخ‌نامه پیدا نشد.')
    quiz_access(db, user, attempt.quiz_id)
    expire(db, attempt)
    return attempt


@router.get('/quiz-attempts/{attempt_id}')
def get_attempt(attempt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    attempt = student_attempt(db, user, attempt_id)
    db.commit()
    return attempt_dict(db, attempt)


@router.put('/quiz-attempts/{attempt_id}/answers/{question_id}')
def save_answer(attempt_id: int, question_id: int, data: QuizAnswerInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    attempt = student_attempt(db, user, attempt_id)
    if attempt.submitted_at:
        db.commit()
        raise HTTPException(409, 'مهلت پاسخ‌گویی پایان یافته یا پاسخ‌نامه ثبت نهایی شده است.')
    q = db.get(QuizQuestion, question_id)
    if not q or q.quiz_id != attempt.quiz_id:
        raise HTTPException(404, 'سؤال در این کوییز وجود ندارد.')
    if q.kind == 'choice' and data.value != '' and data.value not in {str(i) for i in range(len(q.options))}:
        raise HTTPException(422, 'گزینهٔ پاسخ معتبر نیست.')
    answer = db.scalar(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id, QuizAnswer.question_id == q.id))
    if not answer:
        answer = QuizAnswer(attempt_id=attempt.id, question_id=q.id)
        db.add(answer)
    answer.value, answer.updated_at = data.value, now()
    db.commit()
    return {'saved': True, 'server_now': iso(now()), 'deadline': iso(attempt.deadline)}


@router.post('/quiz-attempts/{attempt_id}/submit')
def submit_attempt(attempt_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    attempt = student_attempt(db, user, attempt_id)
    finalize(db, attempt)
    db.commit()
    return attempt_dict(db, attempt)


@router.get('/quizzes/{quiz_id}/results')
def quiz_results(quiz_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    quiz = quiz_access(db, user, quiz_id, True)
    attempts = db.scalars(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id).with_for_update()).all()
    for attempt in attempts:
        expire(db, attempt)
    db.commit()
    by_student = {a.student_id: a for a in attempts}
    students = db.scalars(select(User).join(Enrollment).where(Enrollment.course_id == quiz.course_id)).all()
    return {'quiz': quiz_dict(db, quiz, True), 'results': [
        {'student': user_dict(student), 'attempt': attempt_dict(db, by_student[student.id], True) if student.id in by_student else None} for student in students]}


@router.put('/quiz-attempts/{attempt_id}/grades/{question_id}')
def grade_answer(attempt_id: int, question_id: int, data: QuizGradeInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    attempt = db.scalar(select(QuizAttempt).where(QuizAttempt.id == attempt_id).with_for_update())
    if not attempt:
        raise HTTPException(404, 'پاسخ‌نامه پیدا نشد.')
    quiz_access(db, user, attempt.quiz_id, True)
    expire(db, attempt)
    if not attempt.submitted_at:
        raise HTTPException(409, 'پاسخ‌نامه هنوز نهایی نشده است.')
    q = db.get(QuizQuestion, question_id)
    if not q or q.quiz_id != attempt.quiz_id or q.kind != 'short':
        raise HTTPException(422, 'نمره‌دهی دستی فقط برای سؤال تشریحی همین کوییز مجاز است.')
    if data.score > q.points:
        raise HTTPException(422, 'نمره از بارم سؤال بیشتر است.')
    answer = db.scalar(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id, QuizAnswer.question_id == q.id))
    answer.score, answer.feedback = data.score, data.feedback
    db.commit()
    return attempt_dict(db, attempt, True)
