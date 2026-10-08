"""Produce an OKF v0.2 bundle from course sources, without generating facts."""
import json
import tempfile
from datetime import datetime, timezone
from zipfile import ZipFile, ZIP_DEFLATED
from sqlalchemy import select
from app.core.config import settings
from app.models import Topic, Resource, ResourceChunk


def document(kind, title, body, **metadata):
    # JSON values are valid YAML scalars/collections; quoting prevents user text
    # (colons, newlines, '---') from injecting frontmatter keys.
    fields = {'type': kind, 'title': title, **metadata}
    front = '\n'.join(f'{key}: {json.dumps(value, ensure_ascii=False)}' for key, value in fields.items())
    return f'---\n{front}\n---\n\n{body}\n'


def label(text):
    return str(text).replace('\\', '\\\\').replace('[', '\\[').replace(']', '\\]').replace('\n', ' ')


def course_bundle(db, course):
    """Return a spooled zip. Text chunks are fetched in batches, not all at once."""
    output = tempfile.SpooledTemporaryFile(max_size=2 * 1024 * 1024, mode='w+b')
    generated = {'by': f'hamdars/{settings.APP_VERSION}', 'at': datetime.now(timezone.utc).isoformat()}
    topics = db.scalars(select(Topic).where(Topic.course_id == course.id).order_by(Topic.id)).all()
    resources = db.scalars(select(Resource).where(Resource.course_id == course.id).order_by(Resource.id)).all()
    try:
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            archive.writestr('index.md', '---\nokf_version: "0.2"\n---\n\n# کتابخانهٔ درس\n\n'
                             '* [درس](course.md) - مشخصات درس\n'
                             '* [مباحث](topics/index.md) - مباحث تعریف‌شده توسط استاد\n'
                             '* [منابع](resources/index.md) - متن استخراج‌شده و ارجاع صفحه\n')
            archive.writestr('course.md', document('Course', course.name, course.description or '', generated=generated,
                                                 description='منابع و مباحث درس', course_id=course.id))
            archive.writestr('topics/index.md', '# مباحث\n\n' + '\n'.join(
                f'* [{label(t.name)}]({t.id}.md) - مبحث درس' for t in topics))
            for topic in topics:
                body = (topic.description or '') + '\n\n[درس](../course.md)\n\n' + '\n'.join(
                    f'* [{label(r.title)}](../resources/{r.id}/source.md)' for r in resources if r.topic_id == topic.id)
                archive.writestr(f'topics/{topic.id}.md', document('Learning Topic', topic.name, body, generated=generated))
            archive.writestr('resources/index.md', '# منابع درس\n\n' + '\n'.join(
                f'* [{label(r.title)}]({r.id}/source.md) - {r.page_count} صفحه' for r in resources))
            for resource in resources:
                base = f'resources/{resource.id}'
                body = '[درس](../../course.md)\n\n[بخش‌های منبع](index.md)'
                if resource.topic_id is not None:
                    body += f'\n\n[مبحث مرتبط](../../topics/{resource.topic_id}.md)'
                archive.writestr(f'{base}/source.md', document(
                    'Course Source', resource.title, body, generated=generated,
                    filename=resource.filename, page_count=resource.page_count,
                    description='متن استخراج‌شده از منبع استاد؛ فایل اصلی در بسته موجود نیست.'))
                links = []
                statement = select(ResourceChunk).where(ResourceChunk.resource_id == resource.id).order_by(ResourceChunk.position)
                for chunk in db.scalars(statement.execution_options(yield_per=100)):
                    name = f'chunk-{chunk.position:06d}.md'
                    title = f'{resource.title} · صفحهٔ {chunk.page} · بخش {chunk.position + 1}'
                    links.append(f'* [{label(title)}]({name}) - متن استخراج‌شده')
                    archive.writestr(f'{base}/{name}', document(
                        'Source Excerpt', title, '[منبع](source.md)\n\n## متن استخراج‌شده\n\n' + chunk.text,
                        generated=generated, page=chunk.page, position=chunk.position,
                        description=f'متن صفحهٔ {chunk.page}؛ خلاصه یا تأیید علمی تولید نشده است.',
                        sources=[{'resource': f'/resources/{resource.id}/source.md', 'title': resource.title}]))
                archive.writestr(f'{base}/index.md', '# بخش‌های منبع\n\n' + '\n'.join(links))
        output.seek(0)
        return output
    except BaseException:
        output.close()
        raise
