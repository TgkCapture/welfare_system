# app/controllers/user_controller.py
"""
User management for admins and clerks.

Role boundaries:
  - Admin  : full CRUD on all roles (admin, clerk, viewer)
  - Clerk  : create / edit / toggle viewers only — cannot touch admins or clerks
  - Viewer : no access to any endpoint here
"""
from flask import current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from app.auth.forms import RegisterForm, UserEditForm
from app.decorators.permissions import role_required
from app.extensions import db
from app.models.user import User


class UserController:
    """Handles user management business logic."""

    # ==================== ADMIN — LIST ====================

    @staticmethod
    @role_required('admin')
    def admin_users():
        """List all users (admin only)."""
        users = User.query.order_by(User.created_at.desc()).all()

        return render_template(
            'main/admin_users.html',
            version=current_app.version,
            users=users,
            current_user=current_user,
        )

    # ==================== ADMIN — CREATE ====================

    @staticmethod
    @role_required('admin')
    def create_user():
        """Create a user of any role (admin only)."""
        form = RegisterForm()
        form.role.choices = [
            ('admin', 'Administrator'),
            ('clerk', 'Clerk'),
            ('viewer', 'Viewer'),
        ]

        if form.validate_on_submit():
            return UserController._create_user(
                email=form.email.data,
                password=form.password.data,
                role=form.role.data,
                success_redirect=url_for('main.admin_users'),
                failure_redirect=url_for('main.create_user'),
            )

        return render_template(
            'main/create_user.html',
            version=current_app.version,
            form=form,
            is_admin=True,
        )

    # ==================== ADMIN — EDIT ====================

    @staticmethod
    @role_required('admin')
    def edit_user(user_id):
        """Edit any user (admin only). Self-edits redirected to profile."""
        user = User.query.get_or_404(user_id)

        if user.id == current_user.id:
            flash('Use your profile page to edit your own account.', 'info')
            return redirect(url_for('auth.profile'))

        form = UserEditForm(obj=user)
        form.role.choices = [
            ('admin', 'Administrator'),
            ('clerk', 'Clerk'),
            ('viewer', 'Viewer'),
        ]

        if form.validate_on_submit():
            # Check if email has changed
            email_changed = form.email.data != user.email
            
            # Only validate email uniqueness if it has changed
            if email_changed:
                # FIX: Used clean filter operations to avoid matching the current user
                conflict = User.query.filter(
                    (User.email == form.email.data) & (User.id != user.id)
                ).first()
                
                if conflict:
                    flash('That email address is already in use.', 'danger')
                    return redirect(url_for('main.edit_user', user_id=user_id))

            try:
                user.email = form.email.data
                user.role = form.role.data
                user.is_active = form.is_active.data
                db.session.commit()

                flash(f'User {user.email} updated successfully.', 'success')
                return redirect(url_for('main.admin_users'))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating user {user_id}: {e}")
                flash(f'Update failed: {str(e)}', 'danger')

        return render_template(
            'main/edit_user.html',
            form=form,
            user=user,
            version=current_app.version,
            is_admin=True,
        )

    # ==================== ADMIN — DELETE ====================

    @staticmethod
    @role_required('admin')
    def delete_user(user_id):
        """Permanently delete a user (admin only). Self-deletion blocked."""
        user = User.query.get_or_404(user_id)

        if user.id == current_user.id:
            flash('You cannot delete your own account.', 'danger')
            return redirect(url_for('main.admin_users'))

        # Prevent deleting the last admin — system would be unrecoverable
        if user.role == 'admin':
            remaining_admins = User.query.filter_by(
                role='admin', is_active=True
            ).count()
            if remaining_admins <= 1:
                flash(
                    'Cannot delete the last active admin account.',
                    'danger'
                )
                return redirect(url_for('main.admin_users'))

        try:
            email = user.email
            db.session.delete(user)
            db.session.commit()
            flash(f'User {email} deleted successfully.', 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting user {user_id}: {e}")
            flash(f'Deletion failed: {str(e)}', 'danger')

        return redirect(url_for('main.admin_users'))

    # ==================== ADMIN — TOGGLE ACTIVE ====================

    @staticmethod
    @role_required('admin')
    def toggle_user_active(user_id):
        """Toggle active status for any user (admin only). Self-toggle blocked."""
        user = User.query.get_or_404(user_id)

        if user.id == current_user.id:
            flash('You cannot deactivate your own account.', 'danger')
            return redirect(url_for('main.admin_users'))

        # Prevent deactivating the last active admin
        if user.role == 'admin' and user.is_active:
            remaining_admins = User.query.filter_by(
                role='admin', is_active=True
            ).count()
            if remaining_admins <= 1:
                flash(
                    'Cannot deactivate the last active admin account.',
                    'danger'
                )
                return redirect(url_for('main.admin_users'))

        try:
            user.is_active = not user.is_active
            db.session.commit()

            status = 'activated' if user.is_active else 'deactivated'
            flash(f'User {user.email} {status} successfully.', 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error toggling user {user_id}: {e}")
            flash(f'Update failed: {str(e)}', 'danger')

        return redirect(url_for('main.admin_users'))

    # ==================== CLERK — LIST ====================

    @staticmethod
    @role_required('clerk')
    def clerk_users():
        """List viewer accounts (clerk only)."""
        viewers = (
            User.query
            .filter_by(role='viewer')
            .order_by(User.created_at.desc())
            .all()
        )

        return render_template(
            'main/clerk_users.html',
            version=current_app.version,
            users=viewers,
            current_user=current_user,
        )

    # ==================== CLERK — CREATE VIEWER ====================

    @staticmethod
    @role_required('clerk')
    def create_viewer():
        """Create a viewer account (clerk only — role is forced server-side)."""
        form = RegisterForm()
        form.role.choices = [('viewer', 'Viewer')]
        form.role.data = 'viewer'

        if form.validate_on_submit():
            return UserController._create_user(
                email=form.email.data,
                password=form.password.data,
                role='viewer',                         # always forced — never trust form.role
                success_redirect=url_for('main.clerk_users'),
                failure_redirect=url_for('main.create_viewer'),
            )

        return render_template(
            'main/create_user.html',
            version=current_app.version,
            form=form,
            is_admin=False,
        )

    # ==================== CLERK — EDIT VIEWER ====================

    @staticmethod
    @role_required('clerk')
    def edit_viewer(user_id):
        """Edit a viewer account (clerk only). Non-viewers are blocked."""
        user = User.query.get_or_404(user_id)

        if user.role != 'viewer':
            flash('You can only edit viewer accounts.', 'danger')
            return redirect(url_for('main.clerk_users'))

        form = UserEditForm(obj=user)
        form.role.choices = [('viewer', 'Viewer')]

        if form.validate_on_submit():
            # Check if email has changed
            email_changed = form.email.data != user.email
            
            # Only validate email uniqueness if it has changed
            if email_changed:
                conflict = User.query.filter(
                    (User.email == form.email.data) & (User.id != user.id)
                ).first()
                
                if conflict:
                    flash('That email address is already in use.', 'danger')
                    return redirect(url_for('main.edit_viewer', user_id=user_id))

            try:
                user.email = form.email.data
                user.is_active = form.is_active.data
                # Role is intentionally not updated — clerks cannot promote viewers
                db.session.commit()

                flash(f'Viewer {user.email} updated successfully.', 'success')
                return redirect(url_for('main.clerk_users'))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error editing viewer {user_id}: {e}")
                flash(f'Update failed: {str(e)}', 'danger')

        return render_template(
            'main/edit_user.html',
            form=form,
            user=user,
            version=current_app.version,
            is_admin=False,
        )

    # ==================== CLERK — TOGGLE VIEWER ACTIVE ====================

    @staticmethod
    @role_required('clerk')
    def toggle_viewer_active(user_id):
        """Toggle active status for a viewer (clerk only)."""
        user = User.query.get_or_404(user_id)

        if user.role != 'viewer':
            flash('You can only manage viewer accounts.', 'danger')
            return redirect(url_for('main.clerk_users'))

        try:
            user.is_active = not user.is_active
            db.session.commit()

            status = 'activated' if user.is_active else 'deactivated'
            flash(f'Viewer {user.email} {status} successfully.', 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error toggling viewer {user_id}: {e}")
            flash(f'Update failed: {str(e)}', 'danger')

        return redirect(url_for('main.clerk_users'))

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _create_user(email, password, role, success_redirect, failure_redirect):
        """Shared user creation logic used by both admin and clerk flows.

        Args:
            email:             Email address for the new account.
            password:          Plain-text password (will be hashed here).
            role:              Role string — callers are responsible for
                               passing a safe, server-validated value.
            success_redirect:  Where to redirect on success.
            failure_redirect:  Where to redirect if the email is taken.
        """
        if User.query.filter_by(email=email).first():
            flash('That email address is already registered.', 'danger')
            return redirect(failure_redirect)

        try:
            new_user = User(
                email=email,
                password=generate_password_hash(password, method='scrypt'),
                role=role,
            )
            db.session.add(new_user)
            db.session.commit()

            flash(
                f'{"Viewer" if role == "viewer" else "User"} {new_user.email} '
                f'created successfully as {new_user.role}.',
                'success',
            )
            return redirect(success_redirect)

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating user {email}: {e}")
            flash(f'User creation failed: {str(e)}', 'danger')
            return redirect(failure_redirect)