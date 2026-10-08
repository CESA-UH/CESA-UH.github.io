from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import FileResponse
from pathlib import Path
import uuid
import re
import os
from app.core.config import BACKEND_DIR, settings
from app.services.site_import import ingest
from app.models import SiteFile, Topic, SiteTopic, ResourceOrigin, TopicReading
from pydantic import Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import current_user, bearer
from app.api import course_access
from app.models import User, SiteDocument, SiteDocumentRevision
from app.schemas import Input
from app.services.permissions import can_edit_course
from app.services.site_documents import document_source, render_document, course_source
from app.models import Course
from app.services import site_file_storage

router = APIRouter(prefix='/api/site-courses')


def optional_user(credentials=Depends(bearer), db: Session=Depends(get_db)):
    return current_user(credentials, db) if credentials else None


class EditDocument(Input):
    path: str = Field(min_length=1, max_length=500)
    markdown: str = Field(max_length=200000)
    expected_revision: int = Field(ge=0)
    source_digest: str = Field(min_length=64, max_length=64)


@router.get('/{key}/document')
def read_document(key: str, path: str = Query('index.md', max_length=500), user=Depends(optional_user), db:Session=Depends(get_db)):
    mapping, source, digest = document_source(db, key, path)
    doc = db.get(SiteDocument, (key, path))
    editable = bool(user and can_edit_course(db, user, db.get(Course, mapping.course_id)))
    return {'path':path, 'revision':doc.revision if doc else 0, 'source_digest':digest, 'can_edit':editable,
            'html':render_document(doc.markdown,path) if doc else None,
            'markdown':(doc.markdown if doc else source) if editable else None}


@router.put('/{key}/document')
def edit_document(key: str, data: EditDocument, user:User=Depends(current_user), db:Session=Depends(get_db)):
    mapping, source, digest = document_source(db, key, data.path)
    course_access(db, user, mapping.course_id, teacher_only=True)
    current = db.get(SiteDocument, (key, data.path))
    revision = current.revision if current else 0
    if revision != data.expected_revision or (revision == 0 and digest != data.source_digest):
        raise HTTPException(409, 'نسخهٔ صفحه تغییر کرده است؛ آخرین نسخه را دریافت کنید. متن شما در ویرایشگر حفظ شده است.')
    # Keep original source as revision 0, then every edit as an immutable revision.
    try:
        if not current:
            db.add(SiteDocumentRevision(site_key=key,path=data.path,revision=0,markdown=source,edited_by=user.id))
            db.add(SiteDocument(site_key=key,path=data.path,revision=1,markdown=data.markdown,edited_by=user.id))
        else:
            result=db.execute(update(SiteDocument).where(SiteDocument.site_key==key,SiteDocument.path==data.path,
                SiteDocument.revision==revision).values(markdown=data.markdown,revision=revision+1,edited_by=user.id,updated_at=datetime.utcnow()))
            if result.rowcount != 1:
                db.rollback()
                raise HTTPException(409, 'ویرایش هم‌زمان انجام شده است؛ آخرین نسخه را دریافت کنید.')
        db.add(SiteDocumentRevision(site_key=key,path=data.path,revision=revision+1,markdown=data.markdown,edited_by=user.id))
        if data.path == 'index.md':
            sync_page_topics(db, key, mapping.course_id, data.markdown)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'ویرایش هم‌زمان انجام شده است؛ آخرین نسخه را دریافت کنید.')
    return {'revision':revision+1,'html':render_document(data.markdown,data.path),'path':data.path}


@router.get('/{key}/document/history')
def history(key:str,path:str=Query('index.md',max_length=500),user:User=Depends(current_user),db:Session=Depends(get_db)):
    mapping, _, _ = document_source(db,key,path)
    course_access(db,user,mapping.course_id,teacher_only=True)
    rows=db.execute(select(SiteDocumentRevision.revision,SiteDocumentRevision.created_at,User.first_name,User.last_name)
        .join(User, User.id==SiteDocumentRevision.edited_by).where(SiteDocumentRevision.site_key==key,
        SiteDocumentRevision.path==path).order_by(SiteDocumentRevision.revision.desc()).limit(50)).all()
    return [{'revision':r,'at':at.isoformat()+'Z','editor':first+' '+last} for r,at,first,last in rows]


@router.get('/{key}/document/versions/{revision}')
def version(key:str,revision:int,path:str=Query('index.md',max_length=500),user:User=Depends(current_user),db:Session=Depends(get_db)):
    mapping, _, _ = document_source(db,key,path)
    course_access(db,user,mapping.course_id,teacher_only=True)
    row=db.scalar(select(SiteDocumentRevision).where(SiteDocumentRevision.site_key==key,
        SiteDocumentRevision.path==path,SiteDocumentRevision.revision==revision))
    if not row:raise HTTPException(404,'نسخه پیدا نشد.')
    return {'revision':revision,'markdown':row.markdown}


def sync_page_topics(db, key, course_id, text):
    from app.services.site_import import sessions
    from urllib.parse import urlparse, unquote
    rows=sessions(text)
    for row in rows:
        row['number']=str(int(row['number'])).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
    if len({r['number'] for r in rows}) != len(rows):
        raise HTTPException(422,'شمارهٔ جلسه‌ها نباید تکراری باشد.')
    if any(len(r['number'])>20 or len(r['name'])>255 for r in rows):
        raise HTTPException(422,'شماره یا عنوان جلسه بیش از حد طولانی است.')
    for row in rows:
        ref=db.get(SiteTopic,(key,row['number']))
        description='جلسهٔ '+row['number']+(' • مطالعه: '+row['reading'] if row['reading'] else '')
        topic=db.get(Topic,ref.topic_id) if ref else None
        if topic:
            topic.name,topic.description=row['name'],description
        else:
            topic=Topic(course_id=course_id,name=row['name'],description=description)
            db.add(topic);db.flush();db.add(SiteTopic(site_key=key,session=row['number'],topic_id=topic.id));db.flush()
        for _, link in row['links']:
            origin=db.scalar(select(ResourceOrigin).where(ResourceOrigin.course_id==course_id,ResourceOrigin.url==link))
            if not origin:
                uploaded=re.search(r'/files/([a-f0-9]{32})/download$',urlparse(link).path)
                file_row=db.get(SiteFile,uploaded[1]) if uploaded else None
                if file_row and file_row.site_key==key and file_row.resource_id:
                    origin=db.scalar(select(ResourceOrigin).where(ResourceOrigin.resource_id==file_row.resource_id))
            if not origin:
                relative=unquote(urlparse(link).path)
                if '/courses/' in relative:
                    relative=relative.split('/courses/',1)[1].split('/',1)[-1]
                origin=db.scalar(select(ResourceOrigin).where(ResourceOrigin.course_id==course_id,ResourceOrigin.source_key==relative))
            if origin and not db.get(TopicReading,(topic.id,origin.resource_id)):
                db.add(TopicReading(topic_id=topic.id,resource_id=origin.resource_id));db.flush()
    db.flush()


@router.post('/{key}/files', status_code=201)
def upload_file(key:str, request:Request, file:UploadFile=File(...), user:User=Depends(current_user), db:Session=Depends(get_db)):
    mapping,_=course_source(db,key)
    course=course_access(db,user,mapping.course_id,teacher_only=True)
    filename=Path((file.filename or '').replace('\\','/')).name[:255]
    suffix=Path(filename).suffix.lower()
    if suffix not in {'.pdf','.txt','.md','.png','.jpg','.jpeg'}:
        raise HTTPException(422,'فقط PDF، متن و تصویر PNG/JPG قابل بارگذاری است.')
    identifier=uuid.uuid4().hex
    folder=BACKEND_DIR/'data/site-files';folder.mkdir(parents=True,exist_ok=True)
    disk=folder/(identifier+suffix)
    size=0
    persisted=False
    try:
        with disk.open('xb') as handle:
            os.chmod(disk,0o600)
            while block:=file.file.read(65536):
                size+=len(block)
                if size>settings.MAX_UPLOAD_BYTES:raise HTTPException(413,'فایل بزرگ‌تر از حد مجاز است.')
                handle.write(block)
        if not size:raise HTTPException(422,'فایل خالی است.')
        url=str(request.base_url).rstrip('/')+'/api/site-courses/'+key+'/files/'+identifier+'/download'
        row=SiteFile(id=identifier,site_key=key,filename=filename,uploaded_by=user.id)
        warning=None
        if suffix in {'.pdf','.txt','.md'}:
            try:
                resource,_=ingest(db,course,user,disk,'uploaded/'+identifier+suffix,url,title=filename)
                resource.title=filename;resource.filename=filename
                row.resource_id=resource.id
            except ValueError as exc:
                warning=str(exc)
        persisted=site_file_storage.persist(key,identifier,disk)
        db.add(row);db.commit()
        if persisted:disk.unlink(missing_ok=True)
        return {'id':identifier,'filename':filename,'url':url,'resource_id':row.resource_id,'index_warning':warning}
    except Exception:
        db.rollback();disk.unlink(missing_ok=True)
        if persisted:site_file_storage.discard(key,identifier,suffix)
        raise


@router.get('/{key}/files/{identifier}/download')
def download_file(key:str,identifier:str,db:Session=Depends(get_db)):
    row=db.get(SiteFile,identifier)
    if not row or row.site_key!=key:raise HTTPException(404,'فایل پیدا نشد.')
    if site_file_storage.remote():return site_file_storage.download(row)
    disk=BACKEND_DIR/'data/site-files'/(row.id+Path(row.filename).suffix.lower())
    if not disk.is_file():raise HTTPException(404,'فایل در دسترس نیست.')
    # This is a published course attachment; never inline executable HTML.
    return FileResponse(disk,filename=row.filename,headers={'X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'"})
