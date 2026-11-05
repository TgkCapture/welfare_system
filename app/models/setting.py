# app/models/setting.py
"""
Key-value settings store.

Used for system-wide configuration that needs to be editable at
runtime without a redeploy (e.g. Google Sheets URL, retention days).
"""
from app.extensions import db


class Setting(db.Model):
    __tablename__ = 'settings'

    id    = db.Column(db.Integer, primary_key=True)
    key   = db.Column(db.String(100), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    # ------------------------------------------------------------------
    # Class-level helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_value(cls, key: str, default=None):
        """Return the stored value for *key*, or *default* if not set."""
        setting = cls.query.filter_by(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set_value(cls, key: str, value) -> 'Setting':
        """Upsert *key* = *value*.

        Commits the session — callers do not need to call
        ``db.session.commit()`` themselves.

        Returns the Setting instance.
        """
        setting = cls.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = cls(key=key, value=value)
            db.session.add(setting)

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return setting

    @classmethod
    def delete_key(cls, key: str) -> bool:
        """Remove a setting by key. Returns True if it existed."""
        setting = cls.query.filter_by(key=key).first()
        if setting:
            db.session.delete(setting)
            db.session.commit()
            return True
        return False

    @classmethod
    def get_all(cls) -> dict:
        """Return all settings as a plain {key: value} dict."""
        return {s.key: s.value for s in cls.query.all()}

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f'<Setting {self.key!r}>'