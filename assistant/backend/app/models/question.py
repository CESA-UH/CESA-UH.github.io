from datetime import datetime
from enum import Enum
from app.models.assessment import assessment_questions
from sqlalchemy import DateTime, Enum as SQLEnum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id"),
        nullable=False,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    question_type: Mapped[QuestionType] = mapped_column(
        SQLEnum(QuestionType, inherit_schema=True),
        nullable=False,
    )

    difficulty: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
    )

    correct_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    topic: Mapped["Topic"] = relationship(
        "Topic",
        back_populates="questions",
    )
    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment",
        secondary=assessment_questions,
        back_populates="questions",
    )
    answers: Mapped[list["Answer"]] = relationship(
        "Answer",
        back_populates="question",
    )
    events: Mapped[list["StudentEvent"]] = relationship(
        "StudentEvent",
        back_populates="question",
    )
