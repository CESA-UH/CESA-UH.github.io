"""Separate time series for self-reports, assessed quiz results and chat signals."""
from sqlalchemy import select
from app.models import Topic, SelfReport, QuizAttempt, QuizQuestion, QuizAnswer


def learning_trends(db, course_id, student_id, chat):
    topics = db.scalars(select(Topic).where(Topic.course_id == course_id).order_by(Topic.id)).all()
    by_topic = {t.id: {'topic_id': t.id, 'name': t.name, 'self_reports': [], 'quizzes': [], 'chat': []} for t in topics}
    reports = db.scalars(select(SelfReport).join(Topic).where(
        Topic.course_id == course_id, SelfReport.student_id == student_id).order_by(SelfReport.created_at, SelfReport.id))
    for report in reports:
        by_topic[report.topic_id]['self_reports'].append({
            'at': report.created_at.isoformat() + 'Z', 'confidence': report.confidence,
            'percent': (report.confidence - 1) * 25, 'difficulty': report.difficulty,
            'study_minutes': report.study_minutes})
    rows = db.execute(select(QuizAnswer, QuizQuestion, QuizAttempt).join(QuizQuestion, QuizQuestion.id == QuizAnswer.question_id)
        .join(QuizAttempt, QuizAttempt.id == QuizAnswer.attempt_id).join(Topic, Topic.id == QuizQuestion.topic_id)
        .where(Topic.course_id == course_id, QuizAttempt.student_id == student_id, QuizAttempt.submitted_at.is_not(None))
        .order_by(QuizAttempt.submitted_at)).all()
    grouped = {}
    for answer, question, attempt in rows:
        item = grouped.setdefault((question.topic_id, attempt.id), {
            'attempt_id': attempt.id, 'quiz_id': attempt.quiz_id, 'at': attempt.submitted_at.isoformat() + 'Z',
            'points': 0, 'max_points': 0, 'pending': False})
        item['max_points'] += question.points
        item['points'] += answer.score or 0
        item['pending'] = item['pending'] or answer.score is None
    for (topic_id, _), item in grouped.items():
        item['percent'] = None if item['pending'] else round(item['points'] / item['max_points'] * 100, 1)
        by_topic[topic_id]['quizzes'].append(item)
    for signal in chat['topics']:
        if signal['topic_id'] in by_topic:
            by_topic[signal['topic_id']]['chat'] = signal.get('daily', [])
    for item in by_topic.values():
        values = item['self_reports']
        item['confidence_change'] = values[-1]['confidence'] - values[0]['confidence'] if len(values) >= 2 else None
        graded = [p for p in item['quizzes'] if p['percent'] is not None]
        item['quiz_change'] = round(graded[-1]['percent'] - graded[0]['percent'], 1) if len(graded) >= 2 else None
    return list(by_topic.values())
