# app/controllers/role_controller.py
"""
Group role management (requires the manage_users permission).

Guardrails:
  - An officer may only create, edit or delete roles whose permissions
    they hold themselves, and may only give a role those permissions.
  - A group always keeps at least one active officer with manage_users.
  - A role still held by an officer cannot be deleted.
"""
from flask import abort, current_app, flash, redirect, render_template, url_for
from flask_login import current_user

from app.auth.forms import RoleForm
from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.role import PERMISSIONS, Role
from app.models.user import User


class RoleController:

    # ==================== LIST ====================

    @staticmethod
    @permission_required('manage_users')
    def roles():
        """List the group's roles with their permissions and holders."""
        roles = Role.for_group().order_by(Role.name).all()
        holders = {
            r.id: User.for_group().filter(User.role_id == r.id).count()
            for r in roles
        }
        return render_template(
            'main/roles.html',
            version=current_app.version,
            roles=roles,
            holders=holders,
            permissions=PERMISSIONS,
        )

    # ==================== CREATE ====================

    @staticmethod
    @permission_required('manage_users')
    def create_role():
        form = RoleController._form()

        if form.validate_on_submit():
            perms = RoleController._submitted_permissions(form)
            try:
                role = Role(group_id=current_user.group_id, name=form.name.data, permissions=perms)
                db.session.add(role)
                db.session.commit()
                flash(f'Role {role.name} created.', 'success')
                return redirect(url_for('main.roles'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating role {form.name.data}: {e}")
                flash(f'Role creation failed: {str(e)}', 'danger')

        return render_template('main/role_form.html', version=current_app.version,
                               form=form, role=None)

    # ==================== EDIT ====================

    @staticmethod
    @permission_required('manage_users')
    def edit_role(role_id):
        role = RoleController._manageable_role(role_id)
        form = RoleController._form(role)
        if not form.is_submitted():
            form.name.data = role.name
            form.permissions.data = list(role.permissions or [])

        if form.validate_on_submit():
            perms = RoleController._submitted_permissions(form)

            if RoleController._would_remove_last_manager(role, perms):
                flash(
                    'This role holds the last active officers who can manage officers. '
                    'Give another officer that permission first.',
                    'danger',
                )
                return redirect(url_for('main.edit_role', role_id=role.id))

            try:
                role.name = form.name.data
                role.permissions = perms
                db.session.commit()
                flash(f'Role {role.name} updated.', 'success')
                return redirect(url_for('main.roles'))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error updating role {role_id}: {e}")
                flash(f'Update failed: {str(e)}', 'danger')

        return render_template('main/role_form.html', version=current_app.version,
                               form=form, role=role)

    # ==================== DELETE ====================

    @staticmethod
    @permission_required('manage_users')
    def delete_role(role_id):
        role = RoleController._manageable_role(role_id)

        if User.for_group().filter(User.role_id == role.id).count():
            flash(f'Move the officers holding {role.name} to another role first.', 'danger')
            return redirect(url_for('main.roles'))

        try:
            name = role.name
            db.session.delete(role)
            db.session.commit()
            flash(f'Role {name} deleted.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting role {role_id}: {e}")
            flash(f'Deletion failed: {str(e)}', 'danger')

        return redirect(url_for('main.roles'))

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _form(role=None):
        form = RoleForm(role=role)
        # Only the permissions the officer holds can be handed out
        form.permissions.choices = [
            (code, label) for code, label in PERMISSIONS.items()
            if current_user.has_permission(code)
        ]
        return form

    @staticmethod
    def _submitted_permissions(form):
        """The submitted permissions in display order; 403 if any is not grantable."""
        perms = set(form.permissions.data or [])
        if not perms <= current_user.permissions:
            abort(403)
        return [code for code in PERMISSIONS if code in perms]

    @staticmethod
    def _manageable_role(role_id):
        """A role of the current group that the officer could grant, else 404/403."""
        role = Role.get_for_group_or_404(role_id)
        if not current_user.can_grant(role):
            abort(403)
        return role

    @staticmethod
    def _would_remove_last_manager(role, new_perms) -> bool:
        """True if saving *role* with *new_perms* leaves no active manager."""
        if 'manage_users' in new_perms or not role.has('manage_users'):
            return False
        active = User.for_group(role.group_id).filter(User.is_active.is_(True)).all()
        holders = [u for u in active if u.role_id == role.id]
        others = [u for u in active if u.role_id != role.id and u.has_permission('manage_users')]
        return bool(holders) and not others
