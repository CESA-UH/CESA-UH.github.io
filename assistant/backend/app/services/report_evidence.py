"""Course-scoped, pseudonymous evidence snapshot. Never truncates student records."""
import hashlib
from datetime import datetime
import json
from sqlalchemy import select, and_
from app.models import (Topic, SelfReport, ReportForm, ReportFormEntry, ChatMessage, ChatThreadMessage,
                        ChatTopicSelection, Resource, Quiz, QuizAttempt, QuizQuestion, QuizAnswer,
                        StudentEvent, StudentSkill, Attempt, Assessment, Answer, Question)
from app.services.quiz_grading import expire_course_attempts


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def evidence_snapshot(db, course_id, student_id):
    expire_course_attempts(db, course_id, student_id)
    if db.get_bind().dialect.name == 'sqlite':
        connection = db.connection()
        if not connection.connection.driver_connection.in_transaction:
            connection.exec_driver_sql('BEGIN')
    topics = [{'id': t.id, 'name': t.name, 'description': t.description} for t in db.scalars(
        select(Topic).where(Topic.course_id == course_id).order_by(Topic.id))]
    evidence = []
    counts = dict(self_reports=0, form_entries=0, chat_messages=0, student_questions=0,
                  quiz_attempts=0, quiz_answers=0, events=0, legacy_attempts=0, legacy_answers=0, legacy_skill_estimates=0)
    for r, entry, form in db.execute(select(SelfReport, ReportFormEntry, ReportForm).select_from(SelfReport).join(Topic, Topic.id == SelfReport.topic_id).outerjoin(
            ReportFormEntry, ReportFormEntry.report_id == SelfReport.id).outerjoin(
            ReportForm, ReportForm.id == ReportFormEntry.form_id).where(
            Topic.course_id == course_id, SelfReport.student_id == student_id).order_by(SelfReport.created_at, SelfReport.id)):
        item = {'id': f'S{r.id}', 'kind': 'self_report', 'at': str(r.created_at), 'topic_id': r.topic_id,
                'confidence_out_of_5': r.confidence, 'difficulty': r.difficulty,
                'study_minutes_self_reported': r.study_minutes, 'note': r.note}
        if entry and form and form.course_id == course_id:
            item['form'] = {'title': form.title, 'fields': form.fields, 'answers': entry.answers}
            counts['form_entries'] += 1
        counts['self_reports'] += 1
        evidence.append(item)
    for m, thread_id, topic_id in db.execute(select(ChatMessage, ChatThreadMessage.thread_id, ChatTopicSelection.topic_id)
            .outerjoin(ChatThreadMessage, ChatThreadMessage.message_id == ChatMessage.id)
            .outerjoin(ChatTopicSelection, ChatTopicSelection.message_id == ChatMessage.id)
            .where(ChatMessage.course_id == course_id, ChatMessage.student_id == student_id)
            .order_by(ChatMessage.created_at, ChatMessage.id)):
        evidence.append({'id': f'C{m.id}', 'kind': 'chat', 'at': str(m.created_at), 'thread_id': thread_id,
                         'topic_id': topic_id, 'role': m.role, 'mode': m.mode, 'text': m.content,
                         'source_references': m.citations})
        counts['chat_messages'] += 1
        counts['student_questions'] += int(m.role == 'user')
    quizzes = db.scalars(select(Quiz).where(Quiz.course_id == course_id, Quiz.published.is_(True)).order_by(Quiz.id)).all()
    for quiz in quizzes:
        attempt = db.scalar(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz.id, QuizAttempt.student_id == student_id))
        evidence.append({'id': f'Q{quiz.id}', 'kind': 'quiz_participation', 'at': str(quiz.starts_at),
                         'title': quiz.title, 'starts_at': str(quiz.starts_at), 'ends_at': str(quiz.ends_at),
                         'attempt_id': attempt.id if attempt else None,
                         'submitted_at': str(attempt.submitted_at) if attempt and attempt.submitted_at else None,
                         'deadline': str(attempt.deadline) if attempt else None,
                         'expired': attempt.expired if attempt else False})
        if not attempt:
            continue
        counts['quiz_attempts'] += 1
        for q, a in db.execute(select(QuizQuestion, QuizAnswer).select_from(QuizQuestion).join(Topic).outerjoin(
                QuizAnswer, and_(QuizAnswer.question_id == QuizQuestion.id, QuizAnswer.attempt_id == attempt.id)).where(
                QuizQuestion.quiz_id == quiz.id, Topic.course_id == course_id).order_by(QuizQuestion.position)):
            evidence.append({'id': f'A{attempt.id}T{q.id}', 'kind': 'quiz_answer', 'at': str(attempt.submitted_at or attempt.started_at),
                             'topic_id': q.topic_id, 'quiz_title': quiz.title, 'question': q.text,
                             'options': q.options, 'correct_choice': q.correct_choice if attempt.submitted_at else None,
                             'kind_of_question': q.kind, 'max_points': q.points,
                             'answer': a.value if a else '', 'score': a.score if a and attempt.submitted_at else None,
                             'feedback': a.feedback if a else '', 'submitted': bool(attempt.submitted_at),
                             'pending_grading': bool(attempt.submitted_at and a and a.score is None)})
            counts['quiz_answers'] += int(a is not None)
    for e in db.scalars(select(StudentEvent).where(StudentEvent.course_id == course_id,
            StudentEvent.student_id == student_id).order_by(StudentEvent.timestamp, StudentEvent.id)):
        evidence.append({'id': f'E{e.id}', 'kind': 'event', 'at': str(e.timestamp),
                         'topic_id': e.topic_id, 'event': e.event_type.value, 'metadata': e.event_metadata})
        counts['events'] += 1
    for a, assessment in db.execute(select(Attempt, Assessment).join(Assessment).where(
            Assessment.course_id == course_id, Attempt.student_id == student_id).order_by(Attempt.started_at)):
        evidence.append({'id': f'L{a.id}', 'kind': 'legacy_assessment', 'at': str(a.started_at),
                         'title': assessment.title, 'completed_at': str(a.completed_at) if a.completed_at else None, 'score': a.score})
        counts['legacy_attempts'] += 1
        for ans, q in db.execute(select(Answer, Question).select_from(Answer).join(Question).join(Topic).where(Answer.attempt_id == a.id, Topic.course_id == course_id)):
            evidence.append({'id': f'LA{ans.id}', 'kind': 'legacy_answer', 'at': str(ans.answered_at),
                             'topic_id': q.topic_id, 'question': q.text, 'answer': ans.answer,
                             'is_correct': ans.is_correct, 'time_spent': ans.time_spent, 'attempt_number': ans.attempt_number})
            counts['legacy_answers'] += 1
    for skill in db.scalars(select(StudentSkill).join(Topic).where(Topic.course_id == course_id, StudentSkill.student_id == student_id)):
        evidence.append({'id': f'K{skill.id}', 'kind': 'legacy_skill_estimate', 'topic_id': skill.topic_id,
                         'at': str(skill.last_updated), 'legacy_mastery_estimate': skill.mastery,
                         'legacy_confidence_estimate': skill.confidence,
                         'note': 'برآورد خودکار قدیمی سیستم؛ نمره یا مدرک مستقیم تسلط نیست.'})
        counts['legacy_skill_estimates'] += 1
    evidence.sort(key=lambda e: (e['at'], e['id']))
    attach_chat_topics(evidence, topics)
    metrics = {}
    for t in topics:
        reports = [e for e in evidence if e['kind'] == 'self_report' and e.get('topic_id') == t['id']]
        graded = [e for e in evidence if e['kind'] == 'quiz_answer' and e.get('topic_id') == t['id'] and e['submitted'] and e['score'] is not None]
        pending = [e for e in evidence if e['kind'] == 'quiz_answer' and e.get('topic_id') == t['id'] and e['pending_grading']]
        metrics[str(t['id'])] = {'self_report_count': len(reports),
            'first_confidence': reports[0]['confidence_out_of_5'] if reports else None,
            'last_confidence': reports[-1]['confidence_out_of_5'] if reports else None,
            'graded_question_count': len(graded), 'graded_points': sum(e['score'] for e in graded),
            'graded_max_points': sum(e['max_points'] for e in graded), 'pending_grading_count': len(pending),
            'graded_evidence_ids': [e['id'] for e in graded], 'self_report_ids': [e['id'] for e in reports]}
    resources = [{'id': r.id, 'topic_id': r.topic_id, 'title': r.title, 'pages': r.page_count} for r in db.scalars(
        select(Resource).where(Resource.course_id == course_id).order_by(Resource.id))]
    result = {'student_alias': f'student-{student_id}', 'topics': topics, 'resources': resources,
              'counts': counts, 'topic_metrics': metrics, 'evidence': evidence}
    result['fingerprint'] = hashlib.sha256(dump(result).encode()).hexdigest()
    return result


def evidence_batches(snapshot, limit=14000):
    """Split even single oversized records; preserve all text and evidence IDs."""
    batch, size = [], 0
    for record in snapshot['evidence']:
        encoded = dump(record)
        parts = [record] if len(encoded) <= limit else [
            {'id': record['id'], 'kind': record['kind'], 'topic_id': record.get('topic_id'),
             'part': i // (limit - 2000) + 1, 'parts': (len(encoded) + limit - 2001) // (limit - 2000),
             'record_json_fragment': encoded[i:i + limit - 2000]}
            for i in range(0, len(encoded), limit - 2000)]
        for part in parts:
            length = len(dump(part))
            if batch and size + length > limit:
                yield batch
                batch, size = [], 0
            batch.append(part)
            size += length
    if batch:
        yield batch


def attach_chat_topics(records, topics):
    previous = {}
    for record in records:
        if record['kind'] != 'chat':
            continue
        if record.get('topic_id') is None:
            matched = [t['id'] for t in topics if t['name'] in record.get('text', '')]
            if len(matched) == 1:
                record['topic_id'], record['topic_origin'] = matched[0], 'explicit_topic_name'
        thread = record.get('thread_id')
        at = datetime.fromisoformat(record['at'].replace('Z', '+00:00'))
        if record.get('role') == 'user' and thread is not None:
            if record.get('topic_id') is None and thread in previous:
                topic_id, last = previous[thread]
                if 0 <= (at-last).total_seconds() <= 1800:
                    record['topic_id'], record['topic_origin'] = topic_id, 'same_thread_context'
            if record.get('topic_id') is not None:
                previous[thread] = (record['topic_id'], at)
