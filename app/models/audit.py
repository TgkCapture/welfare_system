# app/models/audit.py
"""
The audit log: who changed what, and when.

Every change an officer makes (settings, workbook layout, rules, roles,
officers, members, PINs and links, uploads, reports) and every platform
action on a group (creating it, suspending it, support sessions) is kept
here with a plain-language summary. Rows are never edited or deleted.

The officer's email is copied onto the row, so the entry still reads
correctly after their account is removed. Platform-wide events (such as
storage cleanup) have no group.
"""
from datetime import datetime

from app.extensions import db
from app.models.tenancy import TenantScoped


class AuditEvent(TenantScoped, db.Model):
    __tablename__ = 'audit_events'

    id         = db.Column(db.Integer, primary_key=True)
    group_id   = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=True, index=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    actor      = db.Column(db.String(255), nullable=False, default='')
    action     = db.Column(db.String(50), nullable=False, index=True)
    summary    = db.Column(db.String(500), nullable=False)
    details    = db.Column(db.JSON, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    # Done by a platform superadmin during a support session
    in_support = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    group = db.relationship('Group')

    @property
    def area(self) -> str:
        """The first part of the action, e.g. 'member' for 'member.merge'."""
        return self.action.split('.', 1)[0]

    def __repr__(self) -> str:
        return f'<AuditEvent {self.action} group={self.group_id} by {self.actor!r}>'
