"""Personal study plans with separate evidence channels and actual source locations.

Chat obstacles are review signals, not a measured proficiency score. Only graded
quiz attempts contribute assessed results. No LLM invents book/page references.
"""
import re
import unicodedata
from sqlalchemy import select, or_
from app.models import Resource, ResourceChunk, ResourceOrigin, TopicReading
from app.services.retrieval import retrieve, citation

SEARCH_HINTS = {
    'تقسیم': 'divide conquer recurrence recursive base case merge sort',
    'بازگشت': 'recursion recursive base case recurrence',
    'بازگشتی': 'recursion recurrence master theorem induction',
    'حریصانه': 'greedy optimal substructure exchange argument',
    'استقرا': 'induction inductive hypothesis proof',
    'مجانبی': 'asymptotic complexity big O omega theta',
    'درجی': 'insertion sort time complexity',
    'ادغامی': 'merge sort merge recurrence',
    'آرایه': 'array indexing data structure',
    'پرسیپترون': 'perceptron activation weights learning',
    'Perceptron': 'perceptron activation weights learning',
    'BackPropagation': 'backpropagation gradient descent neural network',
    'جستجو': 'search heuristic A* graph',
}
ISSUE_PATTERNS = {
    'شرط توقف': [r'base\s+case', r'stopping\s+condition', r'termination', r'if[^\n]{0,35}n[^\n]{0,12}(?:==|=|≤|<=)\s*1'],
    'رابطه بازگشتی': [r'recurrence', r'recursion\s+tree', r'master\s+theorem'],
    'هیوریستیک': [r'heuristic', r'h\s*\(\s*n\s*\)'],
    'اثبات': [r'proof', r'induction', r'inductive'],
}
ACTIONS = {
    'concept': 'تعریف و یک مثال منبع را بخوان؛ سپس بدون نگاه به متن، مفهوم را با زبان خودت توضیح بده.',
    'practice': 'مثال حل‌شدهٔ منبع را مرحله‌به‌مرحله بازسازی کن و سپس یک مسئلهٔ مشابه را مستقل حل کن.',
    'prerequisite': 'تعریف‌ها و پیش‌نیازهای ذکرشده در این بخش را مرور کن؛ قسمت نامفهوم را برای حل‌تمرین درس مشخص کن.',
    'time': 'بخش پیشنهادی را در دو نوبت ۲۰ دقیقه‌ای بخوان و بعد خوداظهاری تازه ثبت کن.',
    'none': 'بخش پیشنهادی را مرور کن و یک تمرین از همین مبحث را بدون کمک حل کن.',
}


def reading_sources(db, course_id, topic, note=''):
    query = topic.name + ' ' + (topic.description or '') + ' ' + note
    query += ' ' + ' '.join(v for k, v in SEARCH_HINTS.items() if k.casefold() in query.casefold())
    patterns = [p for issue, items in ISSUE_PATTERNS.items() if issue in note for p in items]
    found = retrieve(db, course_id, query, topic.id, limit=12 if patterns else 4)
    def specificity(source):
        text = unicodedata.normalize('NFKC', source['excerpt']).lower()
        return sum(bool(re.search(pattern, text)) for pattern in patterns)
    if patterns:
        found.sort(key=specificity, reverse=True)
    match = 'text_match'
    if not found:
        # Explicitly distinguish a topic-linked starting point from a text match.
        rows = db.execute(select(ResourceChunk, Resource).join(Resource).where(
            Resource.course_id == course_id, or_(Resource.topic_id == topic.id, Resource.id.in_(select(TopicReading.resource_id).where(TopicReading.topic_id == topic.id))))
            .order_by(Resource.id, ResourceChunk.page, ResourceChunk.position).limit(2)).all()
        found = [citation(chunk, resource) for chunk, resource in rows]
        match = 'topic_link'
    origins = {o.resource_id: o for o in db.scalars(select(ResourceOrigin).where(
        ResourceOrigin.course_id == course_id, ResourceOrigin.resource_id.in_([s['resource_id'] for s in found])))} if found else {}
    result, seen = [], set()
    for source in found:
        key = (source['resource_id'], source['page'])
        if key in seen:
            continue
        seen.add(key)
        excerpt = source['excerpt'].strip()
        # A text excerpt rather than a fabricated section heading.
        focus_start = 0
        normalized = unicodedata.normalize('NFKC', excerpt).lower()
        for pattern in patterns:
            match_text = re.search(pattern, normalized)
            if match_text:
                focus_start = max(0, match_text.start()-60)
                break
        focus = ' '.join(excerpt[focus_start:focus_start+240].split())[:160]
        origin = origins.get(source['resource_id'])
        result.append({**source, 'match': match, 'focus': focus,
                       'original_url': origin.url + '#page=' + str(source['page']) if origin else None})
    return result[:3]


def study_plan(db, course_id, topics, latest, trends, chat):
    topic_metrics = {t['topic_id']: t for t in trends}
    signals = {t['topic_id']: t for t in chat['topics']}
    recommendations, strengths, statuses = [], [], {}
    for topic in topics:
        report = latest.get(topic.id)
        signal = signals.get(topic.id, {})
        graded = [q for q in topic_metrics[topic.id]['quizzes'] if q['percent'] is not None]
        quiz = graded[-1] if graded else None
        evidence, reasons = [], []
        difficulty = report.difficulty if report else 'none'
        self_weak = bool(report and (report.confidence <= 2 or report.difficulty != 'none'))
        quiz_weak = bool(quiz and quiz['percent'] < 60)
        chat_review = bool(signal.get('reported_obstacles', 0))
        if report:
            evidence.append({'kind': 'self_report', 'id': report.id, 'at': report.created_at.isoformat()+'Z', 'confidence': report.confidence, 'difficulty': report.difficulty})
            reasons.append(f'اطمینان خوداظهاری {report.confidence} از ۵')
        if quiz:
            evidence.append({'kind': 'graded_quiz', 'id': quiz['attempt_id'], 'at': quiz['at'], 'percent': quiz['percent']})
            reasons.append(f"آخرین کوییز تصحیح‌شدهٔ مبحث: {quiz['percent']:g}٪")
        if chat_review:
            evidence.append({'kind': 'chat_signal', 'obstacle_count': signal['reported_obstacles']})
            reasons.append('در پرسش‌های این مبحث نشانهٔ ابهام دیده شده؛ نیازمند بررسی، بدون نمرهٔ تسلط')
        weak = self_weak or quiz_weak
        strong = bool((quiz and quiz['percent'] >= 80) or (report and report.confidence >= 4 and report.difficulty == 'none')) and not weak and not chat_review
        status = 'needs_attention' if weak else 'review' if chat_review else 'strength' if strong else 'developing' if evidence else 'unassessed'
        statuses[topic.id] = status
        if strong:
            strengths.append({'topic_id': topic.id, 'topic': topic.name, 'reason': ' • '.join(reasons), 'evidence': evidence,
                              'basis': 'graded_quiz' if quiz else 'self_report'})
        if weak or chat_review:
            if difficulty == 'none' and quiz_weak:
                difficulty = 'practice'
            readings = reading_sources(db, course_id, topic, report.note if report else '')
            recommendations.append({'topic_id': topic.id, 'topic': topic.name, 'reason': ' • '.join(reasons),
                'status': status, 'evidence': evidence, 'action': ACTIONS[difficulty], 'sources': readings,
                'check': 'پس از مطالعه، یک مثال را بدون کمک حل کن و میزان درک خودت را دوباره ثبت کن؛ کوییز بعدی تغییر نتیجه را نشان می‌دهد.',
                'priority': 0 if quiz_weak else report.confidence if self_weak else 6,
                'resource_status': 'available' if readings else 'missing',
                'reading_hint': (topic.description or '')})
    recommendations.sort(key=lambda r: (r['priority'], r['topic_id']))
    return recommendations, strengths, statuses
