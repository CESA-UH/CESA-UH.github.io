from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from typing import Literal
from sqlalchemy import select, or_, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.services.permissions import can_edit_course
from app.core.database import get_db
from app.core.security import current_user
from app.models import User, UserRole, Course, CourseAssistant, Enrollment, SiteCourse, TopicReading, Resource
from app.schemas import Input, Register
from app.api import topic_access, course_access, course_dict, user_dict, role_required

router = APIRouter(prefix='/api')


class MemberInput(Input):
    student_id: int = Field(gt=0)


class OwnerInput(Input):
    teacher_id: int = Field(gt=0)


@router.get('/admin/users')
def users(q: str = '', offset: int = 0, role: Literal['all','student','teacher','admin','assistant']='all', user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, 'admin')
    if offset < 0 or len(q) > 255:
        raise HTTPException(422, 'جست‌وجو معتبر نیست.')
    stmt = select(User).order_by(User.id)
    if role=='assistant':
        stmt=stmt.where(User.id.in_(select(CourseAssistant.student_id)))
    elif role!='all':
        stmt=stmt.where(User.role==UserRole(role))
    if q.strip():
        # Substring search; escape SQL wildcard characters in the search input.
        query = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        stmt = stmt.where(or_(User.email.ilike('%'+query+'%', escape='\\'), User.first_name.ilike('%'+query+'%', escape='\\'), User.last_name.ilike('%'+query+'%', escape='\\')))
    return [user_dict(u) for u in db.scalars(stmt.offset(offset).limit(100))]


@router.get('/courses/{course_id}/assistants')
def assistants(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    rows = db.execute(select(CourseAssistant, User).join(User, User.id == CourseAssistant.student_id).where(CourseAssistant.course_id == course_id)).all()
    return [{'student': user_dict(student), 'assigned_at': grant.assigned_at.isoformat()+'Z'} for grant, student in rows]


@router.put('/courses/{course_id}/assistants')
def assign_assistant(course_id: int, data: MemberInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, 'admin')
    course_access(db, user, course_id, teacher_only=True)
    student = db.get(User, data.student_id)
    if not student or student.role != UserRole.STUDENT:
        raise HTTPException(422, 'حل‌تمرین باید از حساب‌های دانشجو انتخاب شود.')
    if not db.get(CourseAssistant, (course_id, student.id)):
        db.add(CourseAssistant(course_id=course_id, student_id=student.id, assigned_by=user.id))
    # Staff access is independent of learner enrollment; do not manufacture a learning record.
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # An identical concurrent assignment is idempotent.
        if not db.get(CourseAssistant, (course_id, student.id)):
            raise HTTPException(409, 'تعیین نقش هم‌زمان انجام شد؛ دوباره تلاش کنید.')
    return {'student': user_dict(student), 'course_id': course_id}


@router.delete('/courses/{course_id}/assistants/{student_id}', status_code=204)
def revoke_assistant(course_id: int, student_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, 'admin')
    course_access(db, user, course_id, teacher_only=True)
    grant = db.get(CourseAssistant, (course_id, student_id))
    if grant:
        db.delete(grant)
        db.commit()
    # Revoke edit access, preserve membership, submissions and report history.


@router.put('/courses/{course_id}/teacher')
def assign_teacher(course_id: int, data: OwnerInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, 'admin')
    course = course_access(db, user, course_id, teacher_only=True)
    teacher = db.get(User, data.teacher_id)
    if not teacher or teacher.role != UserRole.TEACHER:
        raise HTTPException(422, 'یک حساب استاد انتخاب کنید.')
    course.teacher_id = teacher.id
    db.commit()
    return course_dict(db, course, user)


@router.post('/courses/{course_id}/members')
def enroll_member(course_id: int, data: MemberInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, 'admin')
    course_access(db, user, course_id, teacher_only=True)
    student = db.get(User, data.student_id)
    if not student or student.role != UserRole.STUDENT:
        raise HTTPException(422, 'یک حساب دانشجو انتخاب کنید.')
    if not db.scalar(select(Enrollment.id).where(Enrollment.course_id == course_id, Enrollment.student_id == student.id)):
        db.add(Enrollment(course_id=course_id, student_id=student.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return {'student': user_dict(student), 'course_id': course_id}


@router.post('/site-courses/{key}/open')
def open_site_course(key: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    mapping = db.get(SiteCourse, key)
    if not mapping:
        raise HTTPException(404, 'این درس هنوز به سامانه متصل نشده است.')
    course = db.get(Course, mapping.course_id)
    if user.role == UserRole.STUDENT and mapping.open_enrollment and not can_edit_course(db, user, course):
        if not db.scalar(select(Enrollment.id).where(Enrollment.course_id == mapping.course_id, Enrollment.student_id == user.id)):
            db.add(Enrollment(course_id=mapping.course_id, student_id=user.id))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
    course = course_access(db, user, mapping.course_id)
    return course_dict(db, course, user)


class ReadingInput(Input):
    resource_ids: list[int] = Field(max_length=200)


@router.put('/courses/{course_id}/topics/{topic_id}/readings')
def set_readings(course_id: int, topic_id: int, data: ReadingInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    topic_access(db, course_id, topic_id)
    selected = set(data.resource_ids)
    resources = list(db.scalars(select(Resource).where(Resource.course_id == course_id, Resource.id.in_(selected))))
    if {r.id for r in resources} != selected:
        raise HTTPException(422, 'منابع باید در همین درس ثبت شده باشند.')
    db.execute(delete(TopicReading).where(TopicReading.topic_id == topic_id))
    for resource in db.scalars(select(Resource).where(Resource.course_id == course_id, Resource.topic_id == topic_id)):
        if resource.id not in selected:
            resource.topic_id = None
    db.add_all([TopicReading(topic_id=topic_id, resource_id=rid) for rid in selected])
    db.commit()
    return {'topic_id': topic_id, 'resource_ids': sorted(selected)}


class AdminCreateUser(Register):
    role: Literal['student', 'teacher', 'admin'] = 'student'


class AdminEditUser(Input):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: Literal['student', 'teacher', 'admin']


@router.post('/admin/users', status_code=201)
def create_user(data: AdminCreateUser, user: User=Depends(current_user), db: Session=Depends(get_db)):
    from app.core.security import hash_password
    role_required(user, 'admin')
    if db.scalar(select(User).where(User.email==data.email)):
        raise HTTPException(409,'این ایمیل حساب دارد.')
    row=User(email=data.email,first_name=data.first_name,last_name=data.last_name,
             role=UserRole(data.role),password_hash=hash_password(data.password))
    db.add(row)
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'این ایمیل حساب دارد.')
    return user_dict(row)


@router.put('/admin/users/{user_id}')
def edit_user(user_id:int,data:AdminEditUser,user:User=Depends(current_user),db:Session=Depends(get_db)):
    role_required(user,'admin')
    row=db.get(User,user_id)
    if not row:raise HTTPException(404,'حساب پیدا نشد.')
    target=UserRole(data.role)
    if row.role!=target:
        if row.id==user.id:raise HTTPException(422,'نقش حساب ادمین فعلی قابل تغییر نیست.')
        if target==UserRole.STUDENT and db.scalar(select(Course.id).where(Course.teacher_id==row.id)):
            raise HTTPException(422,'ابتدا استاد درس‌های این حساب را تغییر دهید.')
        if target!=UserRole.STUDENT and db.scalar(select(CourseAssistant.course_id).where(CourseAssistant.student_id==row.id)):
            raise HTTPException(422,'ابتدا نقش حل‌تمرین این حساب را از درس‌ها لغو کنید.')
    row.first_name,row.last_name,row.role=data.first_name,data.last_name,target
    db.commit()
    return user_dict(row)


@router.get('/admin/users/{user_id}/courses')
def user_courses(user_id:int,user:User=Depends(current_user),db:Session=Depends(get_db)):
    role_required(user,'admin')
    row=db.get(User,user_id)
    if not row:raise HTTPException(404,'حساب پیدا نشد.')
    taught=list(db.scalars(select(Course).where(Course.teacher_id==user_id)))
    assisted=list(db.scalars(select(Course).join(CourseAssistant).where(CourseAssistant.student_id==user_id)))
    enrolled=list(db.scalars(select(Course).join(Enrollment).where(Enrollment.student_id==user_id)))
    return {'teacher':[{'id':c.id,'name':c.name} for c in taught],
            'assistant':[{'id':c.id,'name':c.name} for c in assisted],
            'student':[{'id':c.id,'name':c.name} for c in enrolled]}
