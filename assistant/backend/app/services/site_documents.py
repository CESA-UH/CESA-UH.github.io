import hashlib
import json
import re
from pathlib import Path
import bleach
import markdown
from fastapi import HTTPException
from app.core.config import settings
from app.models import SiteCourse
from sqlalchemy import select


def course_source(db, key):
    mapping = db.get(SiteCourse, key)
    if not mapping:
        raise HTTPException(404, 'درس پیدا نشد.')
    root = Path(settings.ECE_DOCS_PATH).resolve() if settings.ECE_DOCS_PATH else None
    if not root or not (root / 'courses/index.json').is_file():
        raise HTTPException(503, 'محتوای سایت روی این سرور تنظیم نشده است.')
    for course in json.loads((root / 'courses/index.json').read_text()):
        if key == course['id']+'-'+course.get('term_en','current').replace(' ','-'):
            slug = course['id']
            if not re.fullmatch(r'[A-Za-z0-9_-]+', slug):
                break
            return mapping, (root / 'docs-src' / slug / 'docs').resolve()
    raise HTTPException(404, 'سورس این درس پیدا نشد.')


def document_source(db, key, path):
    mapping, root = course_source(db, key)
    # Existing Markdown pages only; never allow config, hidden files or traversal.
    parts = Path(path).parts
    if not parts or any(p.startswith('.') for p in parts) or Path(path).is_absolute() or '\\' in path:
        raise HTTPException(422, 'مسیر صفحه معتبر نیست.')
    file = (root / path).resolve()
    if not file.is_relative_to(root) or file.suffix != '.md' or not file.is_file():
        raise HTTPException(404, 'صفحه پیدا نشد.')
    text = file.read_text(encoding='utf-8')
    return mapping, text, hashlib.sha256(text.encode()).hexdigest()


def render_document(text, path='index.md'):
    # No snippets/includes or execution extensions; protect visitors from raw HTML.
    html = markdown.markdown(text, extensions=['tables', 'fenced_code', 'attr_list', 'toc', 'pymdownx.arithmatex'],
                             extension_configs={'pymdownx.arithmatex': {'generic': True}})
    tags = {'p','br','hr','h1','h2','h3','h4','h5','h6','strong','em','del','blockquote','ul','ol','li','pre','code',
            'table','thead','tbody','tr','th','td','a','img','span','div','details','summary','sup','sub'}
    clean = bleach.clean(html, tags=tags, attributes={
        '*':['id','class'], 'a':['href','title','target','rel'], 'img':['src','alt','title'],
        'th':['align'], 'td':['align'], 'ol':['start']}, protocols=['http','https','mailto'], strip=True)
    if path != 'index.md':
        from urllib.parse import urlparse
        def adjust(match):
            value=match[2]
            if not value.startswith(('/', '#', '?')) and not urlparse(value).scheme:
                value='../'+value
            return match[1]+value+match[3]
        clean=re.sub(r'(\b(?:href|src)=")([^"]*)(")',adjust,clean)
    return clean


def published_page(path):
    if path in {'index.md'}:
        return 'index.html'
    return path[:-3] + '/index.html'
