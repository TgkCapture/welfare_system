"""
Daily jobs run once a day however many workers (or cron entries) try.
"""
from datetime import date, datetime

import pytest

from app.models.job import JobRun
from app.services import jobs, scheduler as scheduler_module
from app.services.scheduler import CleanupScheduler


def test_only_the_first_claim_of_the_day_succeeds(app):
    assert jobs.claim('cleanup') is not None
    assert jobs.claim('cleanup') is None
    assert jobs.claim('other') is not None
    assert jobs.claim('cleanup', day=date(2030, 1, 1)) is not None


def test_a_job_runs_once_and_records_how_it_went(app):
    calls = []

    def work():
        calls.append(1)
        return {'deleted_count': 2, 'big': list(range(100))}

    assert jobs.run_daily('cleanup', work, summarise=lambda r: {'deleted_count': r['deleted_count']}) is not None
    assert jobs.run_daily('cleanup', work) is None
    assert calls == [1]

    run = JobRun.query.one()
    assert (run.outcome, run.details, run.run_on) == ('ok', {'deleted_count': 2}, date.today())
    assert run.finished_at is not None


def test_a_failed_run_is_recorded_and_not_retried_the_same_day(app):
    def broken():
        raise RuntimeError('disk full')

    with pytest.raises(RuntimeError):
        jobs.run_daily('cleanup', broken)
    assert jobs.run_daily('cleanup', lambda: {}) is None

    run = jobs.last_run('cleanup')
    assert (run.outcome, run.details) == ('failed', {'error': 'disk full'})


def test_two_workers_clean_up_once(app):
    first, second = CleanupScheduler(), CleanupScheduler()
    for worker in (first, second):
        worker.app = app

    results = [first._run_cleanup(), second._run_cleanup()]

    assert results[0]['success'] is True and results[1] is None
    assert JobRun.query.filter_by(job='cleanup').count() == 1


def test_the_cron_command_runs_once_a_day(app):
    runner = app.test_cli_runner()
    assert 'Deleted 0 file(s)' in runner.invoke(args=['daily-cleanup']).output
    assert 'already run' in runner.invoke(args=['daily-cleanup']).output


@pytest.mark.parametrize('now, last_run, due', [
    (datetime(2026, 11, 3, 1, 59), None, False),                 # before the time
    (datetime(2026, 11, 3, 2, 0), None, True),
    (datetime(2026, 11, 3, 15, 0), None, True),                  # started late: still runs today
    (datetime(2026, 11, 3, 15, 0), date(2026, 11, 3), False),    # this worker already tried
    (datetime(2026, 11, 4, 2, 1), date(2026, 11, 3), True),
])
def test_cleanup_is_due_once_the_time_has_passed(monkeypatch, now, last_run, due):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(scheduler_module, 'datetime', Clock)
    worker = CleanupScheduler()
    worker.cleanup_hour, worker._last_run_date = (2, 0), last_run
    assert worker._is_due() is due
