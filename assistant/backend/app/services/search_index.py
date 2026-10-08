"""Portable, persistent inverted index for exact lexical BM25 retrieval."""
from collections import Counter
from sqlalchemy import insert, select
from app.models import Resource, ResourceChunk, ChunkSearchDocument, ChunkSearchTerm


def index_chunks(db, chunks, title):
    # Imported here so extraction and query tokenization share the same rules.
    from app.services.retrieval import tokens
    documents, postings = [], []
    for chunk in chunks:
        counts = Counter(t for t in tokens(chunk.text + ' ' + title) if len(t) <= 255)
        documents.append({'chunk_id': chunk.id, 'length': sum(counts.values())})
        postings.extend({'chunk_id': chunk.id, 'term': term, 'frequency': count} for term, count in counts.items())
    if documents:
        db.execute(insert(ChunkSearchDocument), documents)
    # Limit bind parameters and temporary allocations on both SQLite and PostgreSQL.
    for start in range(0, len(postings), 1000):
        db.execute(insert(ChunkSearchTerm), postings[start:start + 1000])


def backfill(db, course_id=None, batch_size=100):
    """Index legacy chunks in bounded batches; caller controls the transaction."""
    last_id = 0
    while True:
        statement = (select(ResourceChunk, Resource.title)
                     .join(Resource, Resource.id == ResourceChunk.resource_id)
                     .outerjoin(ChunkSearchDocument, ChunkSearchDocument.chunk_id == ResourceChunk.id)
                     .where(ChunkSearchDocument.chunk_id.is_(None), ResourceChunk.id > last_id)
                     .order_by(ResourceChunk.id).limit(batch_size))
        if course_id is not None:
            statement = statement.where(Resource.course_id == course_id)
        rows = db.execute(statement).all()
        if not rows:
            return
        # Resource titles differ, so group each bounded batch by resource.
        groups = {}
        for chunk, title in rows:
            groups.setdefault((chunk.resource_id, title), []).append(chunk)
        for (_, title), chunks in groups.items():
            index_chunks(db, chunks, title)
        last_id = rows[-1][0].id
