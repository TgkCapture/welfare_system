# app/controllers/dashboard_controller.py
"""
The officer dashboard, file cleanup and utility endpoints.
"""
from datetime import datetime

from flask import (
    current_app, flash, jsonify, redirect,
    render_template, request, url_for,
)
from flask_login import current_user, login_required

from app.decorators.permissions import permission_required
from app.models.tenancy import current_group
from app.services import dashboard
from app.services.file_cleanup import FileCleanupService


class DashboardController:
    """Handles dashboard display logic only — no mutations."""

    # ==================== DASHBOARD ====================

    @staticmethod
    @login_required
    def dashboard():
        """One dashboard for every officer; each part shows if their role allows it."""
        if current_user.is_superadmin:
            return redirect(url_for('platform.dashboard'))
        group = current_group()
        return render_template(
            'main/dashboard.html',
            version=current_app.version,
            public_url=url_for('group.landing', slug=group.slug, _external=True),
            **dashboard.overview(group, current_user),
        )

    @staticmethod
    @login_required
    def old_dashboard():
        """The former admin, clerk and viewer dashboards, kept for bookmarks."""
        return redirect(url_for('main.dashboard'))

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
