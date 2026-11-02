# app/models/ledger.py
"""
Money out, rates and balances.

Payout purposes are configured per group in the app. Payouts and rates are
the stored read-model of the workbook's Payouts and Rates sheets: each sync
replaces them. Yearly balances are calculated by the app, never typed, and
kept next to what the sheet's own Summary said so the two can be compared.
Every sync is recorded with the warnings it raised.
"""
from datetime import datetime

from app.extensions import db
from app.models.tenancy import TenantScoped

DEFAULT_PAYOUT_PURPOSES = ['Funeral condolence', 'Wedding gift', 'Sick patient grant']


class PayoutPurpose(TenantScoped, db.Model):
    __tablename__ = 'payout_purposes'
    __table_args__ = (
        db.UniqueConstraint('group_id', 'name', name='uq_payout_purposes_group_name'),
    )

    id         = db.Column(db.Integer, primary_key=True)
    group_id   = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    name       = db.Column(db.String(80), nullable=False)
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @classmethod
    def seed_defaults(cls, group) -> None:
        """Add the default purposes to *group* (uncommitted)."""
        db.session.add_all(cls(group=group, name=name) for name in DEFAULT_PAYOUT_PURPOSES)

    group = db.relationship('Group')


class Payout(TenantScoped, db.Model):
    """One row of the Payouts sheet."""
    __tablename__ = 'payouts'

    id          = db.Column(db.Integer, primary_key=True)
    group_id    = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    year        = db.Column(db.Integer, nullable=False)
    paid_on     = db.Column(db.Date, nullable=True)
    member_id   = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True, index=True)
    beneficiary = db.Column(db.String(150), nullable=True)
    purpose     = db.Column(db.String(80), nullable=True)   # as written in the sheet
    amount      = db.Column(db.Float, nullable=False)
    approved_by = db.Column(db.String(150), nullable=True)
    notes       = db.Column(db.Text, nullable=True)
    sheet_row   = db.Column(db.Integer, nullable=True)
    synced_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    member = db.relationship('Member')


class Rate(TenantScoped, db.Model):
    """One row of the Rates sheet: the monthly amount from a given month on."""
    __tablename__ = 'rates'

    id             = db.Column(db.Integer, primary_key=True)
    group_id       = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    effective_from = db.Column(db.Date, nullable=False)
    amount         = db.Column(db.Float, nullable=False)


class YearSummary(TenantScoped, db.Model):
    """A year's balances as calculated by the app, beside the sheet's own figures."""
    __tablename__ = 'year_summaries'
    __table_args__ = (
        db.UniqueConstraint('group_id', 'year', name='uq_year_summaries_group_year'),
    )

    id                  = db.Column(db.Integer, primary_key=True)
    group_id            = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    year                = db.Column(db.Integer, nullable=False)
    opening_balance     = db.Column(db.Float, nullable=False, default=0.0)
    total_contributions = db.Column(db.Float, nullable=False, default=0.0)
    total_payouts       = db.Column(db.Float, nullable=False, default=0.0)
    closing_balance     = db.Column(db.Float, nullable=False, default=0.0)
    # What the workbook's Summary sheet said (None when it had no value)
    sheet_opening       = db.Column(db.Float, nullable=True)
    sheet_closing       = db.Column(db.Float, nullable=True)
    synced_at           = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class SyncRun(TenantScoped, db.Model):
    """One sync of a workbook, with the warnings it raised."""
    __tablename__ = 'sync_runs'

    id        = db.Column(db.Integer, primary_key=True)
    group_id  = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    synced_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source    = db.Column(db.String(20), nullable=False, default='upload')    # upload / google_sheets
    layout    = db.Column(db.String(20), nullable=False, default='standard')  # standard / legacy
    # [{'where': 'Payouts row 4', 'message': '...'}, ...]
    warnings  = db.Column(db.JSON, nullable=False, default=list)
    # {'years': [...], 'months': [[2026, 3], ...], 'new_members': [...]}
    details   = db.Column(db.JSON, nullable=False, default=dict)

    user = db.relationship('User')
