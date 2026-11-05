# app/models/ledger.py
"""
Money out, rates and balances.

Payout purposes are the group's own: each group lists why it pays money out
(there is no fixed or default list). Payouts and rates are
the stored read-model of the workbook's Payouts and Rates sheets: each sync
replaces them. Yearly balances are calculated by the app, never typed, and
kept next to what the sheet's own Summary said so the two can be compared.
Every sync is recorded with the warnings it raised.
"""
from datetime import datetime

from app.extensions import db
from app.models.tenancy import TenantScoped

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


# How a sync's warnings are grouped for officers, most important first:
# (kind, heading, why it matters). Warnings without a kind go last.
WARNING_SECTIONS = [
    ('formula', 'Formulas typed over',
     "A number typed over a Summary formula stops it adding up, so the workbook's own totals go "
     'wrong. Fix these first: the Summary differences below usually come from them.'),
    ('dates', 'Dates changed by dragging',
     'These change which months members are expected to pay, so they change who shows as unpaid.'),
    ('summary', "Summary totals that don't match the app",
     "Reports use the app's figures, worked out from the payments and payouts. The Summary sheet "
     'should agree with them.'),
    (None, 'Other things to check', None),
]


class SyncRun(TenantScoped, db.Model):
    """One sync of a workbook, with the warnings it raised."""
    __tablename__ = 'sync_runs'

    id        = db.Column(db.Integer, primary_key=True)
    group_id  = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    synced_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source    = db.Column(db.String(20), nullable=False, default='upload')    # upload / google_sheets
    layout    = db.Column(db.String(20), nullable=False, default='standard')  # standard / legacy
    # [{'where': 'Payouts row 4', 'message': '...', 'fix': '...'?, 'kind': '...'?}, ...]
    warnings  = db.Column(db.JSON, nullable=False, default=list)
    # {'years': [...], 'months': [[2026, 3], ...], 'new_members': [...]}
    details   = db.Column(db.JSON, nullable=False, default=dict)

    user = db.relationship('User')

    @property
    def warning_sections(self) -> list:
        """The warnings grouped as WARNING_SECTIONS: [(heading, why, [warnings])], empty groups left out."""
        known = {kind for kind, _, _ in WARNING_SECTIONS if kind}
        sections = []
        for kind, heading, why in WARNING_SECTIONS:
            items = [w for w in self.warnings or []
                     if (w.get('kind') == kind if kind else w.get('kind') not in known)]
            if items:
                sections.append((heading, why, items))
        return sections

    @property
    def ordered_warnings(self) -> list:
        """Every warning, most important first."""
        return [w for _, _, items in self.warning_sections for w in items]
