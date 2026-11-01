# app/controllers/user_controller.py
"""
Officer management within a group (requires the manage_users permission).

Guardrails:
  - Officers only see and manage accounts in their own group.
  - An officer may only assign, or manage holders of, roles whose
    permissions they hold themselves.
  - A group always keeps at least one active officer with manage_users.
"""
from flask import abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user
from werkzeug.security import generate_password_hash

from app.auth.forms import RegisterForm, UserEditForm
from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.role import Role
from app.models.user import User


class UserController:
    """Handles officer management business logic."""

    # ==================== LIST ====================

    @staticmethod
    @permission_required('manage_users')
    def admin_users():
        """List the officers of the current group."""
        users = (
            User.query
            .filter_by(group_id=current_user.group_id)
            .order_by(User.created_at.desc())
            .all()
        )

        return render_template(
            'main/admin_users.html',
            version=current_app.version,
            users=users,
            roles=UserController._group_roles(),
            current_user=current_user,
        )

    # ==================== CREATE ====================

    @staticmethod
    @permission_required('manage_users')
    def create_user():
        """Create an officer in the current group."""
        form = RegisterForm()
        form.role.choices = UserController._grantable_role_choices()

        if form.validate_on_submit():
            role = UserController._grantable_role(form.role.data)
            try:
                new_user = User(
                    email=form.email.data.strip(),
                    password=generate_password_hash(form.password.data, method='scrypt'),
                    group_id=current_user.group_id,
                    role=role,
                )
                db.session.add(new_user)
                db.session.commit()
                flash(f'Officer {new_user.email} created as {role.name}.', 'success')
                return redirect(url_for('main.admin_users'))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating officer {form.email.data}: {e}")
                flash(f'Officer creation failed: {str(e)}', 'danger')

        return render_template(
            'main/create_user.html',
            version=current_app.version,
            form=form,
        )

    # ==================== EDIT ====================

    @staticmethod
    @permission_required('manage_users')
    def edit_user(user_id):
        """Edit an officer's email, role and active status."""
        user = UserController._manageable_officer(user_id)
        if user.id == current_user.id:
            flash('Use your profile page to edit your own account.', 'info')
            return redirect(url_for('auth.profile'))

        form = UserEditForm(obj=user)
        form.role.choices = UserController._grantable_role_choices()
        if not form.is_submitted():
            form.role.data = user.role_id

        if form.validate_on_submit():
            role = UserController._grantable_role(form.role.data)

            if UserController._would_remove_last_manager(
                user, keeps_access=form.is_active.data and role.has('manage_users'),
            ):
                flash(
                    'This is the last active officer who can manage officers. '
                    'Give another officer that permission first.',
                    'danger',
                )
                return redirect(url_for('main.edit_user', user_id=user.id))

            try:
                user.email = form.email.data.strip()
                user.role = role
                user.is_active = form.is_active.data
                db.session.commit()

                flash(f'Officer {user.email} updated successfully.', 'success')
                return redirect(url_for('main.admin_users'))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating officer {user_id}: {e}")
                flash(f'Update failed: {str(e)}', 'danger')

        return render_template(
            'main/edit_user.html',
            form=form,
            user=user,
            version=current_app.version,
        )

    # ==================== DELETE ====================

    @staticmethod
    @permission_required('manage_users')
    def delete_user(user_id):
        """Permanently delete an officer. Self-deletion blocked."""
        user = UserController._manageable_officer(user_id)

        if user.id == current_user.id:
            flash('You cannot delete your own account.', 'danger')
            return redirect(url_for('main.admin_users'))

        if UserController._would_remove_last_manager(user, keeps_access=False):
            flash('Cannot delete the last active officer who can manage officers.', 'danger')
            return redirect(url_for('main.admin_users'))

        try:
            email = user.email
            db.session.delete(user)
            db.session.commit()
            flash(f'Officer {email} deleted successfully.', 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting officer {user_id}: {e}")
            flash(f'Deletion failed: {str(e)}', 'danger')

        return redirect(url_for('main.admin_users'))

    # ==================== TOGGLE ACTIVE ====================

    @staticmethod
    @permission_required('manage_users')
    def toggle_user_active(user_id):
        """Activate or deactivate an officer. Self-toggle blocked."""
        user = UserController._manageable_officer(user_id)

        if user.id == current_user.id:
            flash('You cannot deactivate your own account.', 'danger')
            return redirect(url_for('main.admin_users'))

        if user.is_active and UserController._would_remove_last_manager(user, keeps_access=False):
            flash('Cannot deactivate the last active officer who can manage officers.', 'danger')
            return redirect(url_for('main.admin_users'))

        try:
            user.is_active = not user.is_active
            db.session.commit()

            status = 'activated' if user.is_active else 'deactivated'
            flash(f'Officer {user.email} {status} successfully.', 'success')

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error toggling officer {user_id}: {e}")
            flash(f'Update failed: {str(e)}', 'danger')

        return redirect(url_for('main.admin_users'))

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _group_roles():
        return Role.query.filter_by(group_id=current_user.group_id).order_by(Role.name).all()

    @staticmethod
    def _grantable_role_choices():
        return [(r.id, r.name) for r in UserController._group_roles() if current_user.can_grant(r)]

    @staticmethod
    def _grantable_role(role_id):
        """Return the submitted role, or 403 if the officer may not grant it."""
        role = db.session.get(Role, role_id)
        if role is None or role.group_id != current_user.group_id or not current_user.can_grant(role):
            abort(403)
        return role

    @staticmethod
    def _manageable_officer(user_id):
        """Return an officer of the current group whose role the caller could grant.

        Officers of other groups are reported as not found.
        """
        user = db.session.get(User, user_id)
        if user is None or user.group_id != current_user.group_id:
            abort(404)
        if user.role and not current_user.can_grant(user.role):
            abort(403)
        return user

    @staticmethod
    def _would_remove_last_manager(user, keeps_access: bool) -> bool:
        """True if changing *user* would leave the group with no active manager."""
        if keeps_access or not (user.is_active and user.has_permission('manage_users')):
            return False
        others = User.query.filter(
            User.group_id == user.group_id, User.id != user.id, User.is_active.is_(True),
        ).all()
        return not any(u.has_permission('manage_users') for u in others)
