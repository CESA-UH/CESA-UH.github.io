from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import Base, engine
from sqlalchemy.orm import Session
from app.services.search_index import backfill
import app.models  # Register all models for table creation.
from app.api import router
from app.routes.teaching import router as teaching_router
from app.routes.learning_reports import router as reports_router
from app.services.report_worker import ReportWorker
from app.routes.course_staff import router as staff_router
from app.services.published_docs import PublishedDocs
from app.routes.site_documents import router as documents_router
from pathlib import Path

STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app):
    from app.services.cloud_bootstrap import prepare_database
    prepare_database(engine)
    Base.metadata.create_all(engine)
    from app.services.cloud_bootstrap import initialize_cloud
    initialize_cloud(engine)
    with Session(engine) as db:
        backfill(db)
        db.commit()
    worker = ReportWorker(engine, settings.REPORT_WORKER_CONCURRENCY) if settings.REPORT_WORKER_ENABLED else None
    if worker:
        worker.start()
    try:
        yield
    finally:
        if worker:
            worker.close()


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, debug=settings.DEBUG, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['https://cesa-uh.github.io'],
                   allow_methods=['GET','PUT','POST'], allow_headers=['Authorization','Content-Type'])
app.include_router(router)
app.include_router(teaching_router)
app.include_router(reports_router)
app.include_router(staff_router)
app.include_router(documents_router)
if settings.ECE_DOCS_PATH:
    app.mount("/docs-site", PublishedDocs(directory=settings.ECE_DOCS_PATH, html=True, session_factory=lambda: Session(engine)), name="course-docs")

app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def root():
    if settings.ECE_DOCS_PATH and (Path(settings.ECE_DOCS_PATH)/'index.html').is_file():
        html=(Path(settings.ECE_DOCS_PATH)/'index.html').read_text()
        # Preserve CESA's layout and resolve all relative assets/course links at its public mount.
        html=html.replace('<head>', '<head><base href="/docs-site/">', 1)
        return HTMLResponse(html)
    return FileResponse(STATIC / "index.html")


@app.get("/login", include_in_schema=False)
@app.get("/app", include_in_schema=False)
def application():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
