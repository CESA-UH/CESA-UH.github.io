from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, FileResponse
from starlette.concurrency import run_in_threadpool
from pathlib import Path
import re
import json
from app.models import SiteDocument
from app.services.site_documents import render_document


class PublishedDocs(StaticFiles):
    """Publish only built pages/assets, never .git, sources, or the local venv."""
    def __init__(self, *args, session_factory=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_factory = session_factory

    def override(self, path, response):
        path = str(Path(response.path).relative_to(self.directory)).replace('\\','/') if isinstance(response, FileResponse) else path
        parts = path.split('/')
        if len(parts) < 3 or parts[0] != 'courses' or not isinstance(response, FileResponse):
            return None
        root = Path(self.directory)
        catalog = json.loads((root/'courses/index.json').read_text())
        entry = next((c for c in catalog if c['id'] == parts[1]), None)
        if not entry:return None
        page = '/'.join(parts[2:])
        source_path = 'index.md' if page in {'','index.html'} else page.removesuffix('/index.html').rstrip('/')+'.md'
        key = entry['id']+'-'+entry.get('term_en','current').replace(' ','-')
        with self.session_factory() as db:
            doc = db.get(SiteDocument, (key, source_path))
            if not doc:return None
            replacement = render_document(doc.markdown,source_path)
        html = Path(response.path).read_text()
        pattern = r'(<article\b[^>]*class="[^"\n]*md-content__inner[^"\n]*"[^>]*>)[\s\S]*?(</article>)'
        html, count = re.subn(pattern, lambda m:m[1]+replacement+m[2], html, count=1)
        return HTMLResponse(html, headers={'Cache-Control':'no-store'}) if count else None

    async def get_response(self, path, scope):
        if path not in {'', '.', 'index.html'} and path.split('/', 1)[0] not in {'assets', 'courses'}:
            raise HTTPException(404)
        if path not in {'', '.'} and any(part.startswith('.') for part in path.split('/')):
            raise HTTPException(404)
        response = await super().get_response(path, scope)
        if self.session_factory and path.startswith('courses/'):
            override = await run_in_threadpool(self.override, path, response)
            if override:return override
        return response
