# app/models/user.py
"""
User model — officer accounts.

An officer belongs to exactly one group (``group_id``) and holds one of
that group's roles (``role_id``). Email is unique within a group, so the
same person may hold separate, unrelated accounts in different groups.

Platform superadmins have ``is_superadmin`` set and no group.

Transitional: the legacy ``role`` string (admin/clerk/viewer) still drives
permission checks until step 1b switches them to ``group_role``.
"""
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = (
        db.UniqueConstraint('group_id', 'email', name='uq_users_group_email'),
    )

    # Canonical role values — reference this tuple anywhere you need
    # to validate or iterate roles rather than hard-coding strings.
    ROLES = ('admin', 'clerk', 'viewer')

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
    role       = db.Column(
        db.String(20),
        nullable=False,
        default='viewer',
        server_default='viewer',
    )
    is_active  = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        server_default=db.func.current_timestamp(),
    )
    last_login = db.Column(db.DateTime, nullable=True)

    group      = db.relationship('Group', back_populates='users')
    # Named group_role while the legacy `role` string column still exists
    group_role = db.relationship('Role')

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
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def validate_role(role: str) -> None:
        """Raise ValueError if *role* is not a recognised value."""
        if role not in User.ROLES:
            raise ValueError(
                f"Invalid role '{role}'. Must be one of: {User.ROLES}"
            )

    # ------------------------------------------------------------------
    # Role helpers
    # ------------------------------------------------------------------

    @property
    def is_admin(self) -> bool:
        return self.role == 'admin'

    @property
    def is_clerk(self) -> bool:
        return self.role == 'clerk'

    @property
    def is_viewer(self) -> bool:
        return self.role == 'viewer'

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------

    # Single source of truth for role → permissions mapping.
    # Use frozenset so membership checks are O(1).
    _ROLE_PERMISSIONS: dict = {
        'admin': frozenset([
            'manage_users', 'upload_files', 'view_reports',
            'download_reports', 'manage_settings', 'cleanup_files',
        ]),
        'clerk': frozenset([
            'upload_files', 'view_reports', 'download_reports',
        ]),
        'viewer': frozenset([
            'view_reports',
        ]),
    }

    def has_permission(self, permission: str) -> bool:
        """Return True if this user's role grants *permission*."""
        return permission in self._ROLE_PERMISSIONS.get(self.role, frozenset())

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f'<User {self.email!r} role={self.role!r}>'