"""Local, page-aware lexical retrieval. No external embeddings or file storage."""
import io
import math
import heapq
import re
from pathlib import Path
from pypdf import PdfReader
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session
from app.models import Resource, ResourceChunk, ChunkSearchDocument, ChunkSearchTerm, TopicReading
from app.core.config import settings

STOP = set("از به با در که و را این آن یک برای است می من تو چه چطور چگونه لطفا کن کنید توضیح بده درباره رو چیست چرا دارد دارند شود شده بود باشد هست هستم لطفاً the a an is are of to in and how what explain please".split())

# Conversational filler must not make an unrelated chapter look like evidence.
STOP.update("سلام خوبی خوب هستی میخوام میخواهم بهم برام میشه ساده کامل راهنمایی کمک کجا شروع کنم کنیم درس مبحث بیشتر الگوریتم روش سازی".split())

def normalize(text):
    text = re.sub(r"[\u064b-\u065f\u0670]", "", text.lower().replace("ي", "ی").replace("ك", "ک").replace("\u200c", " "))
    # Keep A* as a searchable algorithm name instead of dropping the one-letter 'a'.
    return re.sub(r"\ba\s*[*∗]|\ba[-_ ]?star\b|ای\s*استار", " astar ", text)


def tokens(text):
    return [t for t in re.findall(r"[^\W_]+", normalize(text)) if t not in STOP and len(t) > 1]


def iter_pages(filename: str, stream):
    """Extract one page at a time; retain no list of all extracted PDF text."""
    suffix = Path(filename).suffix.lower()
    total = 0
    found = False
    try:
        if suffix == ".pdf":
            reader = PdfReader(stream)
            if reader.is_encrypted:
                raise ValueError("PDF رمزگذاری شده است؛ نسخهٔ بدون رمز بارگذاری کنید.")
            if len(reader.pages) > settings.MAX_RESOURCE_PAGES:
                raise ValueError(f"حداکثر {settings.MAX_RESOURCE_PAGES} صفحه در هر فایل مجاز است.")
            pages = ((number, page.extract_text() or "") for number, page in enumerate(reader.pages, 1))
        elif suffix in {".txt", ".md"}:
            try:
                pages = [(1, stream.read().decode("utf-8-sig"))]
            except UnicodeDecodeError as exc:
                raise ValueError("فایل متنی باید با UTF-8 ذخیره شده باشد.") from exc
        else:
            raise ValueError("فقط PDF متنی، TXT و Markdown پشتیبانی می‌شود.")
        for number, text in pages:
            # PDF encodings can emit NUL, which PostgreSQL text cannot store.
            text = text.replace("\x00", "")
            total += len(text)
            if total > settings.MAX_RESOURCE_CHARACTERS:
                raise ValueError("حجم متن استخراج‌شده بیش از حد مجاز است.")
            found = found or bool(text.strip())
            yield number, text
        if not found:
            raise ValueError("متنی استخراج نشد. PDF تصویری به OCR نیاز دارد؛ نسخهٔ متنی بارگذاری کنید.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("فایل خوانده نشد؛ فایل سالم بارگذاری کنید.") from exc


def extract_pages(filename: str, data: bytes):
    # Compatibility helper for small callers; uploads use the iterator directly.
    return [text for _, text in iter_pages(filename, io.BytesIO(data))]


def chunk_page(text, size=1000, overlap=160):
    text = re.sub(r"[ \t]+", " ", text).strip()
    for start in range(0, len(text), size - overlap):
        chunk = text[start:start + size].strip()
        if chunk:
            yield chunk
        if start + size >= len(text):
            break


def citation(chunk, resource):
    return {"chunk_id": chunk.id, "resource_id": resource.id, "title": resource.title,
            "page": chunk.page, "excerpt": chunk.text}


def retrieve(db: Session, course_id: int, query: str, topic_id=None, limit=4):
    from app.services.search_index import backfill
    query_tokens = sorted(set(t for t in tokens(query) if len(t) <= 255))[:64]
    if not query_tokens or limit <= 0:
        return []
    # Legacy resources are indexed once and participate in exactly the same score.
    # On normal startup they have already been backfilled; uploads index on write.
    backfill(db, course_id)
    scope = [Resource.course_id == course_id]
    if topic_id is not None:
        scope.append(or_(Resource.topic_id == topic_id,
                         Resource.id.in_(select(TopicReading.resource_id).where(TopicReading.topic_id == topic_id)),
                         and_(Resource.topic_id.is_(None), ~Resource.id.in_(select(TopicReading.resource_id)))))
    joins = lambda stmt: (stmt.join(ResourceChunk, ResourceChunk.id == ChunkSearchDocument.chunk_id)
                         .join(Resource, Resource.id == ResourceChunk.resource_id).where(*scope))
    count, total = db.execute(joins(select(func.count(), func.sum(ChunkSearchDocument.length))
                                   .select_from(ChunkSearchDocument))).one()
    if not count:
        return []
    average = (total or 0) / count or 1
    frequencies = dict(db.execute(joins(select(ChunkSearchTerm.term, func.count())
        .select_from(ChunkSearchDocument).join(ChunkSearchTerm, ChunkSearchTerm.chunk_id == ChunkSearchDocument.chunk_id))
        .where(ChunkSearchTerm.term.in_(query_tokens)).group_by(ChunkSearchTerm.term)).all())
    idfs = {term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in frequencies.items()}
    statement = joins(select(ChunkSearchDocument.chunk_id, ChunkSearchDocument.length,
                             ChunkSearchTerm.term, ChunkSearchTerm.frequency)
                      .select_from(ChunkSearchDocument)
                      .join(ChunkSearchTerm, ChunkSearchTerm.chunk_id == ChunkSearchDocument.chunk_id))
    statement = statement.where(ChunkSearchTerm.term.in_(query_tokens)).order_by(ChunkSearchDocument.chunk_id)
    # Score only matching postings. Keep a bounded heap and fetch full text only
    # for the final winners; a common query term cannot load an entire book.
    top = []
    def keep(score, chunk_id):
        if score > 0:
            heapq.heappush(top, (score, -chunk_id))
            if len(top) > limit:
                heapq.heappop(top)
    previous, score = None, 0.0
    for chunk_id, length, term, frequency in db.execute(statement.execution_options(yield_per=256)):
        if previous is not None and chunk_id != previous:
            keep(score, previous)
            score = 0.0
        previous = chunk_id
        score += idfs[term] * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * length / average))
    if previous is not None:
        keep(score, previous)
    top.sort(reverse=True)
    best = top[0][0] if top else 0
    ids = [-negative for score, negative in top if score >= best * 0.25]
    if not ids:
        return []
    rows = db.execute(select(ResourceChunk, Resource).join(Resource, Resource.id == ResourceChunk.resource_id)
                      .where(ResourceChunk.id.in_(ids), Resource.course_id == course_id)).all()
    results = {chunk.id: citation(chunk, resource) for chunk, resource in rows}
    return [results[chunk_id] for chunk_id in ids]
