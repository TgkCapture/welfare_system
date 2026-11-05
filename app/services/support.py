# app/services/support.py
"""
Support sessions: a platform superadmin looking at a group's screens.

A superadmin starts a session from the group's platform page and must give
a reason. For the length of the session (SUPPORT_SESSION_MINUTES) they see
the group's screens as an officer holding every permission would, but
**read-only**: any form they submit is refused. The start, every page they
open, and the end are written to that group's audit log, so the group's
officers can see exactly what was looked at and why.

The session lives in the superadmin's signed cookie session, so it ends
when they log out.
"""
from datetime import datetime, timedelta

from flask import current_app, has_request_context, session
from flask_login import current_user

_KEY = 'support'


def _ttl() -> timedelta:
    return timedelta(minutes=current_app.config.get('SUPPORT_SESSION_MINUTES', 60))


def _raw():
    if not has_request_context() or not current_user or not current_user.is_authenticated:
        return None
    if not current_user.is_superadmin:
        return None
    return session.get(_KEY)


def active_group_id():
    """The group being supported, or None (also once the session has run out)."""
    data = _raw()
    if not data or expired(data):
        return None
    return data['group_id']


def expired(data) -> bool:
    return datetime.utcnow() >= datetime.fromisoformat(data['started']) + _ttl()


def is_active() -> bool:
    return active_group_id() is not None


def info():
    """What the banner shows: the group, the reason and when it runs out."""
    data = _raw()
    if not data or expired(data):
        return None
    from app.extensions import db
    from app.models.group import Group
    return {
        'group': db.session.get(Group, data['group_id']),
        'reason': data['reason'],
        'ends_at': datetime.fromisoformat(data['started']) + _ttl(),
    }


def start(group, reason: str):
    from app.services import audit

    session[_KEY] = {'group_id': group.id, 'reason': reason, 'started': datetime.utcnow().isoformat()}
    audit.record('support.start', f'Platform support opened a read-only session: {reason}',
                 group_id=group.id, details={'reason': reason}, in_support=True)


def end(why: str = 'ended'):
    """Close the session, if there is one. *why* is 'ended' or 'expired'."""
    from app.services import audit

    data = session.pop(_KEY, None)
    if not data:
        return None
    summary = ('Platform support session ended' if why == 'ended'
               else 'Platform support session ran out')
    audit.record('support.end', summary, group_id=data['group_id'], in_support=True)
    return data['group_id']


def pending_expiry():
    """True if a session is stored but has run out (it still needs an 'end' entry)."""
    data = _raw()
    return bool(data) and expired(data)


# Requests a support session may make without them being logged or refused
_ALWAYS_ALLOWED = {'static', 'auth.logout', 'platform.end_support'}
_READ_METHODS = {'GET', 'HEAD', 'OPTIONS'}


def guard():
    """Run before every request (registered in create_app).

    Closes a session that has run out, refuses anything but reading while
    one is open, and logs each group page the superadmin opens.
    """
    from flask import flash, redirect, request, url_for

    from app.services import audit

    if pending_expiry():
        end('expired')
        flash('Your support session ran out.', 'info')
        if request.blueprint != 'platform' and request.endpoint not in _ALWAYS_ALLOWED:
            return redirect(url_for('platform.dashboard'))
        return None

    if not is_active() or request.endpoint in _ALWAYS_ALLOWED or request.blueprint == 'platform':
        return None

    if request.method not in _READ_METHODS:
        flash('Support sessions are read-only: nothing was changed.', 'warning')
        return redirect(url_for('main.dashboard'))

    if request.blueprint != 'group':   # the group's public pages are public anyway
        audit.record('support.view', f'Viewed {request.path}', details={'path': request.full_path.rstrip('?')})
    return None
