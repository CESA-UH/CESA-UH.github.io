"""Durable DB queue, atomic leases and resumable checkpoints; no request holds an LLM call."""
import logging
import secrets
import threading
from datetime import datetime, timedelta
from sqlalchemy import select, update, or_, and_
from sqlalchemy.orm import Session
from app.models import LearningReport
from app.services.report_agent import run_agent, AgentError
from app.services.report_evidence import evidence_snapshot

log = logging.getLogger(__name__)
LEASE_SECONDS = 90


class LeaseLost(Exception):
    pass


def claim(engine):
    token, now = secrets.token_hex(16), datetime.utcnow()
    eligible = or_(and_(LearningReport.status == 'queued', or_(LearningReport.lease_until.is_(None), LearningReport.lease_until < now)), and_(LearningReport.status == 'running', LearningReport.lease_until < now))
    with Session(engine) as db:
        job_id = db.scalar(select(LearningReport.id).where(eligible).order_by(LearningReport.created_at, LearningReport.id).limit(1))
        if job_id is None:
            return None
        result = db.execute(update(LearningReport).where(LearningReport.id == job_id, eligible).values(
            status='running', lease_token=token, lease_until=now + timedelta(seconds=LEASE_SECONDS)))
        db.commit()
        return (job_id, token) if result.rowcount == 1 else None


def process(engine, job_id, token):
    retry_delay = 0
    heartbeat_stop = threading.Event()

    def heartbeat():
        while not heartbeat_stop.wait(15):
            try:
                with Session(engine) as db:
                    db.execute(update(LearningReport).where(LearningReport.id == job_id,
                        LearningReport.lease_token == token, LearningReport.status == 'running').values(
                        lease_until=datetime.utcnow() + timedelta(seconds=LEASE_SECONDS)))
                    db.commit()
            except Exception:
                log.warning('Could not renew learning report lease')

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()

    def persist(**values):
        with Session(engine) as db:
            result = db.execute(update(LearningReport).where(LearningReport.id == job_id,
                LearningReport.lease_token == token, LearningReport.status == 'running').values(**values))
            db.commit()
            if result.rowcount != 1:
                raise LeaseLost()

    try:
        snapshot_engine = engine.execution_options(isolation_level='REPEATABLE READ') if engine.dialect.name == 'postgresql' else engine
        with Session(snapshot_engine) as db:
            job = db.get(LearningReport, job_id)
            snapshot, checkpoint, models = job.snapshot, job.checkpoint, job.models
            had_snapshot = bool(snapshot)
            if not snapshot:
                snapshot = evidence_snapshot(db, job.course_id, job.student_id)
        if not had_snapshot:
            persist(snapshot=snapshot, snapshot_at=datetime.utcnow(), counts=snapshot['counts'])
        learning_data = sum(snapshot['counts'].get(k,0) for k in ('self_reports','student_questions','quiz_attempts','events','legacy_attempts','legacy_skill_estimates'))
        if not learning_data:
            content = '## شواهد کافی موجود نیست\n\nبرای این دانشجو هنوز خوداظهاری، گفت‌وگو یا پاسخ کوییز ثبت نشده است. '
            content += 'از نبود داده نمی‌توان ضعف یا تسلط را نتیجه گرفت. نخست یک خوداظهاری و ارزیابی کوتاه از مباحث ترم ثبت شود.\n\n'
            content += '\n'.join('### ' + t['name'] + '\nشواهدی برای ارزیابی این مبحث ثبت نشده است.\n' for t in snapshot['topics'])
        else:
            def save(checkpoint, models, phase, progress):
                persist(checkpoint=checkpoint, models=models, phase=phase, progress=progress)
            content, checkpoint, models = run_agent(snapshot, checkpoint, models, save)
        persist(content=content, checkpoint=checkpoint, models=models, status='completed', active_key=None,
                completed_at=datetime.utcnow(), phase='گزارش آماده است', progress=100, lease_token=None, lease_until=None, error='')
    except LeaseLost:
        pass
    except Exception as exc:
        try:
            with Session(engine) as db:
                saved = dict(db.get(LearningReport,job_id).checkpoint)
            retries = saved.get('__worker_retry',0)
            if isinstance(exc,AgentError) and exc.retryable:
                retry_delay = min(300, 15 * 2**min(retries,5))
                saved['__worker_retry'] = retries + 1
                persist(status='queued',checkpoint=saved,lease_token=None,
                        lease_until=datetime.utcnow() + timedelta(seconds=min(300, 15 * 2**min(retries,5))),
                        phase=f'سرویس در دسترس نیست؛ در صف تلاش خودکار {retries + 1}',error='')
            else:
                persist(status='failed', active_key=None, lease_token=None, lease_until=None,
                        phase='تهیهٔ گزارش متوقف شد', error=str(exc) if isinstance(exc, AgentError) else 'خطای پردازش گزارش؛ دوباره تلاش کنید.')
        except LeaseLost:
            pass
        log.warning('Learning report %s interrupted (%s)', job_id, type(exc).__name__)
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=2)
    return retry_delay


class ReportWorker:
    def __init__(self, engine, concurrency=1):
        self.engine, self.stop = engine, threading.Event()
        self.threads = [threading.Thread(target=self.loop, daemon=True, name=f'learning-report-{i}')
                        for i in range(max(1, min(4, concurrency)))]

    def start(self):
        for thread in self.threads:
            thread.start()

    def close(self):
        self.stop.set()

    def loop(self):
        while not self.stop.is_set():
            try:
                item = claim(self.engine)
                if item:
                    delay = process(self.engine, *item)
                    if delay:
                        self.stop.wait(delay)
                    continue
            except Exception:
                log.warning('Learning report queue temporarily unavailable')
            self.stop.wait(3)
