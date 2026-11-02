# app/controllers/report_management.py
"""
Report lifecycle management: archive, restore, delete, cleanup, regenerate.
"""
import os
import shutil
from datetime import datetime

from flask import current_app, flash, redirect, url_for
from flask_login import current_user

from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.report import GeneratedReport, ReportAccessLog
from app.models.tenancy import current_group
from app.services.file_cleanup import FileCleanupService
from app.services.group_storage import group_folder
from app.controllers.report_controller import ReportController


class ReportManagement:
    """Officer operations on existing reports."""

    # ==================== ARCHIVE / RESTORE ====================

    @staticmethod
    @permission_required('manage_reports')
    def archive_report(report_id):
        """Soft-delete a report (manage_reports)."""
        report = GeneratedReport.get_for_group_or_404(report_id)

        try:
            report.is_archived = True
            report.archived_at = datetime.utcnow()
            db.session.commit()

            flash(
                f'Report {report.month}/{report.year} has been archived.',
                'success'
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error archiving report {report_id}: {e}")
            flash(f'Archive failed: {str(e)}', 'error')

        return redirect(url_for('report.list'))

    @staticmethod
    @permission_required('manage_reports')
    def restore_report(report_id):
        """Restore an archived report (manage_reports)."""
        report = GeneratedReport.get_for_group_or_404(report_id)

        try:
            report.is_archived = False
            report.archived_at = None
            db.session.commit()

            flash(
                f'Report {report.month}/{report.year} has been restored.',
                'success'
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error restoring report {report_id}: {e}")
            flash(f'Restore failed: {str(e)}', 'error')

        return redirect(url_for('report.list'))

    # ==================== DELETE ====================

    @staticmethod
    @permission_required('manage_reports')
    def delete_report(report_id):
        """Permanently delete a report and its file (manage_reports)."""
        report = GeneratedReport.get_for_group_or_404(report_id)

        try:
            # Remove file from disk first — if this fails, abort before
            # touching the DB so the record stays as an audit trail
            if os.path.exists(report.file_path):
                os.remove(report.file_path)

            ReportAccessLog.for_group().filter_by(report_id=report_id).delete()
            db.session.delete(report)
            db.session.commit()

            flash(
                f'Report {report.month}/{report.year} has been permanently deleted.',
                'success'
            )
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting report {report_id}: {e}")
            flash(f'Delete failed: {str(e)}', 'error')

        return redirect(url_for('report.list'))

    # ==================== REGENERATE ====================

    @staticmethod
    @permission_required('generate_reports')
    def regenerate_report(report_id):
        """Copy an existing report file as a new record (generate_reports).

        NOTE: This duplicates the PDF on disk — it does NOT re-parse
        the source Excel file.  True regeneration requires storing the
        raw contribution data per report, which is on the roadmap.
        Until then the method is honestly named 'duplicate' in the UI.
        """
        report = GeneratedReport.get_for_group_or_404(report_id)

        if not os.path.exists(report.file_path):
            flash('Source report file not found on disk.', 'error')
            return redirect(
                url_for('report.preview_specific', report_id=report_id)
            )

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"copy_{timestamp}_{report.filename}"
            new_filepath = os.path.join(group_folder('reports'), new_filename)

            shutil.copy2(report.file_path, new_filepath)

            new_report = GeneratedReport(
                group_id=report.group_id,
                month=report.month,
                year=report.year,
                report_type=report.report_type,
                filename=new_filename,
                file_path=new_filepath,
                generated_by=current_user.id,
                file_size=os.path.getsize(new_filepath),
                total_contributions=report.total_contributions,
                contributors_count=report.contributors_count,
                defaulters_count=report.defaulters_count,
                money_dispensed=report.money_dispensed,
                total_book_balance=report.total_book_balance,
            )

            db.session.add(new_report)
            db.session.commit()

            ReportController._log_access(new_report.id, 'regenerate')

            flash(
                f'A copy of the {report.month}/{report.year} report has been created.',
                'success'
            )
            return redirect(
                url_for('report.preview_specific', report_id=new_report.id)
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error regenerating report {report_id}: {e}")
            flash(f'Regeneration failed: {str(e)}', 'error')
            return redirect(url_for('report.list'))

    # ==================== BULK CLEANUP ====================

    @staticmethod
    @permission_required('manage_reports')
    def cleanup_reports():
        """Delete the group's expired files and archive their reports (manage_reports)."""
        try:
            result = FileCleanupService.cleanup_group(current_group())
            flash(
                f'Cleanup complete: '
                f'{result["deleted_count"]} files removed, '
                f'{result["reports_archived"]} reports archived.',
                'success'
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in report cleanup: {e}")
            flash(f'Cleanup failed: {str(e)}', 'error')

        return redirect(url_for('report.list'))