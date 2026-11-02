# app/controllers/platform_controller.py
"""
Platform administration for superadmins.

Superadmins create, rename and suspend groups and add officers to a
group (its first Chairperson, or a replacement if a group locks itself
out). They do not see a group's reports or data.
"""
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from app.auth.forms import GroupCreateForm, GroupForm, RegisterForm
from app.decorators.permissions import superadmin_required
from app.extensions import db
from app.models.group import Group, GroupSettings
from app.models.report import GeneratedReport
from app.models.role import Role
from app.models.user import User
from app.services import audit, support
from app.services.file_cleanup import FileCleanupService


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
                audit.record('group.create', f'Platform created the group, with {form.officer_email.data.strip()} '
                             'as its first Chairperson', group_id=group.id)
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
                old = group.name
                group.name = form.name.data.strip()
                db.session.commit()
                audit.record('group.rename', f'Platform renamed the group from {old} to {group.name}',
                             group_id=group.id)
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
            events=audit.events(group.id, all_groups=True, page=1).items[:10], icons=audit.ICONS,
            support_minutes=current_app.config.get('SUPPORT_SESSION_MINUTES', 60),
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
            audit.record('group.toggle', f'Platform {status} the group', group_id=group.id)
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
                audit.record('officer.create', f'Platform added the officer {user.email} as {role.name}',
                             group_id=group.id, details={'user_id': user.id, 'role': role.name})
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

    # ==================== STORAGE ====================

    @staticmethod
    @superadmin_required
    def storage():
        """Storage per group; POST runs (or previews) cleanup for every group."""
        result = None
        if request.method == 'POST':
            dry_run = bool(request.form.get('dry_run'))
            result = FileCleanupService.cleanup_all(dry_run=dry_run)
            if not dry_run:
                audit.record('storage.cleanup', 'Platform cleaned up old files for every group',
                             details={k: v for k, v in result.items() if isinstance(v, (int, float, str))})
        return render_template('platform/storage.html', result=result,
                               storage=FileCleanupService.platform_storage())

    # ==================== SUPPORT SESSIONS ====================

    @staticmethod
    @superadmin_required
    def start_support(group_id):
        """Open a read-only, logged look at a group's screens (see app/services/support.py)."""
        group = PlatformController._group(group_id)
        reason = ' '.join(request.form.get('reason', '').split())
        if not 5 <= len(reason) <= 200:
            flash('Say why you need to look (5 to 200 characters): the group will see it.', 'danger')
            return redirect(url_for('platform.group_detail', group_id=group.id))
        support.end()          # one group at a time
        support.start(group, reason)
        flash(f'Support session opened for {group.name}. It is read-only and the group can see '
              'what you open.', 'info')
        return redirect(url_for('main.dashboard'))

    @staticmethod
    @superadmin_required
    def end_support():
        group_id = support.end()
        flash('Support session ended.', 'info')
        if group_id:
            return redirect(url_for('platform.group_detail', group_id=group_id))
        return redirect(url_for('platform.dashboard'))

    # ==================== AUDIT LOG ====================

    @staticmethod
    @superadmin_required
    def audit_log():
        """Every group's audit log, plus platform-wide events; ?group= and ?area= narrow it."""
        group_id = request.args.get('group', type=int)
        area = request.args.get('area') if request.args.get('area') in audit.AREAS else None
        page = audit.events(group_id, area=area, all_groups=True, page=request.args.get('page', 1, type=int))
        return render_template('platform/audit.html', page=page, icons=audit.ICONS, areas=audit.AREAS,
                               area=area, group_id=group_id, groups=Group.query.order_by(Group.name).all())

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
