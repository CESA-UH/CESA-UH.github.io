from datetime import datetime
from enum import Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime, Enum as SQLEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, inherit_schema=True),
        default=UserRole.STUDENT,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    courses: Mapped[list["Course"]] = relationship(
        "Course",
        back_populates="teacher",
    )
    attempts: Mapped[list["Attempt"]] = relationship(
        "Attempt",
        back_populates="student",
    )
    skills: Mapped[list["StudentSkill"]] = relationship(
        "StudentSkill",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["StudentEvent"]] = relationship(
        "StudentEvent",
        back_populates="student",
        cascade="all, delete-orphan",
    )