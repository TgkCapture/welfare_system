# app/models/group.py
"""
Welfare groups (tenants) and their per-group settings.

Every tenant-owned row carries a ``group_id``. Groups are fully
independent and never share data.
"""
import re
import secrets
from datetime import datetime

from app.extensions import db

_SLUG_RE = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
# No 0/O, 1/I/L: the code is read out and typed on phones
_CODE_CHARS = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
ACCESS_CODE_LENGTH = 6


def new_access_code() -> str:
    return ''.join(secrets.choice(_CODE_CHARS) for _ in range(ACCESS_CODE_LENGTH))


class Group(db.Model):
    __tablename__ = 'groups'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(150), nullable=False)
    # Used in URLs (/g/<slug>/...) and storage folder names
    slug       = db.Column(db.String(60), nullable=False, unique=True, index=True)
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    settings = db.relationship(
        'GroupSettings', back_populates='group', uselist=False,
        cascade='all, delete-orphan',
    )
    roles = db.relationship(
        'Role', back_populates='group', cascade='all, delete-orphan',
    )
    users = db.relationship('User', back_populates='group')

    @staticmethod
    def is_valid_slug(slug: str) -> bool:
        return bool(slug) and len(slug) <= 60 and bool(_SLUG_RE.match(slug))

    def __repr__(self) -> str:
        return f'<Group {self.slug!r}>'


class GroupSettings(db.Model):
    """One row per group. Contribution rates live in the group's workbook."""
    __tablename__ = 'group_settings'

    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'), primary_key=True)

    # ── Branding ─────────────────────────────────────────────────────
    display_name  = db.Column(db.String(150), nullable=False)
    short_name    = db.Column(db.String(30), nullable=True)
    logo_path     = db.Column(db.String(255), nullable=True)
    primary_color = db.Column(db.String(7), nullable=False, default='#1d4ed8')
    report_title  = db.Column(db.String(200), nullable=True)

    # ── Money ────────────────────────────────────────────────────────
    currency = db.Column(db.String(3), nullable=False, default='MWK')

    # ── Data source ──────────────────────────────────────────────────
    google_sheet_url = db.Column(db.String(500), nullable=True)
    upload_enabled   = db.Column(db.Boolean, nullable=False, default=True)
    # Where things are in a workbook that isn't the standard layout (SheetMapping);
    # None reads the original Mzugoss layout automatically
    sheet_mapping    = db.Column(db.JSON, nullable=True)

    # ── Storage ──────────────────────────────────────────────────────
    report_retention_days = db.Column(db.Integer, nullable=True)  # None → app default

    # ── Public pages (/g/<slug>/...) ─────────────────────────────────
    # The paid list never shows who hasn't paid; these choose what else it shows
    public_paid_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    public_show_amounts = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    public_show_totals  = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    public_months_back  = db.Column(db.Integer, nullable=False, default=12, server_default='12')
    # One shared code officers post in the group chat; on for every new group
    access_code_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    access_code         = db.Column(db.String(20), nullable=True, default=lambda: new_access_code())

    # ── Setup checklist ──────────────────────────────────────────────
    # Steps that can't be worked out from the group's data, ticked when done
    setup_marks     = db.Column(db.JSON, nullable=False, default=list)
    setup_dismissed = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
    )

    group = db.relationship('Group', back_populates='settings')

    def __repr__(self) -> str:
        return f'<GroupSettings group={self.group_id}>'
