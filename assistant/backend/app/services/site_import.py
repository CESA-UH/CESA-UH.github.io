"""Import trusted local course documents, never execute instructions in documents."""
import hashlib
import json
import re
import secrets
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
from sqlalchemy import select, delete
from app.models import (Course, CourseInvite, Topic, SiteCourse, Resource, ResourceChunk,
                        ResourceOrigin, TopicReading, SiteTopic, ChunkSearchTerm, ChunkSearchDocument)
from app.services.retrieval import iter_pages, chunk_page
from app.services.search_index import index_chunks
from app.core.config import settings


def plain(text):
    return re.sub(r'[*_`]', '', text).strip()


def sessions(markdown):
    result = []
    for line in markdown.splitlines():
        if not line.strip().startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) < 5 or not cells[0].translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')).isdigit():
            continue
        links = []
        for cell in cells[3:]:
            match = re.search(r'\[([^\]]+)\]\((.+)\)', cell)
            if match:
                links.append((plain(match[1]), match[2]))
        result.append({'name': plain(cells[1]), 'number': cells[0],
                       'reading': plain(cells[4]) if cells[4] != '-' else '', 'links': links})
    return result


def local_pdf(docs, value, course_id):
    parsed = urlparse(value)
    if parsed.scheme:
        if parsed.hostname not in {'github.com', 'raw.githubusercontent.com', 'cesa-uh.github.io'}:
            return None
        path = unquote(parsed.path)
        prefix = f'/docs-src/{course_id}/docs/'
        if prefix in path:
            relative = path.split(prefix, 1)[1]
        elif path.startswith(f'/courses/{course_id}/'):
            relative = path.split(f'/courses/{course_id}/', 1)[1]
        else:
            return None
    else:
        relative = unquote(parsed.path)
    path = (docs / relative).resolve()
    if not path.is_relative_to(docs.resolve()) or path.suffix.lower() != '.pdf':
        return None
    return path


def ingest(db, course, owner, path, relative, public_url, title=None):
    if path.stat().st_size > settings.MAX_UPLOAD_BYTES:
        raise ValueError('فایل بزرگ‌تر از حد مجاز است')
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(65536), b''):
            hasher.update(block)
    digest = hasher.hexdigest()
    origin = db.scalar(select(ResourceOrigin).where(ResourceOrigin.course_id == course.id, ResourceOrigin.source_key == relative))
    if origin and origin.digest == digest:
        return db.get(Resource, origin.resource_id), False
    # A single file is replaced atomically; an extraction failure preserves its old version.
    with db.begin_nested():
        resource = db.get(Resource, origin.resource_id) if origin else Resource(
            course_id=course.id, topic_id=None, title=(title or path.stem)[:255], filename=path.name[:255], uploaded_by=owner.id, page_count=0)
        if origin:
            ids = select(ResourceChunk.id).where(ResourceChunk.resource_id == resource.id)
            db.execute(delete(ChunkSearchTerm).where(ChunkSearchTerm.chunk_id.in_(ids)))
            db.execute(delete(ChunkSearchDocument).where(ChunkSearchDocument.chunk_id.in_(ids)))
            db.execute(delete(ResourceChunk).where(ResourceChunk.resource_id == resource.id))
        else:
            db.add(resource)
            db.flush()
        position, batch = 0, []
        with path.open('rb') as handle:
            for number, text in iter_pages(path.name, handle):
                resource.page_count = number
                for content in chunk_page(text):
                    chunk = ResourceChunk(resource_id=resource.id, page=number, position=position, text=content)
                    position += 1
                    db.add(chunk)
                    batch.append(chunk)
                    if len(batch) == 100:
                        db.flush()
                        index_chunks(db, batch, resource.title)
                        batch = []
        if batch:
            db.flush()
            index_chunks(db, batch, resource.title)
        if origin:
            origin.digest, origin.url = digest, public_url
        else:
            db.add(ResourceOrigin(resource_id=resource.id, course_id=course.id, source_key=relative, url=public_url, digest=digest))
        db.flush()
    return resource, True


def sync_site(db, root, owner, base_url='https://cesa-uh.github.io'):
    root = Path(root).resolve()
    base = urlparse(base_url)
    if base.scheme not in {'http', 'https'} or not base.netloc or base.query or base.fragment:
        raise ValueError('آدرس عمومی سایت معتبر نیست')
    catalog = json.loads((root / 'courses/index.json').read_text())
    stats = {'courses': 0, 'topics': 0, 'imported_resources': 0, 'unchanged_resources': 0, 'warnings': []}
    for item in catalog:
        cid = item['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', cid):
            raise ValueError('شناسهٔ درس معتبر نیست')
        docs = (root / 'docs-src' / cid / 'docs').resolve()
        if not docs.is_relative_to(root) or not (docs / 'index.md').is_file():
            stats['warnings'].append(f'{cid}: سورس درس موجود نیست')
            continue
        # Term-specific stable identity; a later semester gets its own data and permissions.
        key = cid + '-' + item.get('term_en', 'current').replace(' ', '-')
        mapping = db.get(SiteCourse, key)
        if mapping:
            course = db.get(Course, mapping.course_id)
        else:
            course = Course(name=item['title_fa']+' — '+item.get('term_fa', ''), description=item.get('desc_fa', ''), teacher_id=owner.id)
            db.add(course)
            db.flush()
            db.add(CourseInvite(course_id=course.id, code=secrets.token_hex(5).upper()))
            mapping = SiteCourse(key=key, course_id=course.id, url=base_url.rstrip('/')+'/courses/'+cid+'/', open_enrollment=True)
            db.add(mapping)
        stats['courses'] += 1
        # Session number in description keeps repeated session titles distinct.
        topic_links = {}
        from app.models import SiteDocument
        edited = db.get(SiteDocument, (key, 'index.md'))
        for session in sessions(edited.markdown if edited else (docs / 'index.md').read_text()):
            description = 'جلسهٔ '+session['number'] + (' • مطالعه: '+session['reading'] if session['reading'] else '')
            db.flush()
            entry = db.get(SiteTopic, (key, session['number']))
            topic = db.get(Topic, entry.topic_id) if entry else None
            if not topic:
                topic = Topic(course_id=course.id, name=session['name'], description=description)
                db.add(topic)
                db.flush()
                db.add(SiteTopic(site_key=key, session=session['number'], topic_id=topic.id))
            else:
                topic.name, topic.description = session['name'], description
            stats['topics'] += 1
            for title, link in session['links']:
                path = local_pdf(docs, link, cid)
                if path and path.is_file():
                    topic_links.setdefault(path, []).append(topic.id)
                else:
                    stats['warnings'].append(f'{cid} / جلسه {session["number"]}: منبع موجود نیست: {title}')
        for path in sorted(docs.rglob('*.pdf')):
            path = path.resolve()
            if not path.is_relative_to(docs):
                stats['warnings'].append(f'{cid}: فایل خارج از پوشهٔ منابع نادیده گرفته شد')
                continue
            relative = path.relative_to(docs).as_posix()
            url = base_url.rstrip('/') + '/courses/'+quote(cid)+'/'+quote(relative, safe='/')
            try:
                resource, changed = ingest(db, course, owner, path, relative, url)
                for tid in set(topic_links.get(path, [])):
                    if not db.get(TopicReading, (tid, resource.id)):
                        db.add(TopicReading(topic_id=tid, resource_id=resource.id))
                stats['imported_resources' if changed else 'unchanged_resources'] += 1
            except ValueError as exc:
                stats['warnings'].append(f'{cid} / {path.name}: {exc}')
        db.commit()
    return stats
