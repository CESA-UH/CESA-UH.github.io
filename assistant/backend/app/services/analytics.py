from datetime import datetime, timedelta
from sqlalchemy import select
from app.models import SelfReport, Topic
from app.services.chat_analytics import chat_analysis
from app.services.learning_trends import learning_trends
from app.services.quiz_grading import expire_course_attempts

DIFFICULTIES = {"none": "بدون مشکل", "concept": "درک مفهوم", "practice": "حل تمرین", "prerequisite": "پیش‌نیاز", "time": "مدیریت زمان"}


def learner_context(db, course_id, student_id, topic_id=None):
    """Latest topic reports only; omit identity, private notes and study times."""
    statement = select(SelfReport, Topic).join(Topic).where(
        Topic.course_id == course_id, SelfReport.student_id == student_id,
    )
    if topic_id is not None:
        statement = statement.where(Topic.id == topic_id)
    rows = db.execute(statement.order_by(SelfReport.created_at.desc(), SelfReport.id.desc())).all()
    latest = {}
    for report, topic in rows:
        if topic.id not in latest:
            latest[topic.id] = {
                "topic": topic.name, "self_reported_confidence": report.confidence,
                "confidence_scale": "1-5", "difficulty": report.difficulty,
                "reported_at": report.created_at.isoformat() + "Z",
            }
        if len(latest) == 6:
            break
    return list(latest.values())


def report_dict(r, topic):
    return {"id": r.id, "topic_id": r.topic_id, "topic": topic.name, "confidence": r.confidence,
            "difficulty": r.difficulty, "difficulty_label": DIFFICULTIES[r.difficulty],
            "study_minutes": r.study_minutes, "note": r.note, "created_at": r.created_at.isoformat() + "Z"}


def dashboard(db, course_id, student_id):
    expire_course_attempts(db, course_id, student_id)
    topics = db.scalars(select(Topic).where(Topic.course_id == course_id).order_by(Topic.id)).all()
    rows = db.execute(select(SelfReport, Topic).join(Topic).where(Topic.course_id == course_id, SelfReport.student_id == student_id).order_by(SelfReport.created_at.desc(), SelfReport.id.desc())).all()
    latest = {}
    for r, _ in rows:
        latest.setdefault(r.topic_id, r)
    skills, recommendations = [], []
    now = datetime.utcnow()
    for topic in topics:
        r = latest.get(topic.id)
        percent = round((r.confidence - 1) * 25) if r else None
        weak = bool(r and (r.confidence <= 2 or r.difficulty != "none"))
        skills.append({"topic_id": topic.id, "name": topic.name, "confidence_percent": percent,
                       "confidence": r.confidence if r else None, "needs_attention": weak,
                       "difficulty": DIFFICULTIES[r.difficulty] if r else "هنوز گزارشی ثبت نشده",
                       "updated_at": r.created_at.isoformat() + "Z" if r else None})
    trend = []
    for days in reversed(range(7)):
        day = (now - timedelta(days=days)).date()
        daily = [r for r, _ in rows if r.created_at.date() == day]
        trend.append({"date": day.isoformat(), "study_minutes": sum(r.study_minutes for r in daily),
                      "confidence": round(sum(r.confidence for r in daily) / len(daily), 1) if daily else None, "reports": len(daily)})
    average = round(sum((r.confidence - 1) * 25 for r in latest.values()) / len(latest)) if latest else None
    chat = chat_analysis(db, course_id, student_id)
    trends = learning_trends(db, course_id, student_id, chat)
    from app.services.recommender import study_plan
    recommendations, strengths, statuses = study_plan(db, course_id, topics, latest, trends, chat)
    for skill in skills:
        skill['learning_status'] = statuses[skill['topic_id']]
        skill['needs_attention'] = statuses[skill['topic_id']] in {'needs_attention', 'review'}
    return {"chat_analysis": chat, "learning_trends": trends, "strengths": strengths, "basis": "self_report_quiz_chat", "average_confidence": average, "reported_topics": len(latest), "total_topics": len(topics),
            "weak_topics": sum(s["needs_attention"] for s in skills),
            "study_minutes_week": sum(t["study_minutes"] for t in trend), "skills": skills,
            "recommendations": recommendations, "trend": trend, "reports": [report_dict(r, t) for r, t in rows[:100]],
            "last_report_at": rows[0][0].created_at.isoformat() + "Z" if rows else None,
            "stale": not rows or rows[0][0].created_at < now - timedelta(days=7)}
