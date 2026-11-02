# app/models/user.py
"""
User model — officer accounts.

An officer belongs to exactly one group (``group_id``) and holds one of
that group's roles (``role_id``). Email is unique within a group, so the
same person may hold separate, unrelated accounts in different groups.

Platform superadmins have ``is_superadmin`` set and no group. They hold
no group permissions; platform pages check ``is_superadmin`` instead.
"""
from flask_login import UserMixin
from app.extensions import db
from app.models.tenancy import TenantScoped


class User(TenantScoped, UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.UniqueConstraint('group_id', 'email', name='uq_users_group_email'),
    )

    id         = db.Column(db.Integer, primary_key=True)
    group_id   = db.Column(
        db.Integer, db.ForeignKey('groups.id'), nullable=True, index=True
    )
    role_id    = db.Column(
        db.Integer, db.ForeignKey('roles.id'), nullable=True, index=True
    )
    is_superadmin = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )
    email      = db.Column(db.String(150), nullable=False, index=True)
    # scrypt hashes are longer than bcrypt — 256 chars is safe headroom
    password   = db.Column(db.String(256), nullable=False)
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    last_login = db.Column(db.DateTime, nullable=True)

    group = db.relationship('Group', back_populates='users')
    role  = db.relationship('Role')

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    @classmethod
    def email_taken(cls, email: str, group_id, exclude_id: int = None) -> bool:
        """True if *email* is used by another account in *group_id*.

        A *group_id* of None checks among superadmins.
        """
        in_group = cls.group_id.is_(None) if group_id is None else cls.group_id == group_id
        query = cls.query.filter(cls.email == email, in_group)
        if exclude_id is not None:
            query = query.filter(cls.id != exclude_id)
        return db.session.query(query.exists()).scalar()

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------

    @property
    def permissions(self) -> frozenset:
        if self.is_superadmin:
            # In a support session a superadmin can open every screen of the
            # group, read-only (app/services/support.py refuses form posts)
            from app.models.role import PERMISSIONS
            from app.services import support
            return frozenset(PERMISSIONS) if support.is_active() else frozenset()
        if self.role is None:
            return frozenset()
        return frozenset(self.role.permissions or ())

    def has_permission(self, permission: str) -> bool:
        """True if this officer's group role grants *permission*."""
        return permission in self.permissions

    def can_grant(self, role) -> bool:
        """An officer may only assign roles whose permissions they hold."""
        return set(role.permissions or ()) <= self.permissions

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    @property
    def role_name(self) -> str:
        if self.is_superadmin:
            return 'Superadmin'
        return self.role.name if self.role else 'No role'

    @property
    def badge_class(self) -> str:
        """CSS modifier for the existing role-badge styles."""
        if self.is_superadmin or self.has_permission('manage_users'):
            return 'admin'
        if self.has_permission('upload_data'):
            return 'clerk'
        return 'viewer'

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f'<User {self.email!r} group={self.group_id} role={self.role_name!r}>'
