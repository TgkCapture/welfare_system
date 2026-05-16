# app/controllers/dashboard_controller.py
"""
Dashboard routing and per-role dashboard views.
"""
import os
from datetime import datetime, timedelta

from flask import (
    current_app, flash, jsonify, redirect,
    render_template, request, session, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from app.decorators.permissions import role_required
from app.extensions import db
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
        """Entry point — redirect to the correct role dashboard."""
        if current_user.is_admin:
            return redirect(url_for('main.admin_dashboard'))
        if current_user.is_clerk:
            return redirect(url_for('main.clerk_dashboard'))
        return redirect(url_for('main.viewer_dashboard'))

    # ==================== ADMIN DASHBOARD ====================

    @staticmethod
    @role_required('admin')
    def admin_dashboard():
        """Full system overview for admins."""
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()

        users_by_role = db.session.query(
            User.role,
            func.count(User.id).label('count')
        ).group_by(User.role).all()

        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_logins = (
            User.query
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
    @role_required('clerk')
    def clerk_dashboard():
        """Operational dashboard for clerks."""
        from app.controllers.settings_controller import SettingsController
        from app.controllers.report_controller import ReportController

        sheets_status = SettingsController.get_google_sheets_status()
        recent_reports = ReportController._get_available_reports_for_user(current_user)
        paid_members_count = DashboardController._get_paid_members_count()

        user = User.query.get(current_user.id)
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
    @login_required
    def viewer_dashboard():
        """Read-only dashboard for viewers."""
        from app.controllers.report_controller import ReportController

        available_reports = ReportController._get_available_reports_for_user(current_user)
        paid_members_count = DashboardController._get_paid_members_count()

        return render_template(
            'main/viewer_dashboard.html',
            version=current_app.version,
            user_role=current_user.role,
            available_reports=available_reports,
            paid_members_count=paid_members_count,
            month_names=MONTH_NAMES,
            current_date=datetime.now(),
        )

    # ==================== FILE CLEANUP (ADMIN) ====================

    @staticmethod
    @role_required('admin')
    def cleanup_files():
        """Admin page to manually trigger file cleanup."""
        cleanup_result = None

        if request.method == 'POST':
            days_to_keep = request.form.get('days_to_keep', 7, type=int)
            cleanup_result = FileCleanupService.cleanup_old_files(days_to_keep)

            if cleanup_result.get('success'):
                flash(
                    f"Cleaned up {cleanup_result['deleted_count']} old files.",
                    'success'
                )
            else:
                flash(f"Cleanup failed: {cleanup_result.get('error')}", 'error')

        folder_sizes = FileCleanupService.get_folder_sizes()

        return render_template(
            'main/cleanup.html',
            version=current_app.version,
            folder_sizes=folder_sizes,
            cleanup_result=cleanup_result,
        )

    # ==================== API / UTILITY ENDPOINTS ====================

    @staticmethod
    @login_required
    def storage_status():
        """JSON endpoint — current storage usage."""
        return jsonify(FileCleanupService.get_folder_sizes())

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
        """Return upload/report folder sizes and file counts."""
        upload_folder = current_app.config.get('UPLOAD_FOLDER', '')
        report_folder = current_app.config.get('REPORT_FOLDER', '')

        def folder_stats(path):
            if not os.path.exists(path):
                return 0, 0
            total_size = 0
            total_count = 0
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
                        total_count += 1
            return total_size, total_count

        upload_size, upload_count = folder_stats(upload_folder)
        report_size, report_count = folder_stats(report_folder)

        return {
            'upload_folder_size': upload_size,
            'report_folder_size': report_size,
            'upload_file_count': upload_count,
            'report_file_count': report_count,
            'total_size': upload_size + report_size,
        }

    @staticmethod
    def _get_recent_reports_from_db():
        """Return the 10 most recent reports from the database.
        """
        try:
            reports = (
                GeneratedReport.query
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
        """Return the total number of contributors across all active reports.
        """
        try:
            result = db.session.query(
                func.sum(GeneratedReport.contributors_count)
            ).filter(
                GeneratedReport.is_archived == False
            ).scalar()
            return int(result) if result else 0
        except Exception as e:
            current_app.logger.error(f"Error getting paid members count: {e}")
            return 0