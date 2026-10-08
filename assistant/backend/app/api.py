import secrets
import json
import re
from pathlib import Path
from fastapi.responses import StreamingResponse
from fastapi import Request, APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.core.security import current_user, hash_password, token_for, verify_password
from app.models import ChatTopicSelection, User, UserRole, Course, Topic, Enrollment, CourseInvite, SelfReport, Resource, ResourceChunk, ChatMessage, ChatThread, ChatThreadMessage
from app.services.permissions import can_edit_course, course_role
from app.models import CourseAssistant, SiteCourse, TopicReading, ResourceOrigin
from app.schemas import Register, Login, CourseInput, TopicInput, JoinInput, ReportInput, ChatInput, ThreadInput
from app.services.analytics import dashboard, report_dict, learner_context
from app.services.retrieval import iter_pages, chunk_page, retrieve
from app.services.search_index import index_chunks
from app.services.okf import course_bundle
from app.services.tutor import answer, stream_answer

router = APIRouter(prefix="/api")


def user_dict(user):
    return {"id": user.id, "email": user.email, "first_name": user.first_name, "last_name": user.last_name, "role": user.role.value}


def role_required(user, role):
    if user.role.value != role:
        raise HTTPException(403, "این عملیات برای نقش شما مجاز نیست.")


def course_access(db, user, course_id, teacher_only=False):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(404, "درس پیدا نشد.")
    if can_edit_course(db, user, course):
        return course
    if not teacher_only and user.role == UserRole.STUDENT and db.scalar(select(Enrollment.id).where(Enrollment.course_id == course_id, Enrollment.student_id == user.id)):
        return course
    raise HTTPException(403, "به این درس دسترسی ندارید.")


def topic_access(db, course_id, topic_id):
    topic = db.get(Topic, topic_id)
    if not topic or topic.course_id != course_id:
        raise HTTPException(404, "مبحث در این درس پیدا نشد.")
    return topic


def course_dict(db, course, user):
    teacher = db.get(User, course.teacher_id)
    invite = db.get(CourseInvite, course.id)
    return {"id": course.id, "name": course.name, "description": course.description,
            "teacher": teacher.first_name + " " + teacher.last_name,
            "join_code": invite.code if invite and can_edit_course(db, user, course) else None,
            "can_edit": can_edit_course(db, user, course), "course_role": course_role(db, user, course),
            "can_manage_assistants": user.role == UserRole.ADMIN,
            "site_key": (db.scalar(select(SiteCourse.key).where(SiteCourse.course_id == course.id))),
            "site_url": (db.scalar(select(SiteCourse.url).where(SiteCourse.course_id == course.id))),
            "student_count": db.scalar(select(func.count()).select_from(Enrollment).where(Enrollment.course_id == course.id)),
            "topic_count": db.scalar(select(func.count()).select_from(Topic).where(Topic.course_id == course.id))}


@router.post("/auth/register", status_code=201)
def register(data: Register, db: Session = Depends(get_db)):
    user = User(email=data.email, password_hash=hash_password(data.password), first_name=data.first_name, last_name=data.last_name, role=UserRole(data.role))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "این ایمیل قبلاً ثبت شده است.")
    return {"access_token": token_for(user), "token_type": "bearer", "user": user_dict(user)}


@router.post("/auth/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "ایمیل یا رمز عبور صحیح نیست.")
    return {"access_token": token_for(user), "token_type": "bearer", "user": user_dict(user)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_dict(user)


@router.get("/status")
def status(user: User = Depends(current_user)):
    return {"tutor_mode": "llm" if settings.llm_key else "retrieval", "model": settings.llm_model if settings.llm_key else None,
            "models": settings.llm_models if settings.llm_key else [],
            "max_upload_bytes": settings.MAX_UPLOAD_BYTES, "max_resource_pages": settings.MAX_RESOURCE_PAGES}


@router.get("/courses")
def courses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    statement = select(Course).order_by(Course.id.desc())
    if user.role != UserRole.ADMIN:
        owned = (Course.teacher_id == user.id) if user.role == UserRole.TEACHER else False
        enrolled = select(Enrollment.course_id).where(Enrollment.student_id == user.id)
        assisted = select(CourseAssistant.course_id).where(CourseAssistant.student_id == user.id)
        statement = statement.where(or_(owned, Course.id.in_(enrolled), Course.id.in_(assisted)))
    return [course_dict(db, c, user) for c in db.scalars(statement).all()]


@router.post("/courses", status_code=201)
def create_course(data: CourseInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role not in {UserRole.TEACHER, UserRole.ADMIN}:
        raise HTTPException(403, "اجازهٔ ساخت درس ندارید.")
    course = Course(name=data.name, description=data.description, teacher_id=user.id)
    db.add(course)
    db.flush()
    db.add(CourseInvite(course_id=course.id, code=secrets.token_hex(5).upper()))
    db.commit()
    return course_dict(db, course, user)


@router.post("/courses/join")
def join_course(data: JoinInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    invite = db.scalar(select(CourseInvite).where(CourseInvite.code == data.code.upper()))
    if not invite:
        raise HTTPException(404, "کد درس معتبر نیست.")
    existing = db.scalar(select(Enrollment).where(Enrollment.course_id == invite.course_id, Enrollment.student_id == user.id))
    if not existing:
        db.add(Enrollment(course_id=invite.course_id, student_id=user.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return course_dict(db, db.get(Course, invite.course_id), user)


@router.get("/courses/{course_id}/topics")
def topics(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id)
    return [{"id": t.id, "name": t.name, "description": t.description} for t in db.scalars(select(Topic).where(Topic.course_id == course_id).order_by(Topic.id))]


@router.post("/courses/{course_id}/topics", status_code=201)
def create_topic(course_id: int, data: TopicInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    topic = Topic(course_id=course_id, name=data.name, description=data.description)
    db.add(topic)
    db.commit()
    return {"id": topic.id, "name": topic.name, "description": topic.description}


@router.post("/courses/{course_id}/reports", status_code=201)
def create_report(course_id: int, data: ReportInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    topic = topic_access(db, course_id, data.topic_id)
    report = SelfReport(student_id=user.id, **data.model_dump())
    db.add(report)
    db.commit()
    return report_dict(report, topic)


@router.get("/courses/{course_id}/dashboard")
def student_dashboard(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    return dashboard(db, course_id, user.id)


@router.get("/courses/{course_id}/students")
def teacher_dashboard(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    students = db.scalars(select(User).join(Enrollment).where(Enrollment.course_id == course_id).order_by(User.first_name, User.id)).all()
    result = []
    difficulty_counts = {}
    topic_counts = {}
    for student in students:
        data = dashboard(db, course_id, student.id)
        for skill in data["skills"]:
            if skill["needs_attention"]:
                topic_counts[skill["name"]] = topic_counts.get(skill["name"], 0) + 1
                difficulty_counts[skill["difficulty"]] = difficulty_counts.get(skill["difficulty"], 0) + 1
        result.append({"student": user_dict(student), "average_confidence": data["average_confidence"],
                       "weak_topics": data["weak_topics"], "reported_topics": data["reported_topics"],
                       "study_minutes_week": data["study_minutes_week"], "last_report_at": data["last_report_at"],
                       "chat_analysis": data["chat_analysis"],
                       "needs_attention": data["weak_topics"] > 0 or data["stale"] or data["chat_analysis"]["needs_attention"],
                       "reason": "چالش در گفت‌وگو" if data["chat_analysis"]["needs_attention"] else "بدون خوداظهاری" if not data["last_report_at"] else "گزارش قدیمی" if data["stale"] else "نیاز به حمایت" if data["weak_topics"] else "در مسیر یادگیری"})
    return {"students": result, "attention_count": sum(s["needs_attention"] for s in result),
            "topic_difficulties": [{"name": n, "count": c} for n, c in sorted(topic_counts.items(), key=lambda x: -x[1])],
            "difficulty_counts": difficulty_counts}


@router.get("/courses/{course_id}/students/{student_id}")
def student_detail(course_id: int, student_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    if not db.scalar(select(Enrollment.id).where(Enrollment.course_id == course_id, Enrollment.student_id == student_id)):
        raise HTTPException(404, "دانشجو عضو این درس نیست.")
    return {"student": user_dict(db.get(User, student_id)), **dashboard(db, course_id, student_id)}


@router.get("/courses/{course_id}/resources")
def resources(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id)
    rows = db.scalars(select(Resource).where(Resource.course_id == course_id).order_by(Resource.id.desc()))
    linked = {}
    for rid, tid in db.execute(select(TopicReading.resource_id, TopicReading.topic_id).join(Resource, Resource.id == TopicReading.resource_id).where(Resource.course_id == course_id)):
        linked.setdefault(rid, []).append(tid)
    origins = {o.resource_id: o.url for o in db.scalars(select(ResourceOrigin).where(ResourceOrigin.course_id == course_id))}
    return [{"id": r.id, "title": r.title, "filename": r.filename, "topic_id": r.topic_id, "page_count": r.page_count,
             "topic_ids": sorted(set(linked.get(r.id, []) + ([r.topic_id] if r.topic_id else []))), "original_url": origins.get(r.id),
             "created_at": r.created_at.isoformat() + "Z",
             "chunk_count": db.scalar(select(func.count()).select_from(ResourceChunk).where(ResourceChunk.resource_id == r.id)),
             "first_page": db.scalar(select(func.min(ResourceChunk.page)).where(ResourceChunk.resource_id == r.id))} for r in rows]


@router.post("/courses/{course_id}/resources", status_code=201)
def upload_resource(course_id: int, file: UploadFile = File(...), title: str = Form(..., min_length=1, max_length=255),
                    topic_id: int | None = Form(None), user: User = Depends(current_user), db: Session = Depends(get_db)):
    course_access(db, user, course_id, teacher_only=True)
    if topic_id is not None:
        topic_access(db, course_id, topic_id)
    filename = Path((file.filename or "").replace("\\", "/")).name[:255]
    if not title.strip():
        raise HTTPException(422, "عنوان منبع را وارد کنید.")
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"حداکثر اندازهٔ فایل {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} مگابایت است.")
    resource = Resource(course_id=course_id, topic_id=topic_id, title=title.strip(), filename=filename, uploaded_by=user.id, page_count=0)
    db.add(resource)
    db.flush()
    position = 0
    batch = []
    try:
        for page, text in iter_pages(filename, file.file):
            resource.page_count = page
            for chunk in chunk_page(text):
                row = ResourceChunk(resource_id=resource.id, page=page, position=position, text=chunk)
                db.add(row)
                batch.append(row)
                position += 1
                if len(batch) >= 100:
                    db.flush()
                    index_chunks(db, batch, resource.title)
                    batch.clear()
        if batch:
            db.flush()
            index_chunks(db, batch, resource.title)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc))
    db.commit()
    return {"id": resource.id, "title": resource.title, "page_count": resource.page_count, "chunk_count": position}


@router.get("/courses/{course_id}/knowledge/export")
def export_knowledge(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    course = course_access(db, user, course_id, teacher_only=True)
    bundle = course_bundle(db, course)
    def blocks():
        try:
            while block := bundle.read(64 * 1024):
                yield block
        finally:
            bundle.close()
    return StreamingResponse(blocks(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="course-{course_id}-okf.zip"',
        "Cache-Control": "no-store"})


@router.get("/resources/{resource_id}/pages/{page}")
def resource_page(resource_id: int, page: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(404, "منبع پیدا نشد.")
    course_access(db, user, resource.course_id)
    chunks = db.scalars(select(ResourceChunk).where(ResourceChunk.resource_id == resource_id, ResourceChunk.page == page).order_by(ResourceChunk.position)).all()
    if not chunks:
        raise HTTPException(404, "این صفحه متن استخراج‌شده ندارد.")
    origin = db.get(ResourceOrigin, resource_id)
    return {"title": resource.title, "page": page, "original_url": origin.url + "#page=" + str(page) if origin else None,
            "previous_page": db.scalar(select(func.max(ResourceChunk.page)).where(ResourceChunk.resource_id == resource_id, ResourceChunk.page < page)),
            "next_page": db.scalar(select(func.min(ResourceChunk.page)).where(ResourceChunk.resource_id == resource_id, ResourceChunk.page > page)),
            "chunks": [{"id": c.id, "text": c.text} for c in chunks]}


def course_context(db, course_id):
    course = db.get(Course, course_id)
    return {"course": course.name, "topics": list(db.scalars(select(Topic.name).where(Topic.course_id == course_id)))}


def message_dict(m):
    return {"id": m.id, "role": m.role, "content": m.content, "mode": m.mode, "citations": m.citations, "created_at": m.created_at.isoformat() + "Z"}


@router.get("/courses/{course_id}/chat")
def chat_history(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    messages = db.scalars(select(ChatMessage).where(ChatMessage.course_id == course_id, ChatMessage.student_id == user.id).order_by(ChatMessage.id.desc()).limit(100)).all()
    return [message_dict(m) for m in reversed(messages)]


@router.post("/courses/{course_id}/chat")
def chat(course_id: int, data: ChatInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    if data.topic_id:
        topic_access(db, course_id, data.topic_id)
    thread = thread_access(db, user, course_id, data.thread_id) if data.thread_id else None
    history = thread_messages(db, thread.id, limit=8) if thread else db.scalars(select(ChatMessage).where(ChatMessage.course_id == course_id, ChatMessage.student_id == user.id).order_by(ChatMessage.id.desc()).limit(8)).all()[::-1]
    # Recent student wording helps retrieve follow-up questions such as "این را بیشتر توضیح بده".
    query = data.message
    if len(data.message.split()) < 8 and re.search(r"(این|آن|همین|همان|بیشتر|ادامه|this|that|more)", data.message, re.IGNORECASE) and history:
        previous = next((m.content for m in reversed(history) if m.role == "user"), "")
        query += " " + previous
    sources = retrieve(db, course_id, query, data.topic_id)
    learner = learner_context(db, course_id, user.id, data.topic_id)
    text, mode, citations = answer(data.message, sources, history, learner, course_context=course_context(db, course_id))
    question = ChatMessage(student_id=user.id, course_id=course_id, role="user", content=data.message, mode=mode)
    db.add(question)
    reply = ChatMessage(student_id=user.id, course_id=course_id, role="assistant", content=text, mode=mode, citations=citations)
    db.add(reply)
    if data.topic_id:
        db.flush()
        db.add(ChatTopicSelection(message_id=question.id, topic_id=data.topic_id))
    if thread:
        db.flush()
        db.add_all([ChatThreadMessage(thread_id=thread.id, message_id=question.id), ChatThreadMessage(thread_id=thread.id, message_id=reply.id)])
    db.commit()
    return message_dict(reply)


def thread_access(db, user, course_id, thread_id):
    thread = db.get(ChatThread, thread_id)
    if not thread or thread.student_id != user.id or thread.course_id != course_id:
        raise HTTPException(404, "گفت‌وگو پیدا نشد.")
    return thread


def thread_messages(db, thread_id, limit=100):
    rows = db.scalars(select(ChatMessage).join(ChatThreadMessage).where(ChatThreadMessage.thread_id == thread_id).order_by(ChatMessage.id.desc()).limit(limit)).all()
    return rows[::-1]


def legacy_thread(db, user, course_id):
    rows = db.scalars(select(ChatMessage).outerjoin(ChatThreadMessage).where(
        ChatMessage.student_id == user.id, ChatMessage.course_id == course_id, ChatThreadMessage.message_id.is_(None),
    ).order_by(ChatMessage.id)).all()
    if rows:
        thread = ChatThread(student_id=user.id, course_id=course_id, title="گفت‌وگوهای قبلی", created_at=rows[0].created_at)
        db.add(thread)
        db.flush()
        for row in rows:
            db.add(ChatThreadMessage(message_id=row.id, thread_id=thread.id))
        db.commit()


@router.get("/courses/{course_id}/chat/threads")
def threads(course_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    legacy_thread(db, user, course_id)
    rows = db.scalars(select(ChatThread).where(ChatThread.course_id == course_id, ChatThread.student_id == user.id).order_by(ChatThread.id.desc())).all()
    return [{"id": t.id, "title": t.title, "created_at": t.created_at.isoformat() + "Z",
             "message_count": db.scalar(select(func.count()).select_from(ChatThreadMessage).where(ChatThreadMessage.thread_id == t.id))} for t in rows]


@router.post("/courses/{course_id}/chat/threads", status_code=201)
def create_thread(course_id: int, data: ThreadInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    thread = ChatThread(student_id=user.id, course_id=course_id, title=data.title)
    db.add(thread)
    db.commit()
    return {"id": thread.id, "title": thread.title}


@router.get("/courses/{course_id}/chat/threads/{thread_id}")
def get_thread(course_id: int, thread_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    thread_access(db, user, course_id, thread_id)
    return [message_dict(m) for m in thread_messages(db, thread_id, limit=500)]


@router.get("/courses/{course_id}/chat/threads/{thread_id}/export")
def export_thread(course_id: int, thread_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    thread = thread_access(db, user, course_id, thread_id)
    content = "# " + thread.title + "\n\n"
    for m in thread_messages(db, thread_id, limit=10000):
        content += "## " + ("دانشجو" if m.role == "user" else "دستیار") + "\n\n" + m.content + "\n\n"
        for i, citation in enumerate(m.citations or [], 1):
            content += f"[{i}] {citation['title']} — صفحهٔ {citation['page']}\n\n"
    from fastapi.responses import Response
    return Response(content, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="conversation.md"'})


@router.post("/courses/{course_id}/chat/stream")
def streamed_chat(course_id: int, data: ChatInput, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    role_required(user, "student")
    course_access(db, user, course_id)
    if data.topic_id:
        topic_access(db, course_id, data.topic_id)
    if data.thread_id:
        thread = thread_access(db, user, course_id, data.thread_id)
    else:
        thread = ChatThread(student_id=user.id, course_id=course_id, title=data.message[:80])
        db.add(thread)
        db.commit()
    history = thread_messages(db, thread.id, limit=8)
    query = data.message
    # Attempts can be long and omit the topic name; retain recent thread evidence.
    previous = [m.content for m in history if m.role == "user"][-3:]
    if previous:
        query += " " + " ".join(previous)
    last_reply = next((m for m in reversed(history) if m.role == "assistant"), None)
    if last_reply:
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", last_reply.content)}
        query += " " + " ".join(c["title"] for i, c in enumerate(last_reply.citations or [], 1) if i in cited)
    sources = retrieve(db, course_id, query, data.topic_id)
    learner = learner_context(db, course_id, user.id, data.topic_id)
    student_id, thread_id = user.id, thread.id

    async def events():
        def sse(data):
            return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"
        yield sse({"event": "start", "thread_id": thread_id, "mode": "general_llm" if not sources and settings.llm_key else "llm" if settings.llm_key else "retrieval" if sources else "no_evidence"})
        async for event in stream_answer(data.message, sources, history, learner, course_context=course_context(db, course_id)):
            if await request.is_disconnected():
                return
            if event["event"] == "complete":
                question = ChatMessage(student_id=student_id, course_id=course_id, role="user", content=data.message, mode=event["mode"])
                reply = ChatMessage(student_id=student_id, course_id=course_id, role="assistant", content=event["content"], mode=event["mode"], citations=event["citations"])
                db.add_all([question, reply])
                db.flush()
                if data.topic_id:
                    db.add(ChatTopicSelection(message_id=question.id, topic_id=data.topic_id))
                db.add_all([ChatThreadMessage(thread_id=thread_id, message_id=question.id), ChatThreadMessage(thread_id=thread_id, message_id=reply.id)])
                if thread.title == "گفت‌وگوی جدید":
                    thread.title = data.message[:80]
                db.commit()
                yield sse({"event": "done", "thread_id": thread_id, "reply": message_dict(reply), "model": event.get("model")})
            else:
                yield sse(event)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
