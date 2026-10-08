from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("course_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CourseInvite(Base):
    __tablename__ = "course_invites"
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)


class SelfReport(Base):
    __tablename__ = "self_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), index=True)
    confidence: Mapped[int] = mapped_column(Integer)
    difficulty: Mapped[str] = mapped_column(String(30))
    study_minutes: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    page_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResourceChunk(Base):
    __tablename__ = "resource_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id"), index=True)
    page: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class ChunkSearchDocument(Base):
    __tablename__ = "chunk_search_documents"
    chunk_id: Mapped[int] = mapped_column(ForeignKey("resource_chunks.id", ondelete="CASCADE"), primary_key=True)
    length: Mapped[int] = mapped_column(Integer)


class ChunkSearchTerm(Base):
    __tablename__ = "chunk_search_terms"
    __table_args__ = (Index("ix_chunk_search_terms_term_chunk", "term", "chunk_id"),)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("chunk_search_documents.chunk_id", ondelete="CASCADE"), primary_key=True)
    term: Mapped[str] = mapped_column(String(255), primary_key=True)
    frequency: Mapped[int] = mapped_column(Integer)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(30), default="retrieval")
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatThread(Base):
    __tablename__ = "chat_threads"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="گفت‌وگوی جدید")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatThreadMessage(Base):
    __tablename__ = "chat_thread_messages"
    message_id: Mapped[int] = mapped_column(ForeignKey("chat_messages.id"), primary_key=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("chat_threads.id"), index=True)
