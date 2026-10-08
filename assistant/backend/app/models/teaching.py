from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class ReportForm(Base):
    __tablename__ = 'report_forms'
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    instructions: Mapped[str] = mapped_column(Text, default='')
    topic_ids: Mapped[list] = mapped_column(JSON)
    fields: Mapped[list] = mapped_column(JSON)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReportFormEntry(Base):
    __tablename__ = 'report_form_entries'
    report_id: Mapped[int] = mapped_column(ForeignKey('self_reports.id'), primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey('report_forms.id'), index=True)
    answers: Mapped[dict] = mapped_column(JSON)


class ChatTopicSelection(Base):
    __tablename__ = 'chat_topic_selections'
    message_id: Mapped[int] = mapped_column(ForeignKey('chat_messages.id'), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey('topics.id'), index=True)


class Quiz(Base):
    __tablename__ = 'teaching_quizzes'
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'), index=True)
    title: Mapped[str] = mapped_column(String(255))
    instructions: Mapped[str] = mapped_column(Text, default='')
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuizQuestion(Base):
    __tablename__ = 'teaching_quiz_questions'
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey('teaching_quizzes.id'), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey('topics.id'), index=True)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20))
    options: Mapped[list] = mapped_column(JSON)
    correct_choice: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points: Mapped[int] = mapped_column(Integer)


class QuizAttempt(Base):
    __tablename__ = 'teaching_quiz_attempts'
    __table_args__ = (UniqueConstraint('quiz_id', 'student_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey('teaching_quizzes.id'), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    deadline: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expired: Mapped[bool] = mapped_column(Boolean, default=False)


class QuizAnswer(Base):
    __tablename__ = 'teaching_quiz_answers'
    __table_args__ = (UniqueConstraint('attempt_id', 'question_id'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey('teaching_quiz_attempts.id'), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey('teaching_quiz_questions.id'))
    value: Mapped[str] = mapped_column(Text, default='')
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, default='')
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
