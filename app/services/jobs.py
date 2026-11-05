# app/services/jobs.py
"""
Run a daily job exactly once, however many workers or cron entries try.

    jobs.run_daily('cleanup', FileCleanupService.cleanup_scheduled)

The first caller of the day claims it (see app/models/job.py) and runs it;
everyone else gets None back. A run that crashes keeps its claim, so the
job waits for the next day rather than retrying in a loop.
"""
import logging
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.job import JobRun

logger = logging.getLogger(__name__)


def claim(job: str, day: date = None):
    """Claim *job* for *day* (today). The JobRun, or None if already claimed."""
    run = JobRun(job=job, run_on=day or date.today())
    db.session.add(run)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None
    return run


def run_daily(job: str, work, summarise=lambda result: result):
    """Run *work* if this caller claims today's *job*. Its result, or None if skipped.

    *summarise* turns the result into what is stored on the run.
    """
    run = claim(job)
    if run is None:
        logger.info(f'{job}: already run today, skipping')
        return None

    try:
        result = work()
    except Exception as e:
        db.session.rollback()
        _finish(run, 'failed', {'error': str(e)[:500]})
        raise
    _finish(run, 'ok', summarise(result))
    return result


def last_run(job: str):
    return JobRun.query.filter_by(job=job).order_by(JobRun.run_on.desc()).first()


def _finish(run, outcome, details):
    run.outcome, run.details, run.finished_at = outcome, details, datetime.utcnow()
    db.session.commit()
