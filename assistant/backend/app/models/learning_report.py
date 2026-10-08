from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class LearningReport(Base):
    __tablename__ = 'learning_reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey('courses.id'), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    # NULL for terminal jobs; uniqueness prevents duplicate active jobs even across processes.
    active_key: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='queued', index=True)
    phase: Mapped[str] = mapped_column(String(255), default='در صف تهیهٔ گزارش')
    progress: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    snapshot_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)
    models: Mapped[list] = mapped_column(JSON, default=list)
    content: Mapped[str] = mapped_column(Text, default='')
    error: Mapped[str] = mapped_column(Text, default='')
