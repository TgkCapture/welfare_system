# app/controllers/dashboard_controller.py
"""
Dashboard routing and per-role dashboard views.
"""
from datetime import datetime, timedelta

from flask import (
    current_app, flash, jsonify, redirect,
    render_template, request, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.role import Role
from app.models.tenancy import current_group
from app.models.user import User
from app.models.report import GeneratedReport
from app.services.file_cleanup import FileCleanupService

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]


class DashboardController:
    """Handles dashboard display logic only — no mutations."""

    # ==================== ROLE ROUTER ====================

    @staticmethod
    @login_required
    def dashboard():
        """Entry point — redirect to the dashboard matching the user's permissions."""
        if current_user.is_superadmin:
            return redirect(url_for('platform.dashboard'))
        if current_user.has_permission('manage_users'):
            return redirect(url_for('main.admin_dashboard'))
        if current_user.has_permission('upload_data'):
            return redirect(url_for('main.clerk_dashboard'))
        return redirect(url_for('main.viewer_dashboard'))

    # ==================== ADMIN DASHBOARD ====================

    @staticmethod
    @permission_required('manage_users')
    def admin_dashboard():
        """Group overview for officers who manage officers."""
        group_users = User.for_group()
        total_users = group_users.count()
        active_users = group_users.filter_by(is_active=True).count()

        users_by_role = [
            {'role': name, 'count': count}
            for name, count in (
                Role.for_group()
                .join(User, User.role_id == Role.id)
                .with_entities(Role.name, func.count(User.id))
                .group_by(Role.name)
                .all()
            )
        ]

        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_logins = (
            group_users
            .filter(
                User.last_login.isnot(None),
                User.last_login >= seven_days_ago,
            )
            .order_by(User.last_login.desc())
            .limit(10)
            .all()
        )

        from app.controllers.settings_controller import SettingsController
        sheets_status = SettingsController.get_google_sheets_status()

        return render_template(
            'main/admin_dashboard.html',
            version=current_app.version,
            total_users=total_users,
            active_users=active_users,
            users_by_role=users_by_role,
            recent_logins=recent_logins,
            file_stats=DashboardController._get_file_statistics(),
            recent_reports=DashboardController._get_recent_reports_from_db(),
            sheets_status=sheets_status,
            current_date=datetime.now(),
        )

    # ==================== CLERK DASHBOARD ====================

    @staticmethod
    @permission_required('upload_data')
    def clerk_dashboard():
        """Operational dashboard for clerks."""
        from app.controllers.settings_controller import SettingsController
        from app.controllers.report_controller import ReportController

        sheets_status = SettingsController.get_google_sheets_status()
        recent_reports = ReportController._get_available_reports_for_user(current_user)
        paid_members_count = DashboardController._get_paid_members_count()

        user = db.session.get(User, current_user.id)  # own account
        last_login = (
            user.last_login.strftime('%B %d, %Y %I:%M %p')
            if user.last_login else 'Never'
        )

        return render_template(
            'main/clerk_dashboard.html',
            version=current_app.version,
            current_date=datetime.now(),
            month_names=MONTH_NAMES,
            sheets_status=sheets_status,
            recent_reports=recent_reports,
            paid_members_count=paid_members_count,
            reports_generated=len(recent_reports),
            last_login=last_login,
            user=current_user,
        )

    # ==================== VIEWER DASHBOARD ====================

    @staticmethod
    @permission_required('view_reports')
    def viewer_dashboard():
        """Read-only dashboard for viewers."""
        from app.controllers.report_controller import ReportController

        available_reports = ReportController._get_available_reports_for_user(current_user)
        paid_members_count = DashboardController._get_paid_members_count()

        return render_template(
            'main/viewer_dashboard.html',
            version=current_app.version,
            available_reports=available_reports,
            paid_members_count=paid_members_count,
            month_names=MONTH_NAMES,
            current_date=datetime.now(),
        )

    # ==================== FILE CLEANUP (manage_reports) ====================

    @staticmethod
    @permission_required('manage_reports')
    def cleanup_files():
        """The group's storage, with a button to expire old files now."""
        group = current_group()
        cleanup_result = None

        if request.method == 'POST':
            dry_run = bool(request.form.get('dry_run'))
            cleanup_result = FileCleanupService.cleanup_group(group, dry_run=dry_run)
            verb = 'Would delete' if dry_run else 'Deleted'
            flash(
                f"{verb} {cleanup_result['deleted_count']} file(s) and "
                f"{'archive' if dry_run else 'archived'} {cleanup_result['reports_archived']} report(s).",
                'info' if dry_run else 'success'
            )

        return render_template(
            'admin/cleanup.html',
            version=current_app.version,
            storage_stats=FileCleanupService.group_storage(group),
            cleanup_result=cleanup_result,
        )

    # ==================== API / UTILITY ENDPOINTS ====================

    @staticmethod
    @permission_required('manage_reports')
    def storage_status():
        """JSON endpoint — the group's storage usage."""
        stats = FileCleanupService.group_storage(current_group())
        # Folder paths are server internals; officers only need the numbers
        for folder in stats['folders'].values():
            folder.pop('path', None)
        return jsonify(stats)

    @staticmethod
    def version():
        """Plain-text version string."""
        return f"Current version: {current_app.version}"

    @staticmethod
    def health_check():
        """Health-check endpoint for uptime monitoring."""
        return jsonify({
            'status': 'healthy',
            'version': current_app.version,
            'timestamp': datetime.now().isoformat(),
        })

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _get_file_statistics():
        """Return the group's upload/report folder sizes (bytes) and file counts."""
        folders = FileCleanupService.group_storage(current_group())['folders']
        to_bytes = lambda mb: int(mb * 1024 * 1024)

        return {
            'upload_folder_size': to_bytes(folders['uploads']['size_mb']),
            'report_folder_size': to_bytes(folders['reports']['size_mb']),
            'upload_file_count': folders['uploads']['file_count'],
            'report_file_count': folders['reports']['file_count'],
            'total_size': to_bytes(folders['uploads']['size_mb'] + folders['reports']['size_mb']),
        }

    @staticmethod
    def _get_recent_reports_from_db():
        """Return the current group's 10 most recent reports.
        """
        try:
            reports = (
                GeneratedReport.for_group()
                .order_by(GeneratedReport.generated_at.desc())
                .limit(10)
                .all()
            )
            return [
                {
                    'month': MONTH_NAMES[int(r.month) - 1] if r.month and str(r.month).isdigit() and 1 <= int(r.month) <= 12 else r.month,
                    'year': r.year,
                    'total_contributions': r.total_contributions,
                    'contributors': r.contributors_count,
                    'generated_date': r.generated_at.strftime('%Y-%m-%d'),
                    'generated_by': r.generator.email if r.generator else 'Unknown',
                }
                for r in reports
            ]
        except Exception as e:
            current_app.logger.error(f"Error fetching recent reports: {e}")
            return []

    @staticmethod
    def _get_paid_members_count():
        """Return the total number of contributors across the group's active reports.
        """
        try:
            result = (
                GeneratedReport.for_group()
                .filter(GeneratedReport.is_archived.is_(False))
                .with_entities(func.sum(GeneratedReport.contributors_count))
                .scalar()
            )
            return int(result) if result else 0
        except Exception as e:
            current_app.logger.error(f"Error getting paid members count: {e}")
            return 0