from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EventType(str, Enum):
    ASSESSMENT_STARTED = "assessment_started"
    QUESTION_VIEWED = "question_viewed"
    QUESTION_ANSWERED = "question_answered"
    ANSWER_CHANGED = "answer_changed"
    ASSESSMENT_SUBMITTED = "assessment_submitted"


class StudentEvent(Base):
    __tablename__ = "student_events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )

    event_type: Mapped[EventType] = mapped_column(
        SQLEnum(EventType, inherit_schema=True),
        nullable=False,
    )

    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id"),
        nullable=True,
    )

    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id"),
        nullable=True,
    )

    event_metadata: Mapped[dict | None] = mapped_column(
        "metadata", JSON,
        nullable=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    student: Mapped["User"] = relationship(
        "User",
        back_populates="events",
    )

    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="events",
    )

    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="events",
    )

    topic: Mapped["Topic"] = relationship(
        "Topic",
        back_populates="events",
    )