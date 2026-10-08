from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class SiteDocument(Base):
    __tablename__ = 'site_documents'
    site_key: Mapped[str] = mapped_column(ForeignKey('site_courses.key'), primary_key=True)
    path: Mapped[str] = mapped_column(String(500), primary_key=True)
    markdown: Mapped[str] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(default=1)
    edited_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SiteDocumentRevision(Base):
    __tablename__ = 'site_document_revisions'
    __table_args__ = (UniqueConstraint('site_key', 'path', 'revision'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    site_key: Mapped[str] = mapped_column(ForeignKey('site_courses.key'))
    path: Mapped[str] = mapped_column(String(500))
    revision: Mapped[int] = mapped_column()
    markdown: Mapped[str] = mapped_column(Text)
    edited_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SiteFile(Base):
    __tablename__ = 'site_files'
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    site_key: Mapped[str] = mapped_column(ForeignKey('site_courses.key'))
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    resource_id: Mapped[int | None] = mapped_column(ForeignKey('resources.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
