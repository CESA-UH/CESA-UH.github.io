"""Persist the BM25 document lengths and inverted postings."""
from alembic import op
import sqlalchemy as sa
revision = '7c4e910'
down_revision = '1b0e032'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('chunk_search_documents',
        sa.Column('chunk_id', sa.Integer(), sa.ForeignKey('resource_chunks.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('length', sa.Integer(), nullable=False))
    op.create_table('chunk_search_terms',
        sa.Column('chunk_id', sa.Integer(), sa.ForeignKey('chunk_search_documents.chunk_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('term', sa.String(255), primary_key=True),
        sa.Column('frequency', sa.Integer(), nullable=False))
    op.create_index('ix_chunk_search_terms_term_chunk', 'chunk_search_terms', ['term', 'chunk_id'])


def downgrade():
    op.drop_table('chunk_search_terms')
    op.drop_table('chunk_search_documents')
