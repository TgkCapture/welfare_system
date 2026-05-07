# app/controllers/auth_controller.py
from datetime import timedelta
from flask import render_template, redirect, url_for, request, flash, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.auth.forms import LoginForm, RegisterForm
from app.decorators.permissions import role_required
from app.models.user import User

SESSION_TIMEOUT = 1800  # seconds


class AuthController:
    """Handles authentication: login, logout, and registration only.
    
    Profile management, password changes, data export and account
    """

    # ==================== LOGIN / LOGOUT ====================

    @staticmethod
    def login():
        """Render login page and handle submission."""
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))

        form = LoginForm()
        if form.validate_on_submit():
            return AuthController._process_login(form)

        return render_template('auth/login.html', form=form)

    @staticmethod
    def _process_login(form):
        """Validate credentials and log the user in."""
        user = User.query.filter_by(email=form.email.data).first()

        # Single generic message prevents user enumeration
        if not user or not check_password_hash(user.password, form.password.data):
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('auth.login'))

        if not user.is_active:
            flash(
                'Your account has been deactivated. '
                'Please contact an administrator.',
                'danger'
            )
            return redirect(url_for('auth.login'))

        # Stamp last-login before committing so it is always accurate
        user.last_login = db.func.current_timestamp()
        db.session.commit()

        login_user(
            user,
            remember=form.remember.data,
            duration=timedelta(seconds=SESSION_TIMEOUT)
        )

        flash('Logged in successfully!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('main.dashboard'))

    @staticmethod
    @login_required
    def logout():
        """Log the current user out."""
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('auth.login'))

    # ==================== REGISTRATION ====================

    @staticmethod
    @role_required('admin')
    def register():
        """Admin-only: create any role account."""
        form = RegisterForm()
        form.role.choices = [
            ('admin', 'Administrator'),
            ('clerk', 'Clerk'),
            ('viewer', 'Viewer'),
        ]

        if form.validate_on_submit():
            return AuthController._process_registration(form, force_role=None)

        return render_template('auth/register.html', form=form)

    @staticmethod
    def public_register():
        """Public self-registration — always creates a Viewer account."""
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))

        form = RegisterForm()
        # Hide role field from public users; it is forced server-side
        form.role.choices = [('viewer', 'Viewer')]
        form.role.data = 'viewer'

        if form.validate_on_submit():
            return AuthController._process_registration(form, force_role='viewer')

        return render_template('auth/register.html', form=form)

    @staticmethod
    def _process_registration(form, force_role=None):
        """Create a new user.
        """
        if User.query.filter_by(email=form.email.data).first():
            flash('That email address is already registered.', 'danger')
            return redirect(url_for('auth.login'))

        role = force_role or form.role.data

        try:
            new_user = User(
                email=form.email.data,
                password=generate_password_hash(form.password.data, method='scrypt'),
                role=role,
            )
            db.session.add(new_user)
            db.session.commit()

            flash(
                f'Account for {new_user.email} created successfully as {new_user.role}.',
                'success'
            )

            # Admins land back on the user list; public registrants go to login
            if current_user.is_authenticated and current_user.is_admin:
                return redirect(url_for('main.admin_users'))
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration failed for {form.email.data}: {e}")
            flash(f'Registration failed: {str(e)}', 'danger')
            return redirect(url_for('auth.register'))