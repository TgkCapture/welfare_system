# app/decorators/permissions.py
"""
Permission decorators.

  @permission_required('upload_data')  — group officer whose role grants it
  @superadmin_required                 — platform superadmin

Permission codes are defined in ``app/models/role.py``.
"""
import functools

from flask import flash, jsonify, redirect, request, url_for
from flask_login import current_user


def _wants_json() -> bool:
    """Return True when the client prefers a JSON response."""
    best = request.accept_mimetypes.best_match(
        ['application/json', 'text/html']
    )
    return (
        best == 'application/json'
        and request.accept_mimetypes[best] > request.accept_mimetypes['text/html']
    ) or request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _deny(message: str, status: int = 403):
    """Return a 403 JSON response or redirect to dashboard with a flash."""
    if _wants_json():
        return jsonify({'error': 'Forbidden', 'message': message}), status
    flash(message, 'danger')
    return redirect(url_for('main.dashboard'))


def _require_login():
    """Return a redirect if nobody usable is logged in, else None."""
    if not current_user.is_authenticated:
        flash('Please log in to access this page.', 'info')
        login_page = 'platform.login' if request.blueprint == 'platform' else 'auth.login'
        return redirect(url_for(login_page, next=request.full_path.rstrip('?')))

    if not current_user.is_active:
        flash('Your account has been deactivated.', 'danger')
        return redirect(url_for('auth.login'))

    return None


def permission_required(permission: str):
    """Restrict a view to officers whose group role grants *permission*.

    Usage::

        @permission_required('upload_data')
        def upload_view(): ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            denied = _require_login()
            if denied:
                return denied

            if not current_user.has_permission(permission):
                return _deny('You do not have permission to perform this action.')

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def superadmin_required(fn):
    """Restrict a view to platform superadmins."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        denied = _require_login()
        if denied:
            return denied

        if not current_user.is_superadmin:
            return _deny('This page is for platform administrators only.')

        return fn(*args, **kwargs)
    return wrapper
