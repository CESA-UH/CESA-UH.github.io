from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    teacher: Mapped["User"] = relationship(
        "User",
        back_populates="courses",
    )
    topics: Mapped[list["Topic"]] = relationship(
        "Topic",
        back_populates="course",
    )
    assessments: Mapped[list["Assessment"]] = relationship(
        "Assessment",
        back_populates="course",
    )
    events: Mapped[list["StudentEvent"]] = relationship(
        "StudentEvent",
        back_populates="course",
        cascade="all, delete-orphan",
    )