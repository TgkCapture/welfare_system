# app/models/rules.py
"""
A group's welfare rules, as ordered sections written by its officers
(edit_rules). The rules page and the rules PDF are both drawn from these.

Bodies use a small formatting syntax (see services/rules_markup.py), so
officers can write lists and bold text without any HTML.
"""
from datetime import datetime

from app.extensions import db
from app.models.tenancy import TenantScoped


class RuleSection(TenantScoped, db.Model):
    __tablename__ = 'rule_sections'

    id         = db.Column(db.Integer, primary_key=True)
    group_id   = db.Column(db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True)
    position   = db.Column(db.Integer, nullable=False, default=0)
    title      = db.Column(db.String(120), nullable=False)
    subtitle   = db.Column(db.String(200), nullable=True)
    body       = db.Column(db.Text, nullable=False, default='')
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def ordered(cls, group_id=None):
        return cls.for_group(group_id).order_by(cls.position, cls.id)

    def __repr__(self) -> str:
        return f'<RuleSection {self.title!r} group={self.group_id}>'
