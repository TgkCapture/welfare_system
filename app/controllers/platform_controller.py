# app/controllers/platform_controller.py
"""
Platform administration for superadmins.

Superadmins create, rename and suspend groups and add officers to a
group (its first Chairperson, or a replacement if a group locks itself
out). They do not see a group's reports or data.
"""
from flask import abort, current_app, flash, redirect, render_template, url_for
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from app.auth.forms import GroupCreateForm, GroupForm, RegisterForm
from app.decorators.permissions import superadmin_required
from app.extensions import db
from app.models.group import Group, GroupSettings
from app.models.report import GeneratedReport
from app.models.role import Role
from app.models.user import User


class PlatformController:

    # ==================== DASHBOARD ====================

    @staticmethod
    @superadmin_required
    def dashboard():
        """List every group with its officer and report counts."""
        officers = (
            db.session.query(User.group_id, func.count(User.id))  # platform-wide
            .filter(User.group_id.isnot(None), User.is_active.is_(True))
            .group_by(User.group_id)
        )
        reports = (
            db.session.query(GeneratedReport.group_id, func.count(GeneratedReport.id))  # platform-wide
            .group_by(GeneratedReport.group_id)
        )
        officer_counts, report_counts = dict(officers.all()), dict(reports.all())

        groups = [
            {
                'group':    g,
                'officers': officer_counts.get(g.id, 0),
                'reports':  report_counts.get(g.id, 0),
            }
            for g in Group.query.order_by(Group.name).all()
        ]
        return render_template('platform/dashboard.html', groups=groups)

    # ==================== CREATE GROUP ====================

    @staticmethod
    @superadmin_required
    def create_group():
        """Create a group, its preset roles and its first officer (Chairperson)."""
        form = GroupCreateForm()

        if form.validate_on_submit():
            try:
                group = Group(name=form.name.data.strip(), slug=form.slug.data)
                group.settings = GroupSettings(display_name=group.name)
                db.session.add(group)
                presets = Role.seed_presets(group)
                db.session.add(User(
                    email=form.officer_email.data.strip(),
                    password=generate_password_hash(form.officer_password.data, method='scrypt'),
                    group=group,
                    role=presets['Chairperson'],
                ))
                db.session.commit()
                flash(f'Group {group.name} created. Its officers sign in at /g/{group.slug}/login.',
                      'success')
                return redirect(url_for('platform.group_detail', group_id=group.id))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error creating group {form.slug.data}: {e}")
                flash(f'Group creation failed: {str(e)}', 'danger')

        return render_template('platform/group_create.html', form=form)

    # ==================== GROUP DETAIL ====================

    @staticmethod
    @superadmin_required
    def group_detail(group_id):
        """Rename a group and list its officers."""
        group = PlatformController._group(group_id)
        form = GroupForm(obj=group)

        if form.validate_on_submit():
            try:
                group.name = form.name.data.strip()
                db.session.commit()
                flash('Group renamed.', 'success')
                return redirect(url_for('platform.group_detail', group_id=group.id))
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error renaming group {group_id}: {e}")
                flash(f'Update failed: {str(e)}', 'danger')

        return render_template(
            'platform/group_detail.html',
            group=group,
            form=form,
            officer_form=PlatformController._officer_form(group),
            officers=User.for_group(group.id).order_by(User.created_at).all(),
        )

    @staticmethod
    @superadmin_required
    def toggle_group(group_id):
        """Suspend or reactivate a group. Suspended groups' officers are signed out."""
        group = PlatformController._group(group_id)
        try:
            group.is_active = not group.is_active
            db.session.commit()
            status = 'reactivated' if group.is_active else 'suspended'
            flash(f'Group {group.name} {status}.', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error toggling group {group_id}: {e}")
            flash(f'Update failed: {str(e)}', 'danger')
        return redirect(url_for('platform.group_detail', group_id=group.id))

    # ==================== ADD OFFICER ====================

    @staticmethod
    @superadmin_required
    def add_officer(group_id):
        """Add an officer with any of the group's roles (e.g. after a lock-out)."""
        group = PlatformController._group(group_id)
        form = PlatformController._officer_form(group)

        if form.validate_on_submit():
            role = Role.for_group(group.id).filter_by(id=form.role.data).first()
            if role is None:
                abort(400)
            try:
                user = User(
                    email=form.email.data.strip(),
                    password=generate_password_hash(form.password.data, method='scrypt'),
                    group_id=group.id,
                    role=role,
                )
                db.session.add(user)
                db.session.commit()
                flash(f'Officer {user.email} added as {role.name}.', 'success')
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error adding officer to group {group_id}: {e}")
                flash(f'Officer creation failed: {str(e)}', 'danger')
        else:
            for errors in form.errors.values():
                for error in errors:
                    flash(error, 'danger')

        return redirect(url_for('platform.group_detail', group_id=group.id))

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _group(group_id):
        group = db.session.get(Group, group_id)
        if group is None:
            abort(404)
        return group

    @staticmethod
    def _officer_form(group):
        form = RegisterForm(group_id=group.id)
        form.role.choices = [(r.id, r.name) for r in Role.for_group(group.id).order_by(Role.name)]
        return form
