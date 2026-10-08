"""Structured source-linked interpretation; factual chronology is rendered from DB, not invented by LLM."""
import json
import re
from app.services.report_evidence import dump


def normalized(text):
    return re.sub(r'\s+', ' ', str(text)).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹يك', '0123456789یک')).strip()


def source_text(record):
    # Canonical facts are always available even when a self-report has no note.
    return dump(record)


def _parse_analysis_strict(text, records, topic_id=None):
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    data = json.loads(text)
    by_id = {r['id']: r for r in records}
    items = data.get('analysis')
    if not isinstance(items, list) or not 1 <= len(items) <= 16:
        raise ValueError('analysis structure')
    validated = []
    for item in items:
        statement, support = item.get('text'), item.get('support')
        if not isinstance(statement, str) or not isinstance(support, list) or not 1 <= len(support) <= 8:
            raise ValueError('missing support')
        aliases = {'توانمندی':'strength','قوت':'strength','نقطه قوت':'strength','توانایی':'strength',
                   'چالش':'difficulty','ضعف':'difficulty','مشکل':'difficulty','weakness':'difficulty',
                   'روند':'trend','پیشرفت':'trend','روند یادگیری':'trend',
                   'ابهام':'uncertainty','عدم قطعیت':'uncertainty','محدودیت':'uncertainty',
                   'مشارکت':'engagement','استفاده':'engagement','فعالیت':'engagement'}
        item['kind'] = aliases.get(item.get('kind'),item.get('kind'))
        if item.get('kind') not in ('strength', 'difficulty', 'trend', 'uncertainty', 'engagement'):
            raise ValueError('invalid observation kind')
        ids = []
        for citation in support:
            record = by_id.get(citation.get('id'))
            quote = citation.get('quote')
            if not record:
                raise ValueError('invalid support ID')
            if record.get('role') == 'assistant':
                raise ValueError('assistant is not student evidence')
            if topic_id is not None and record.get('topic_id') != topic_id:
                raise ValueError('cross-topic evidence')
            if 'field' in citation:
                field = citation['field']
                allowed = {'text','answer','score','confidence_out_of_5','difficulty','note','study_minutes_self_reported','feedback','is_correct','at','submitted','pending_grading','event','metadata','time_spent','attempt_number','legacy_mastery_estimate','legacy_confidence_estimate'}
                if not isinstance(field,str):
                    raise ValueError('unsupported evidence field')
                if field not in allowed and not field.startswith('form.answers.'):
                    candidates = [(k,v) for k,v in record.items() if k in allowed and v == citation.get('value')]
                    candidates += [('form.answers.' + k,v) for k,v in record.get('form',{}).get('answers',{}).items()
                                   if v == citation.get('value')]
                    if len(candidates) != 1:
                        raise ValueError('unsupported evidence field')
                    field = candidates[0][0]
                    citation['field'] = field

                value = record
                for key in field.split('.'):
                    if not isinstance(value, dict) or key not in value:
                        raise ValueError('missing evidence field')
                    value = value[key]
                if value in ('',None) and item['kind'] != 'uncertainty':
                    raise ValueError('empty evidence cannot support a performance claim')
                if value != citation.get('value'):
                    raise ValueError('support value mismatch for ' + record['id'] + '.' + field)
            elif not isinstance(quote, str) or len(normalized(quote)) < 8 or normalized(quote) not in normalized(source_text(record)):
                raise ValueError('invented quote')
            ids.append(record['id'])
        cited = set(re.findall(r'\[([A-Z]+\d+(?:T\d+)?)\]', statement))
        if not cited.issubset(set(ids)):
            raise ValueError('unsupported citation')
        letters = re.findall(r'[^\W\d_]', statement)
        persian = re.findall(r'[\u0600-\u06ff]', statement)
        if len(persian) < 20 or len(persian) / max(1, len(letters)) < .5:
            raise ValueError('analysis must be Persian')
        # Numeric facts/dates belong to the deterministic evidence table.
        narrative = re.sub(r'\[[A-Z]+\d+(?:T\d+)?\]', '', statement)
        numbers = set(re.findall(r'\d+(?:\.\d+)?', normalized(narrative)))
        factual_numbers = set()
        for evidence_id in ids:
            record = by_id[evidence_id]
            factual_numbers.update(re.findall(r'\d+(?:\.\d+)?', normalized(source_text(record))))
            if record['kind'] == 'self_report':
                factual_numbers.add('5')
            if record.get('submitted') and record.get('score') is not None and record.get('max_points'):
                factual_numbers.add(str(round(record['score'] / record['max_points'] * 100)))
        if not numbers.issubset(factual_numbers):
            raise ValueError('number unsupported by cited records')
        validated.append({**item, 'support': support, 'text': narrative.strip(), 'ids': ids})
    return validated



def parse_analysis(text, records, topic_id=None):
    cleaned = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    start = cleaned.find('{')
    if start < 0:
        raise ValueError('analysis must be a JSON object')
    data, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    items = data.get('analysis')
    if not isinstance(items,list) or not 1 <= len(items) <= 32:
        raise ValueError('analysis structure')
    accepted, last_error = [], None
    for item in items:
        try:
            accepted.extend(_parse_analysis_strict(json.dumps({'analysis':[item]},ensure_ascii=False),records,topic_id))
        except (ValueError, TypeError, KeyError) as exc:
            last_error = exc
    if not accepted:
        raise last_error or ValueError('no supported analysis')
    return accepted

def analysis_markdown(items):
    labels = {'strength':'شواهد قوت', 'difficulty':'چالش قابل پیگیری', 'trend':'برداشت از روند',
              'uncertainty':'ابهام و محدودیت شواهد', 'engagement':'مشارکت در یادگیری'}
    out = []
    for item in items:
        refs = ' '.join('[' + ref + ']' for ref in dict.fromkeys(item['ids']))
        out.append('### ' + labels[item['kind']] + '\n\n' + item['text'] + ' ' + refs)
        for support in item['support']:
            # Verbatim support gives the teacher a way to assess the interpretation.
            labels_field = {'score':'نمره', 'confidence_out_of_5':'اطمینان خوداظهاری از ۵', 'text':'پیام دانشجو', 'answer':'پاسخ دانشجو', 'difficulty':'چالش خوداظهاری', 'study_minutes_self_reported':'دقیقهٔ مطالعهٔ خوداظهاری'}
            quote = support.get('quote')
            if quote is None:
                quote = labels_field.get(support['field'], support['field']) + ': ' + str(support['value'])
            quote = quote.replace('\n', ' ').replace('`', '')
            out.append('> شاهد [' + support['id'] + ']: ' + quote)
        for key, title in [('action','اقدام پیشنهادی'), ('check','روش پیگیری')]:
            if item.get(key):
                out.append('**' + title + ':** ' + str(item[key]))
    return '\n\n'.join(out)


def factual_markdown(snapshot):
    records = snapshot['evidence']
    user_chats = [r for r in records if r.get('role') == 'user']
    reports = [r for r in records if r['kind'] == 'self_report']
    submitted = [r for r in records if r['kind'] == 'quiz_answer' and r['submitted']]
    graded = [r for r in submitted if r['score'] is not None]
    pending = [r for r in submitted if r['pending_grading']]
    days = len({r['at'][:10] for r in user_chats})
    text = '## اطلاعات ثبت‌شده\n\n'
    text += f'- پیام‌های دانشجو: {len(user_chats)} در {days} روز (تاریخ UTC)؛ مدت استفاده از روی پیام‌ها قابل اندازه‌گیری نیست.\n'
    text += f'- خوداظهاری‌ها: {len(reports)}؛ امتیاز اطمینان، خوداظهاری است و نمرهٔ تسلط نیست.\n'
    text += f'- پاسخ‌های نهایی کوییز: {len(submitted)}؛ تصحیح‌شده: {len(graded)}؛ در انتظار تصحیح: {len(pending)}.\n'
    for t in snapshot['topics']:
        relevant = [r for r in records if r.get('topic_id') == t['id'] and r.get('role') != 'assistant']
        text += '\n### ' + t['name'] + '\n\n'
        self_reports = [r for r in relevant if r['kind'] == 'self_report']
        if self_reports:
            first, last = self_reports[0], self_reports[-1]
            text += f'اطمینان ثبت‌شده: {first["confidence_out_of_5"]} ← {last["confidence_out_of_5"]} از ۵. [{first["id"]}] [{last["id"]}]\n\n'
        if self_reports:
            text += '| شاهد | تاریخ UTC | اطمینان | چالش | دقیقهٔ خوداظهاری |\n|---|---|---|---|---|\n'
            for r in self_reports:
                text += f'| [{r["id"]}] | {r["at"]} | {r["confidence_out_of_5"]} از ۵ | {r["difficulty"]} | {r["study_minutes_self_reported"]} |\n'
            for r in self_reports:
                if r.get('note'):
                    text += '\nیادداشت [' + r['id'] + ']: ' + r['note'].replace('\n', ' ') + '\n\n'
                form = r.get('form')
                if form:
                    for field in form['fields']:
                        if field['id'] in form['answers']:
                            text += '\n' + field['label'] + ': ' + str(form['answers'][field['id']]).replace('\n',' ') + ' [' + r['id'] + ']\n\n'
        answers = [r for r in relevant if r['kind'] == 'quiz_answer' and r['submitted']]
        if answers:
            text += '| شاهد | تاریخ UTC | سؤال | نمره | وضعیت |\n|---|---|---|---|---|\n'
            for r in answers:
                title = r['question'].replace('|', ' / ').replace('\n',' ')
                score = 'نامشخص' if r['score'] is None else f'{r["score"]} از {r["max_points"]}'
                text += f'| [{r["id"]}] | {r["at"]} | {title} | {score} | {"در انتظار تصحیح" if r["pending_grading"] else "ثبت‌شده"} |\n'
        reading = [r for r in snapshot['resources'] if r['topic_id'] in (None, t['id'])]
        if reading:
            text += '\nمنابع موجود برای مطالعه: ' + '، '.join(r['title'] for r in reading) + '. مطالعهٔ این منابع توسط دانشجو ثبت یا تأیید نشده است.\n'
        if not relevant:
            text += 'شواهد دانشجو برای این مبحث ثبت نشده؛ نبود داده به معنی ضعف یا تسلط نیست.\n'
    return text
