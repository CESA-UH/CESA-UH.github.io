from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="topics",
    )

    parent: Mapped["Topic | None"] = relationship(
        "Topic",
        remote_side="Topic.id",
        back_populates="children",
    )

    children: Mapped[list["Topic"]] = relationship(
        "Topic",
        back_populates="parent",
    )
    questions: Mapped[list["Question"]] = relationship(
        "Question",
        back_populates="topic",
    )
    student_skills: Mapped[list["StudentSkill"]] = relationship(
        "StudentSkill",
        back_populates="topic",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["StudentEvent"]] = relationship(
        "StudentEvent",
        back_populates="topic",
    )