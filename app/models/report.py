# app/models/report.py
"""
Report models.

GeneratedReport  — one row per PDF produced by the system.
ReportAccessLog  — audit trail: who accessed which report and when.
"""
from datetime import datetime

from app.extensions import db   # FIX: was `from app import db` — use extensions


class GeneratedReport(db.Model):
    __tablename__ = 'generated_reports'

    id           = db.Column(db.Integer, primary_key=True)
    month        = db.Column(db.Integer, nullable=False)
    year         = db.Column(db.Integer, nullable=False)
    report_type  = db.Column(
        db.String(50), nullable=False, default='contributions'
    )
    filename     = db.Column(db.String(255), nullable=False)
    file_path    = db.Column(db.String(500), nullable=False)
    generated_by = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )
    generated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )
    file_size    = db.Column(db.Integer)            # bytes
    total_contributions = db.Column(db.Float, default=0.0)
    contributors_count  = db.Column(db.Integer, default=0)
    defaulters_count    = db.Column(db.Integer, default=0)
    money_dispensed     = db.Column(db.Float, nullable=True)
    total_book_balance  = db.Column(db.Float, nullable=True)
    is_archived  = db.Column(db.Boolean, nullable=False, default=False, index=True)
    archived_at  = db.Column(db.DateTime, nullable=True)

    # Relationships
    generator = db.relationship(
        'User',
        backref=db.backref('generated_reports', lazy='dynamic'),
        # lazy='dynamic' lets callers filter/paginate without loading all rows
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def file_size_mb(self) -> float:
        """File size in megabytes, rounded to 2 decimal places."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return 0.0

    @property
    def month_name(self) -> str:
        """Return the full month name for this report's month number."""
        import calendar
        try:
            return calendar.month_name[self.month]
        except IndexError:
            return str(self.month)

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict for API responses."""
        return {
            'id':                  self.id,
            'month':               self.month,
            'month_name':          self.month_name,
            'year':                self.year,
            'report_type':         self.report_type,
            'filename':            self.filename,
            'generated_by':        self.generated_by,
            'generated_at':        self.generated_at.isoformat() if self.generated_at else None,
            'file_size_mb':        self.file_size_mb,
            'total_contributions': self.total_contributions,
            'contributors_count':  self.contributors_count,
            'defaulters_count':    self.defaulters_count,
            'money_dispensed':     self.money_dispensed,
            'total_book_balance':  self.total_book_balance,
            'is_archived':         self.is_archived,
            'archived_at':         self.archived_at.isoformat() if self.archived_at else None,
            'generator_email':     self.generator.email if self.generator else None,
        }

    def __repr__(self) -> str:
        return (
            f'<GeneratedReport {self.month}/{self.year} '
            f'by {self.generator.email if self.generator else self.generated_by}>'
        )


class ReportAccessLog(db.Model):
    """Audit trail for report access events."""
    __tablename__ = 'report_access_logs'

    # Valid action strings — checked at insert time
    ACTIONS = ('generate', 'preview', 'download', 'regenerate', 'export')

    id          = db.Column(db.Integer, primary_key=True)
    report_id   = db.Column(
        db.Integer, db.ForeignKey('generated_reports.id'),
        nullable=False, index=True
    )
    user_id     = db.Column(
        db.Integer, db.ForeignKey('users.id'),
        nullable=False, index=True
    )
    accessed_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )
    action      = db.Column(db.String(50), nullable=False)

    # Relationships
    report = db.relationship(
        'GeneratedReport',
        backref=db.backref('access_logs', lazy='dynamic'),
    )
    user = db.relationship(
        'User',
        backref=db.backref('report_accesses', lazy='dynamic'),
    )

    def __repr__(self) -> str:
        return (
            f'<ReportAccessLog report={self.report_id} '
            f'user={self.user_id} action={self.action!r}>'
        )