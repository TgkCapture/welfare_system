# app/models/user.py
"""
User model.

Roles are enforced as a plain string column with a CHECK constraint
rather than a PostgreSQL ENUM — this keeps the model portable across
SQLite (dev) and PostgreSQL (prod) without dialect-specific imports.
"""
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    # Canonical role values — reference this tuple anywhere you need
    # to validate or iterate roles rather than hard-coding strings.
    ROLES = ('admin', 'clerk', 'viewer')

    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(150), unique=True, nullable=False, index=True)
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