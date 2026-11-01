# app/controllers/auth_controller.py
from datetime import timedelta
from flask import render_template, redirect, url_for, request, flash, current_app
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.auth.forms import LoginForm
from app.models.user import User

SESSION_TIMEOUT = 1800  # seconds


class AuthController:
    """Handles authentication: login and logout only.
    
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
