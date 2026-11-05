# app/services/audit.py
"""
Writing and reading the audit log (see app/models/audit.py).

Controllers call ``record()`` right after a change succeeds:

    audit.record('member.rename', f'Renamed {old} to {member.display_name}',
                 details={'member_id': member.id})

The group, the officer, their IP address and whether this is a support
session are filled in from the request. ``record()`` commits, so the entry
is kept even if the caller has already committed its own change.
"""
from flask import has_request_context, request
from flask_login import current_user

from app.extensions import db
from app.models.audit import AuditEvent
from app.models.tenancy import current_group_id

# Action prefix → label, for the filter on the audit log page
AREAS = {
    'auth':     'Sign-ins',
    'settings': 'Settings',
    'workbook': 'Workbook and layout',
    'sync':     'Uploads and syncs',
    'rules':    'Welfare rules',
    'member':   'Members, links and PINs',
    'officer':  'Officers',
    'role':     'Roles',
    'report':   'Reports',
    'storage':  'Storage',
    'group':    'Group (platform)',
    'support':  'Platform support',
}

# Area → Font Awesome icon, for the timeline
ICONS = {
    'auth': 'right-to-bracket', 'settings': 'gear', 'workbook': 'file-excel', 'sync': 'rotate',
    'rules': 'book-open', 'member': 'user', 'officer': 'user-gear', 'role': 'id-badge',
    'report': 'file-lines', 'storage': 'hdd', 'group': 'layer-group', 'support': 'life-ring',
}

PER_PAGE = 50


def record(action: str, summary: str, *, group_id=None, details=None, actor=None,
           user_id=None, in_support=None, commit=True) -> AuditEvent:
    """Add an entry to the audit log.

    *group_id* defaults to the current group, except on platform pages,
    which name the group they act on (None there is a platform-wide event).
    *actor* and *user_id* default to the signed-in officer (pass *actor*
    for sign-in attempts, where nobody is signed in yet).
    """
    from app.services import support

    signed_in = has_request_context() and current_user and current_user.is_authenticated
    on_platform = has_request_context() and request.blueprint == 'platform'
    if group_id is None and not on_platform:
        group_id = current_group_id()
    if actor is None:
        actor = current_user.email if signed_in else 'system'
    if user_id is None and signed_in:
        user_id = current_user.id
    if in_support is None:
        in_support = support.is_active() and not on_platform

    event = AuditEvent(
        group_id=group_id, user_id=user_id, actor=actor[:255], action=action,
        summary=summary[:500], details=details or None, in_support=in_support,
        ip_address=_client_ip(),
    )
    db.session.add(event)
    if commit:
        db.session.commit()
    return event


def events(group_id=None, *, area=None, user_id=None, page=1, all_groups=False):
    """A page of entries, newest first, as a Flask-SQLAlchemy pagination."""
    query = AuditEvent.query if all_groups else AuditEvent.for_group(group_id)  # platform-wide: callers check
    if all_groups and group_id:
        query = query.filter(AuditEvent.group_id == group_id)
    if area in AREAS:
        query = query.filter(AuditEvent.action.like(f'{area}.%'))
    if user_id:
        query = query.filter(AuditEvent.user_id == user_id)
    return query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()) \
        .paginate(page=page, per_page=PER_PAGE, error_out=False)


def _client_ip():
    # request.remote_addr is the proxy's address unless ProxyFix is set up
    # (see TRUSTED_PROXIES in config); never read X-Forwarded-For directly.
    return request.remote_addr if has_request_context() else None
