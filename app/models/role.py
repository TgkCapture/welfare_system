# app/models/role.py
"""
Group-scoped officer roles.

Permissions are a fixed, platform-defined list. Each group defines its
own named roles (e.g. "Treasurer") as a subset of those permissions.
New groups are seeded with PRESET_ROLES, which they can rename or edit.
"""
from datetime import datetime

from app.extensions import db
from app.models.tenancy import TenantScoped

# code → human label, in display order
PERMISSIONS = {
    'upload_data':      'Upload or sync contribution data',
    'generate_reports': 'Generate reports',
    'manage_reports':   'Archive, restore and delete reports',
    'view_reports':     'View and download reports',
    'manage_members':   'Manage members, links and PINs',
    'edit_rules':       'Edit welfare rules',
    'edit_settings':    'Edit group settings',
    'manage_users':     'Manage officers and roles',
}

PRESET_ROLES = {
    'Chairperson': list(PERMISSIONS),
    'Treasurer': [
        'upload_data', 'generate_reports', 'manage_reports',
        'view_reports', 'manage_members',
    ],
    'Secretary': ['generate_reports', 'view_reports', 'edit_rules'],
}


class Role(TenantScoped, db.Model):
    __tablename__ = 'roles'
    __table_args__ = (
        db.UniqueConstraint('group_id', 'name', name='uq_roles_group_name'),
    )

    id          = db.Column(db.Integer, primary_key=True)
    group_id    = db.Column(
        db.Integer, db.ForeignKey('groups.id'), nullable=False, index=True
    )
    name        = db.Column(db.String(50), nullable=False)
    permissions = db.Column(db.JSON, nullable=False, default=list)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    group = db.relationship('Group', back_populates='roles')

    def has(self, permission: str) -> bool:
        return permission in (self.permissions or [])

    @classmethod
    def seed_presets(cls, group) -> dict:
        """Add PRESET_ROLES to *group* (uncommitted) and return them by name."""
        roles = {
            name: cls(group=group, name=name, permissions=list(perms))
            for name, perms in PRESET_ROLES.items()
        }
        db.session.add_all(roles.values())
        return roles

    def __repr__(self) -> str:
        return f'<Role {self.name!r} group={self.group_id}>'
