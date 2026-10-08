from datetime import datetime, timezone
from sqlalchemy import select
from app.models import Quiz, QuizQuestion, QuizAttempt, QuizAnswer


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def questions(db, quiz_id):
    return db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.position)).all()


def finalize(db, attempt, expired=False):
    if attempt.submitted_at is not None:
        return
    existing = {a.question_id: a for a in db.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id))}
    for question in questions(db, attempt.quiz_id):
        answer = existing.get(question.id)
        if answer is None:
            answer = QuizAnswer(attempt_id=attempt.id, question_id=question.id, value='')
            db.add(answer)
        if not answer.value.strip():
            answer.score = 0
        elif question.kind == 'choice':
            answer.score = question.points if answer.value == str(question.correct_choice) else 0
        else:
            answer.score = None
    attempt.expired = expired
    attempt.submitted_at = attempt.deadline if expired else now()
    db.flush()


def expire(db, attempt):
    if attempt.submitted_at is None and now() >= attempt.deadline:
        finalize(db, attempt, True)


def expire_course_attempts(db, course_id, student_id):
    rows = db.scalars(select(QuizAttempt).join(Quiz, Quiz.id == QuizAttempt.quiz_id)
        .where(Quiz.course_id == course_id, QuizAttempt.student_id == student_id,
               QuizAttempt.submitted_at.is_(None), QuizAttempt.deadline <= now()).with_for_update()).all()
    for attempt in rows:
        expire(db, attempt)
    if rows:
        db.commit()
