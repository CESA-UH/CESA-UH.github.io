from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id"),
        nullable=False,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    assessment: Mapped["Assessment"] = relationship(
        "Assessment",
        back_populates="attempts",
    )

    student: Mapped["User"] = relationship(
        "User",
        back_populates="attempts",
    )

    answers: Mapped[list["Answer"]] = relationship(
        "Answer",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )