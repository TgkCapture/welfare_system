# app/controllers/auth_controller.py
"""
Authentication.

Officers sign in on their group's own page, /g/<slug>/login, which looks
the email up within that group only. Platform superadmins sign in at
/platform/login. /auth/login helps people find their group's page.
"""
from datetime import timedelta
from urllib.parse import urlsplit

from flask import (
    abort, current_app, flash, redirect, render_template, request, url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth.forms import LoginForm
from app.controllers.report_controller import ReportController
from app.extensions import db, limiter
from app.models.group import Group
from app.models.user import User

SESSION_TIMEOUT = 1800  # seconds

# Remembers the last group signed into, so /auth/login can go straight there
LAST_GROUP_COOKIE = 'last_group'
LAST_GROUP_MAX_AGE = 365 * 24 * 3600

# Checked when no account matches, so a wrong email takes as long as a
# wrong password and response times don't reveal which emails exist
_DUMMY_HASH = generate_password_hash('not-a-real-password', method='scrypt')


def _login_rate_limit() -> str:
    return current_app.config['LOGIN_RATE_LIMIT']


# One budget per client IP across every login form
_limit_logins = limiter.shared_limit(_login_rate_limit, scope='login', methods=['POST'])


def safe_next_url(target):
    """Return *target* only if it is a path on this site, else None.

    Prevents open redirects such as ?next=https://evil.example.
    """
    if not target or not target.startswith('/') or target.startswith('//'):
        return None
    if '\\' in target:
        return None
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return None
    return target


class AuthController:
    """Handles authentication: group finder, logins and logout."""

    # ==================== GROUP FINDER ====================

    @staticmethod
    def login():
        """Send the visitor to their group's login page."""
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))

        next_url = safe_next_url(request.args.get('next'))

        if request.method == 'POST':
            slug = request.form.get('group', '').strip().lower()
            if Group.query.filter_by(slug=slug, is_active=True).first():
                return redirect(url_for('group.login', slug=slug, next=next_url))
            flash("We couldn't find an active group with that code.", 'danger')
        else:
            slug = request.cookies.get(LAST_GROUP_COOKIE)
            if slug and Group.query.filter_by(slug=slug, is_active=True).first():
                return redirect(url_for('group.login', slug=slug, next=next_url))

        return render_template('auth/find_group.html', next=next_url)

    # ==================== GROUP LOGIN ====================

    @staticmethod
    @_limit_logins
    def group_login(slug):
        """Officer login for one group."""
        group = Group.query.filter_by(slug=slug, is_active=True).first()
        if group is None:
            abort(404)

        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))

        next_url = safe_next_url(request.args.get('next'))
        form = LoginForm()

        if form.validate_on_submit():
            user = User.for_group(group.id).filter_by(email=form.email.data.strip()).first()
            if AuthController._complete_login(user, form):
                response = redirect(next_url or url_for('main.dashboard'))
                response.set_cookie(
                    LAST_GROUP_COOKIE, group.slug, max_age=LAST_GROUP_MAX_AGE,
                    httponly=True, samesite='Lax',
                    secure=current_app.config.get('SESSION_COOKIE_SECURE', False),
                )
                return response
            return redirect(url_for('group.login', slug=slug, next=next_url))

        return render_template(
            'auth/login.html', form=form, group=group,
            action=url_for('group.login', slug=slug, next=next_url),
        )

    # ==================== PLATFORM LOGIN ====================

    @staticmethod
    @_limit_logins
    def platform_login():
        """Superadmin login."""
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))

        next_url = safe_next_url(request.args.get('next'))
        form = LoginForm()

        if form.validate_on_submit():
            user = User.query.filter_by(  # platform-wide: superadmins have no group
                is_superadmin=True, email=form.email.data.strip(),
            ).first()
            if AuthController._complete_login(user, form):
                return redirect(next_url or url_for('platform.dashboard'))
            return redirect(url_for('platform.login', next=next_url))

        return render_template(
            'auth/login.html', form=form, group=None,
            action=url_for('platform.login', next=next_url),
        )

    # ==================== LOGOUT ====================

    @staticmethod
    @login_required
    def logout():
        """Log the current user out and return them to their own login page."""
        group, is_superadmin = current_user.group, current_user.is_superadmin
        ReportController.clear_session_report()
        logout_user()
        flash('You have been logged out.', 'info')

        if group is not None:
            return redirect(url_for('group.login', slug=group.slug))
        if is_superadmin:
            return redirect(url_for('platform.login'))
        return redirect(url_for('auth.login'))

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _complete_login(user, form) -> bool:
        """Check credentials and log *user* in. Flashes and returns False on failure."""
        password_ok = check_password_hash(
            user.password if user else _DUMMY_HASH, form.password.data,
        )

        # Single generic message prevents user enumeration
        if not user or not password_ok:
            flash('Invalid email or password.', 'danger')
            return False

        if not user.is_active:
            flash(
                'Your account has been deactivated. '
                'Please contact an officer of your group.',
                'danger'
            )
            return False

        # Stamp last-login before committing so it is always accurate
        user.last_login = db.func.current_timestamp()
        db.session.commit()

        ReportController.clear_session_report()
        login_user(
            user,
            remember=form.remember.data,
            duration=timedelta(seconds=SESSION_TIMEOUT)
        )
        flash('Logged in successfully!', 'success')
        return True
