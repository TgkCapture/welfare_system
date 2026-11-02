# app/models/member.py
"""
Stored contribution data: the app's read-model of each group's workbook.

The spreadsheet stays the source of truth. Every sync replaces the stored
rows for the synced period, so the DB always mirrors the latest sync.
Contribution history is kept forever (retention cleanup never touches it).

Members have no accounts. ``history_token`` and ``pin_hash`` are for the
public history pages (Phase 4).
"""
import re
import secrets
import unicodedata
from datetime import date, datetime

from app.extensions import db
from app.models.tenancy import TenantScoped

# Contribution.status values
PAID, PARTIAL, UNPAID = 'paid', 'partial', 'unpaid'


def normalise_name(name) -> str:
    """The form used to match names across years: case, spacing and dots ignored."""
    text = unicodedata.normalize('NFKC', str(name or ''))
    text = re.sub(r'[.,]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip().casefold()


def tidy_name(name) -> str:
    """A display name with stray spaces removed, keeping the sheet's spelling."""
    return re.sub(r'\s+', ' ', str(name or '')).strip()


def new_history_token() -> str:
    return secrets.token_urlsafe(24)


class Member(TenantScoped, db.Model):
    __tablename__ = 'members'
    __table_args__ = (
        db.UniqueConstraint('group_id', 'normalised_name', name='uq_members_group_name'),
        db.UniqueConstraint('group_id', 'code', name='uq_members_group_code'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    group_id        = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    # The Member ID used in the standard workbook (e.g. M001)
    code            = db.Column(db.String(30), nullable=True)
    display_name    = db.Column(db.String(150), nullable=False)
    normalised_name = db.Column(db.String(150), nullable=False)
    phone           = db.Column(db.String(30), nullable=True)
    # First and last month of membership (stored as the 1st of the month)
    joined_on       = db.Column(db.Date, nullable=True)
    left_on         = db.Column(db.Date, nullable=True)
    is_active       = db.Column(db.Boolean, nullable=False, default=True)

    # Public history access (Phase 4)
    history_token       = db.Column(db.String(64), nullable=False, unique=True, default=new_history_token)
    pin_hash            = db.Column(db.String(256), nullable=True)
    pin_failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    pin_locked_until    = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    aliases = db.relationship('MemberAlias', back_populates='member', cascade='all, delete-orphan')
    contributions = db.relationship('Contribution', back_populates='member', lazy='dynamic')

    def is_member_in(self, year: int, month: int) -> bool:
        """True if the member had joined and not yet left in that month."""
        first_of_month = date(year, month, 1)
        if self.joined_on and first_of_month < self.joined_on.replace(day=1):
            return False
        if self.left_on and first_of_month > self.left_on.replace(day=1):
            return False
        return True

    def __repr__(self) -> str:
        return f'<Member {self.display_name!r} group={self.group_id}>'


class MemberAlias(TenantScoped, db.Model):
    """Another spelling of a member's name, used when matching sheet rows."""
    __tablename__ = 'member_aliases'
    __table_args__ = (
        db.UniqueConstraint('group_id', 'normalised_name', name='uq_member_aliases_group_name'),
    )

    id              = db.Column(db.Integer, primary_key=True)
    group_id        = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    member_id       = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)
    normalised_name = db.Column(db.String(150), nullable=False)

    member = db.relationship('Member', back_populates='aliases')


class Contribution(TenantScoped, db.Model):
    """What one member paid in one month, as of the latest sync."""
    __tablename__ = 'contributions'
    __table_args__ = (
        db.UniqueConstraint('member_id', 'year', 'month', name='uq_contributions_member_period'),
        db.Index('ix_contributions_group_period', 'group_id', 'year', 'month'),
    )

    id        = db.Column(db.Integer, primary_key=True)
    group_id  = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False, index=True)
    year      = db.Column(db.Integer, nullable=False)
    month     = db.Column(db.Integer, nullable=False)
    amount    = db.Column(db.Float, nullable=False, default=0.0)
    status    = db.Column(db.String(10), nullable=False)   # PAID / PARTIAL / UNPAID
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    member = db.relationship('Member', back_populates='contributions')


class PeriodSummary(TenantScoped, db.Model):
    """A group's totals for one month, as of the latest sync."""
    __tablename__ = 'period_summaries'
    __table_args__ = (
        db.UniqueConstraint('group_id', 'year', 'month', name='uq_period_summaries_group_period'),
    )

    id                  = db.Column(db.Integer, primary_key=True)
    group_id            = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    year                = db.Column(db.Integer, nullable=False)
    month               = db.Column(db.Integer, nullable=False)
    total_contributions = db.Column(db.Float, nullable=False, default=0.0)
    contributors_count  = db.Column(db.Integer, nullable=False, default=0)
    defaulters_count    = db.Column(db.Integer, nullable=False, default=0)
    # From the sheet's own summary rows, when it has them
    money_dispensed     = db.Column(db.Float, nullable=True)
    book_balance        = db.Column(db.Float, nullable=True)
    source              = db.Column(db.String(20), nullable=False, default='upload')  # upload / google_sheets
    synced_by           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    synced_at           = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f'<PeriodSummary group={self.group_id} {self.year}-{self.month:02d}>'
