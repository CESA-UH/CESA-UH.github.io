from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


assessment_questions = Table(
    "assessment_questions",
    Base.metadata,
    Column(
        "assessment_id",
        ForeignKey("assessments.id"),
        primary_key=True,
    ),
    Column(
        "question_id",
        ForeignKey("questions.id"),
        primary_key=True,
    ),
    Column(
        "question_order",
        Integer,
        nullable=False,
    ),
)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    duration: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="assessments",
    )

    questions: Mapped[list["Question"]] = relationship(
        "Question",
        secondary=assessment_questions,
        back_populates="assessments",
    )
    attempts: Mapped[list["Attempt"]] = relationship(
        "Attempt",
        back_populates="assessment",
    )