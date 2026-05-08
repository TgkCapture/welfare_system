# app/decorators/permissions.py
"""
Role and permission decorators.
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


def role_required(*roles):
    """Restrict a view to users whose role is in *roles*.

    Usage::

        @role_required('admin')
        def admin_only_view(): ...

        @role_required('admin', 'clerk')
        def admin_or_clerk_view(): ...
    """
    # Flatten: allow both @role_required('admin') and
    # @role_required('admin', 'clerk') and @role_required(['admin'])
    allowed = set()
    for r in roles:
        if isinstance(r, (list, tuple)):
            allowed.update(r)
        else:
            allowed.add(r)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'info')
                return redirect(url_for('auth.login'))

            if not current_user.is_active:
                flash('Your account has been deactivated.', 'danger')
                return redirect(url_for('auth.login'))

            if current_user.role not in allowed:
                return _deny(
                    f"You need {' or '.join(sorted(allowed))} access "
                    f"to reach this page."
                )

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def permission_required(permission: str):
    """Restrict a view to users whose role grants *permission*.

    The permission map lives on ``User.has_permission()`` — see
    ``app/models/user.py``.

    Usage::

        @permission_required('upload_files')
        def upload_view(): ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'info')
                return redirect(url_for('auth.login'))

            if not current_user.is_active:
                flash('Your account has been deactivated.', 'danger')
                return redirect(url_for('auth.login'))

            if not current_user.has_permission(permission):
                return _deny(
                    f"You do not have permission to perform this action."
                )

            return fn(*args, **kwargs)
        return wrapper
    return decorator