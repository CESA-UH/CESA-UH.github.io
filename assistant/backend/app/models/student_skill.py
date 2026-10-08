from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StudentSkill(Base):
    __tablename__ = "student_skills"

    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "topic_id",
            name="uq_student_topic",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id"),
        nullable=False,
    )

    mastery: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    student: Mapped["User"] = relationship(
        "User",
        back_populates="skills",
    )

    topic: Mapped["Topic"] = relationship(
        "Topic",
        back_populates="student_skills",
    )