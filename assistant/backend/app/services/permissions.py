from app.models import UserRole, CourseAssistant


def course_role(db, user, course):
    if user.role == UserRole.ADMIN:
        return 'admin'
    if course.teacher_id == user.id and user.role == UserRole.TEACHER:
        return 'teacher'
    if db.get(CourseAssistant, (course.id, user.id)):
        return 'assistant'
    return 'student'


def can_edit_course(db, user, course):
    return course_role(db, user, course) in {'admin', 'teacher', 'assistant'}
