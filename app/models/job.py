# app/models/job.py
"""
Background jobs that run once a day for the whole platform.

Each worker process runs the scheduler, and a cron job may run the same
job too. Before doing the work, a runner inserts the (job, day) row; the
unique key lets exactly one of them succeed, on SQLite and Postgres alike,
and the others skip the day. The row then records how the run went.
"""
from datetime import datetime

from app.extensions import db


class JobRun(db.Model):
    __tablename__ = 'job_runs'
    __table_args__ = (db.UniqueConstraint('job', 'run_on', name='uq_job_runs_job_run_on'),)

    id          = db.Column(db.Integer, primary_key=True)
    job         = db.Column(db.String(50), nullable=False)
    run_on      = db.Column(db.Date, nullable=False)
    started_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    outcome     = db.Column(db.String(20), nullable=True)     # ok / failed; empty while running
    details     = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f'<JobRun {self.job} {self.run_on} {self.outcome or "running"}>'
