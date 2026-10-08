from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("attempts.id"),
        nullable=False,
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id"),
        nullable=False,
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    time_spent: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    answered_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    attempt: Mapped["Attempt"] = relationship(
        "Attempt",
        back_populates="answers",
    )

    question: Mapped["Question"] = relationship(
        "Question",
        back_populates="answers",
    )