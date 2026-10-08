"""Course-scoped permissions and stable connections to the public documentation site."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class CourseAssistant(Base):
    __tablename__ = 'course_assistants'
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), primary_key=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SiteCourse(Base):
    __tablename__ = 'site_courses'
    key: Mapped[str] = mapped_column(String(150), primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'), unique=True)
    url: Mapped[str] = mapped_column(String(1000))
    open_enrollment: Mapped[bool] = mapped_column(Boolean, default=True)


class ResourceOrigin(Base):
    __tablename__ = 'resource_origins'
    __table_args__ = (UniqueConstraint('course_id', 'source_key'),)
    resource_id: Mapped[int] = mapped_column(ForeignKey('resources.id'), primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'))
    source_key: Mapped[str] = mapped_column(String(1000))
    url: Mapped[str] = mapped_column(String(2000))
    digest: Mapped[str] = mapped_column(String(64))


class TopicReading(Base):
    __tablename__ = 'topic_readings'
    topic_id: Mapped[int] = mapped_column(ForeignKey('topics.id'), primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey('resources.id'), primary_key=True)


class SiteTopic(Base):
    __tablename__ = 'site_course_topics'
    site_key: Mapped[str] = mapped_column(ForeignKey('site_courses.key'), primary_key=True)
    session: Mapped[str] = mapped_column(String(20), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey('topics.id'), unique=True)
