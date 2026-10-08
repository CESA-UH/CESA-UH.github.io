"""Explainable indicators from questions, not grades or inferred mastery."""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.models import ChatMessage, Resource, Topic, ChatTopicSelection, ChatThreadMessage
from app.services.retrieval import tokens, normalize

LABELS = {"concept": "درک مفهوم", "practice": "حل تمرین", "prerequisite": "پیش‌نیاز", "followup": "نیاز به توضیح بیشتر", "general": "پرسش عمومی"}


def chat_analysis(db, course_id, student_id):
    messages = db.scalars(select(ChatMessage).where(ChatMessage.course_id == course_id, ChatMessage.student_id == student_id).order_by(ChatMessage.id)).all()
    questions = [m for m in messages if m.role == "user"]
    topics = {t.id: t for t in db.scalars(select(Topic).where(Topic.course_id == course_id))}
    resources = {r.id: r.topic_id for r in db.scalars(select(Resource).where(Resource.course_id == course_id))}
    topic_terms = {tid: set(tokens(t.name + " " + (t.description or ""))) - {"جستجوی", "یادگیری", "مسائل"} for tid, t in topics.items()}
    term_frequency = Counter(term for terms in topic_terms.values() for term in terms)
    topic_terms = {tid: {term for term in terms if term_frequency[term] == 1} for tid, terms in topic_terms.items()}
    selections = dict(db.execute(select(ChatTopicSelection.message_id, ChatTopicSelection.topic_id)
        .join(ChatMessage, ChatMessage.id == ChatTopicSelection.message_id)
        .where(ChatMessage.course_id == course_id, ChatMessage.student_id == student_id)).all())
    thread_ids = dict(db.execute(select(ChatThreadMessage.message_id, ChatThreadMessage.thread_id)
        .join(ChatMessage, ChatMessage.id == ChatThreadMessage.message_id)
        .where(ChatMessage.course_id == course_id, ChatMessage.student_id == student_id)).all())
    replies, pending = {}, {}
    for message in messages:
        thread = thread_ids.get(message.id, -1)
        if message.role == 'user':
            pending[thread] = message.id
        elif message.role == 'assistant' and thread in pending:
            replies[pending.pop(thread)] = message
    context, daily = {}, {}
    counts, problems, explicit = Counter(), Counter(), Counter()
    obstacles = 0
    topic_problems = {}
    no_evidence = 0
    dates = set()
    sessions = 0
    previous = None
    now = datetime.utcnow()
    recent = 0
    for i, m in enumerate(messages):
        if m.role != "user":
            continue
        dates.add(m.created_at.date().isoformat())
        if previous is None or (m.created_at - previous).total_seconds() > 1800:
            sessions += 1
        previous = m.created_at
        recent += m.created_at >= now - timedelta(days=7)
        text = normalize(m.content)
        category = "prerequisite" if re.search(r"پیش نیاز|پایه|از اول", text) else "practice" if re.search(r"تمرین|حل\s+(?:کن|کرد|کردن|مسئله|مساله|سؤال|سوال)|محاسبه|جواب|\bکد\b", text) else "followup" if re.search(r"نفهم|نمی\s?فهم|متوجه نشد|بیشتر|دوباره|اشتباه|\bگیر(?:\s*کرد|\s*افت|\b)", text) else "concept" if re.search(r"چیست|چرا|چطور|توضیح|مفهوم|تفاوت", text) else "general"
        problems[category] += 1
        signal_text = re.sub(r"مشکل(?:ی)?\s*(?:ندار\S*|نیست\S*|حل\s+شد\S*)|اشتباه\s+نکرد\S*|گیر\s+نیست\S*", "", text)
        stuck = bool(re.search(r"نفهم|نمی\s?فهم|نمی\s?تون|نمی\s?توان|متوجه نشد|اشتباه|\bگیر(?:\s*کرد|\s*افت|\b)|مشکل", signal_text))
        obstacles += stuck
        reply = replies.get(m.id)
        matched = set()
        if reply:
            no_evidence += reply.mode in {"no_evidence", "general_llm"}
            cited = {int(n) for n in re.findall(r"\[(\d+)\]", reply.content)}
            for number, citation in enumerate(reply.citations or [], 1):
                if number not in cited:
                    continue
                topic_id = resources.get(citation.get("resource_id"))
                if topic_id in topics:
                    matched.add(topic_id)
        query_tokens = set(tokens(text))
        for topic_id, topic in topics.items():
            meaningful = topic_terms[topic_id]
            if (meaningful and meaningful & query_tokens) or normalize(topic.name) in text:
                matched.add(topic_id)
        selected = selections.get(m.id)
        if selected in topics:
            matched = {selected}
        thread = thread_ids.get(m.id, -1)
        previous_context = context.get(thread)
        if not matched and previous_context and (stuck or category == 'followup') and (m.created_at - previous_context[1]).total_seconds() <= 1800:
            matched = set(previous_context[0])
        if matched:
            context[thread] = (matched, m.created_at)
        day = m.created_at.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Asia/Tehran')).date().isoformat()
        for topic_id in matched:
            point = daily.setdefault(topic_id, {}).setdefault(day, {'date': day, 'questions': 0, 'obstacles': 0})
            point['questions'] += 1
            point['obstacles'] += int(stuck)
            counts[topic_id] += 1
            topic_problems.setdefault(topic_id, Counter())[category] += 1
            if stuck:
                explicit[topic_id] += 1
    signals = []
    for topic_id, count in counts.most_common():
        category = topic_problems[topic_id].most_common(1)[0][0]
        needs = explicit[topic_id] > 0 or topic_problems[topic_id]["followup"] >= 2
        signals.append({"topic_id": topic_id, "name": topics[topic_id].name, "question_count": count,
                        "difficulty": LABELS[category], "reported_obstacles": explicit[topic_id], "needs_attention": needs,
                        "daily": sorted(daily.get(topic_id, {}).values(), key=lambda p: p["date"]),
                        "reason": "بیان مستقیم مشکل در چت" if explicit[topic_id] else "درخواست مکرر توضیح" if needs else "مبحث مورد پرسش؛ به‌تنهایی نشانهٔ ضعف نیست"})
    attention = obstacles > 0 or any(s["needs_attention"] for s in signals)
    return {"basis": "chat_indicators", "question_count": len(questions), "questions_week": recent,
            "reported_obstacles": obstacles, "active_days": len(dates), "sessions": sessions, "no_evidence_count": no_evidence,
            "last_active_at": questions[-1].created_at.isoformat() + "Z" if questions else None,
            "difficulty_counts": {LABELS[k]: v for k, v in problems.items()}, "topics": signals,
            "needs_attention": attention,
            "learning_status": "نیازمند گفت‌وگوی استاد" if attention else "در حال تمرین و پرسش" if questions else "بدون فعالیت در چت",
            "explanation": "تحلیل واژگانی پرسش‌ها و منابع پاسخ است؛ تعداد سؤال یا استفادهٔ زیاد، نشانهٔ ضعف یا تسلط قطعی نیست. نشست‌ها با فاصلهٔ بیش از ۳۰ دقیقه جدا می‌شوند."}
