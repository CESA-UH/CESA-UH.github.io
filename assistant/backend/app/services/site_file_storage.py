"""Persist published course attachments in private Supabase Storage; keys never reach browsers."""
import mimetypes
from pathlib import Path
from urllib.parse import quote, urlparse
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.core.config import settings


def remote():
    return settings.SITE_FILE_STORAGE=='supabase'


def object_url(site_key, identifier, suffix):
    base=settings.SUPABASE_URL.rstrip('/')
    parsed=urlparse(base)
    if parsed.scheme!='https' or not parsed.netloc or parsed.query or parsed.fragment or not settings.SUPABASE_SERVICE_KEY:
        raise HTTPException(503,'ذخیره‌سازی ماندگار سامانه تنظیم نشده است.')
    key='courses/'+quote(site_key,safe='')+'/'+quote(identifier+suffix,safe='')
    return base+'/storage/v1/object/'+quote(settings.SUPABASE_STORAGE_BUCKET,safe='')+'/'+key


def headers():
    return {'Authorization':'Bearer '+settings.SUPABASE_SERVICE_KEY,'apikey':settings.SUPABASE_SERVICE_KEY}


def persist(site_key, identifier, disk):
    if not remote():return False
    try:
        with disk.open('rb') as file, httpx.Client(timeout=120) as client:
            response=client.post(object_url(site_key,identifier,disk.suffix.lower()),
                headers={**headers(),'Content-Type':mimetypes.guess_type(disk.name)[0] or 'application/octet-stream',
                         'Content-Length':str(disk.stat().st_size),'x-upsert':'false'},
                content=iter(lambda:file.read(65536),b''))
        if response.status_code not in {200,201}:
            raise HTTPException(502,'ذخیرهٔ فایل در فضای ماندگار انجام نشد؛ دوباره تلاش کنید.')
    except httpx.HTTPError:
        raise HTTPException(503,'اتصال به فضای فایل‌ها برقرار نشد؛ دوباره تلاش کنید.')
    return True


def discard(site_key, identifier, suffix):
    """Only remove our own uncommitted upload after its DB transaction fails."""
    if not remote():return
    try:
        with httpx.Client(timeout=15) as client:
            client.delete(object_url(site_key,identifier,suffix),headers=headers())
    except (httpx.HTTPError,HTTPException):
        pass


def download(row):
    client=httpx.Client(timeout=120)
    try:
        response=client.send(client.build_request('GET',object_url(row.site_key,row.id,Path(row.filename).suffix.lower()),headers=headers()),stream=True)
        if response.status_code!=200:
            response.close();client.close()
            raise HTTPException(404 if response.status_code==404 else 502,'فایل در دسترس نیست.')
    except httpx.HTTPError:
        client.close();raise HTTPException(503,'اتصال به فضای فایل‌ها برقرار نشد.')
    def chunks():
        try:yield from response.iter_bytes(65536)
        finally:response.close();client.close()
    result_headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.filename,safe=''),
                    'X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'"}
    if response.headers.get('Content-Length'):result_headers['Content-Length']=response.headers['Content-Length']
    return StreamingResponse(chunks(),media_type='application/octet-stream',headers=result_headers)
