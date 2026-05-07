# app/controllers/profile_controller.py
"""
Profile management extracted from AuthController.
"""
import csv
import io
import json
from datetime import datetime

from flask import (
    current_app, make_response, redirect, render_template,
    request, flash, url_for,
)
from flask_login import current_user, login_required, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.auth.forms import ChangePasswordForm, ProfileForm
from app.models.user import User
from app.models.setting import Setting
from app.models.report import GeneratedReport


class ProfileController:
    """All profile-related actions for the currently logged-in user."""

    # ==================== PROFILE VIEW ====================

    @staticmethod
    @login_required
    def profile():
        """Render the profile page with stats, activity and preference forms."""
        user = User.query.get(current_user.id)
        stats = ProfileController._get_user_statistics(user)
        recent_activity = ProfileController._get_user_activity(user)

        notification_preferences = (
            Setting.get_value(f'user_{user.id}_notifications', 'true') == 'true'
        )
        theme_preference = Setting.get_value(f'user_{user.id}_theme', 'light')

        password_form = ChangePasswordForm()
        profile_form = ProfileForm(obj=user)

        return render_template(
            'auth/profile.html',
            user=user,
            password_form=password_form,
            profile_form=profile_form,
            **stats,
            recent_activity=recent_activity,
            notification_preferences=notification_preferences,
            theme_preference=theme_preference,
            version=current_app.version,
        )

    # ==================== PROFILE UPDATE ====================

    @staticmethod
    @login_required
    def update_profile():
        """Handle profile info update (email + preferences)."""
        user = User.query.get(current_user.id)
        email = request.form.get('email', '').strip()

        if not email:
            flash('Email is required.', 'danger')
            return redirect(url_for('auth.profile'))

        # Ensure email is not already taken by a *different* account
        conflict = User.query.filter(
            User.email == email,
            User.id != user.id
        ).first()
        if conflict:
            flash('That email address is already in use.', 'danger')
            return redirect(url_for('auth.profile'))

        user.email = email

        notification_preferences = request.form.get('notification_preferences') == 'on'
        theme_preference = request.form.get('theme_preference', 'light')
        Setting.set_value(
            f'user_{user.id}_notifications',
            'true' if notification_preferences else 'false'
        )
        Setting.set_value(f'user_{user.id}_theme', theme_preference)

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))

    # ==================== PASSWORD CHANGE ====================

    @staticmethod
    @login_required
    def change_password():
        """Handle password change form submission."""
        user = User.query.get(current_user.id)

        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([current_password, new_password, confirm_password]):
            flash('All password fields are required.', 'danger')
            return redirect(url_for('auth.profile'))

        if not check_password_hash(user.password, current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('auth.profile'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('auth.profile'))

        if len(new_password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return redirect(url_for('auth.profile'))

        user.password = generate_password_hash(new_password, method='scrypt')
        db.session.commit()
        flash('Password updated. Please log in again.', 'success')
        return redirect(url_for('auth.logout'))

    # ==================== ACTIVITY LOG ====================

    @staticmethod
    @login_required
    def activity_log():
        """Render the full activity log for the current user."""
        user = User.query.get(current_user.id)
        activity_data = Setting.get_value(f'user_{user.id}_activity', '[]')

        try:
            activities = json.loads(activity_data)
        except (json.JSONDecodeError, TypeError):
            activities = ProfileController._get_user_activity(user)

        return render_template(
            'auth/activity_log.html',
            activities=activities,
            user=user,
            now=datetime.now(),
            version=current_app.version,
        )

    # ==================== DATA EXPORT ====================

    @staticmethod
    @login_required
    def export_data():
        """Export the current user's profile data as a CSV download."""
        user = User.query.get(current_user.id)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Data Type', 'Field', 'Value'])

        writer.writerow(['Profile', 'Email', user.email])
        writer.writerow(['Profile', 'Role', user.role])
        writer.writerow(['Profile', 'Account Created', user.created_at])
        writer.writerow(['Profile', 'Last Login', user.last_login or 'Never'])
        writer.writerow([
            'Profile', 'Account Status',
            'Active' if user.is_active else 'Inactive'
        ])

        notifications = Setting.get_value(f'user_{user.id}_notifications', 'true')
        theme = Setting.get_value(f'user_{user.id}_theme', 'light')
        writer.writerow([
            'Preferences', 'Notifications',
            'Enabled' if notifications == 'true' else 'Disabled'
        ])
        writer.writerow(['Preferences', 'Theme', theme])

        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = (
            f'attachment; filename=user_data_{user.id}'
            f'_{datetime.now().strftime("%Y%m%d")}.csv'
        )
        return response

    # ==================== ACCOUNT DELETION ====================

    @staticmethod
    @login_required
    def delete_account():
        """Allow a non-admin user to permanently delete their own account."""
        if current_user.is_admin:
            flash('Admin accounts cannot be deleted through this interface.', 'danger')
            return redirect(url_for('auth.profile'))

        if request.form.get('confirm_text', '') != 'DELETE':
            flash('Please type "DELETE" to confirm account deletion.', 'danger')
            return redirect(url_for('auth.profile'))

        user = User.query.get(current_user.id)

        try:
            # Log out AFTER the delete succeeds, not before
            db.session.delete(user)
            db.session.commit()
            logout_user()
            flash('Your account has been deleted.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Account deletion failed for user {user.id}: {e}")
            flash(f'Account deletion failed: {str(e)}', 'danger')
            return redirect(url_for('auth.profile'))

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _get_user_statistics(user):
        """Return a dict of stats for the profile page."""
        days_active = max((datetime.now() - user.created_at).days, 0) + 1

        # Real count from the database instead of guessing from session
        reports_generated = 0
        if user.role in ('admin', 'clerk'):
            reports_generated = GeneratedReport.query.filter_by(
                generated_by=user.id
            ).count()

        return {
            'reports_generated': reports_generated,
            'days_active': days_active,
        }

    @staticmethod
    def _get_user_activity(user):
        """Build a minimal activity list from known timestamps."""
        activities = []

        if user.last_login:
            activities.append({
                'icon': 'sign-in-alt',
                'description': 'Last login',
                'timestamp': user.last_login.strftime('%B %d, %Y %I:%M %p'),
            })

        activities.append({
            'icon': 'user-plus',
            'description': 'Account created',
            'timestamp': user.created_at.strftime('%B %d, %Y'),
        })

        return activities