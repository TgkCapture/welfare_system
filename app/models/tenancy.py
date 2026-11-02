# app/models/tenancy.py
"""
Tenant scoping for group-owned models.

Every query on group-owned data goes through ``Model.for_group()`` or
``Model.get_for_group_or_404()``, which filter by the current group.
Rows of other groups are reported as not found, never as forbidden, so
their existence is not revealed.

``current_group_id()`` is the single place the current group is worked
out. Superadmins have no group, so scoped queries return nothing for them.
"""
from flask import abort
from flask_login import current_user
from sqlalchemy import false


def current_group_id():
    """Return the signed-in officer's group id, or None."""
    if current_user and current_user.is_authenticated:
        return current_user.group_id
    return None


def current_group():
    """Return the signed-in officer's Group, or None."""
    from app.extensions import db
    from app.models.group import Group

    group_id = current_group_id()
    return db.session.get(Group, group_id) if group_id is not None else None


class TenantScoped:
    """Mixin for models with a ``group_id`` column."""

    @classmethod
    def for_group(cls, group_id=None):
        """Query limited to *group_id* (default: the current group)."""
        if group_id is None:
            group_id = current_group_id()
        if group_id is None:
            return cls.query.filter(false())
        return cls.query.filter(cls.group_id == group_id)

    @classmethod
    def get_for_group_or_404(cls, obj_id, group_id=None):
        """Return the row with *obj_id* in the group, or abort with 404."""
        obj = cls.for_group(group_id).filter(cls.id == obj_id).first()
        if obj is None:
            abort(404)
        return obj
