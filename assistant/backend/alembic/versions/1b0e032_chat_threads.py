"""Persist independently scoped chat threads, preserving legacy messages."""
from alembic import op
import sqlalchemy as sa
revision = '1b0e032'
down_revision = '78041918e590'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('chat_threads',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('student_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),sa.Column('course_id',sa.Integer(),sa.ForeignKey('courses.id'),nullable=False),sa.Column('title',sa.String(120),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False))
    op.create_index('ix_chat_threads_student_id','chat_threads',['student_id'])
    op.create_index('ix_chat_threads_course_id','chat_threads',['course_id'])
    op.create_table('chat_thread_messages',sa.Column('message_id',sa.Integer(),sa.ForeignKey('chat_messages.id'),primary_key=True),sa.Column('thread_id',sa.Integer(),sa.ForeignKey('chat_threads.id'),nullable=False))
    op.create_index('ix_chat_thread_messages_thread_id','chat_thread_messages',['thread_id'])

def downgrade():
    op.drop_table('chat_thread_messages')
    op.drop_table('chat_threads')
