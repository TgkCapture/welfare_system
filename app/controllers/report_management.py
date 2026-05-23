# app/controllers/report_management.py
"""
Report lifecycle management: archive, restore, delete, cleanup, regenerate.
"""
import os
import shutil
from datetime import datetime, timedelta

from flask import current_app, flash, redirect, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.report import GeneratedReport, ReportAccessLog
from app.services.file_cleanup import FileCleanupService
from app.controllers.report_controller import ReportController


class ReportManagement:
    """Admin / clerk operations on existing reports."""

    # ==================== ARCHIVE / RESTORE ====================

    @staticmethod
    @login_required
    def archive_report(report_id):
        """Soft-delete a report (admins only)."""
        if not current_user.is_admin:
            flash('Only admins can archive reports.', 'error')
            return redirect(url_for('report.list'))

        report = GeneratedReport.query.get_or_404(report_id)

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
    @login_required
    def restore_report(report_id):
        """Restore an archived report (admins only)."""
        if not current_user.is_admin:
            flash('Only admins can restore reports.', 'error')
            return redirect(url_for('report.list'))

        report = GeneratedReport.query.get_or_404(report_id)

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
    @login_required
    def delete_report(report_id):
        """Permanently delete a report and its file (admins only)."""
        if not current_user.is_admin:
            flash('Only admins can delete reports.', 'error')
            return redirect(url_for('report.list'))

        report = GeneratedReport.query.get_or_404(report_id)

        try:
            # Remove file from disk first — if this fails, abort before
            # touching the DB so the record stays as an audit trail
            if os.path.exists(report.file_path):
                os.remove(report.file_path)

            ReportAccessLog.query.filter_by(report_id=report_id).delete()
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
    @login_required
    def regenerate_report(report_id):
        """Copy an existing report file as a new record (admin & clerk).

        NOTE: This duplicates the PDF on disk — it does NOT re-parse
        the source Excel file.  True regeneration requires storing the
        raw contribution data per report, which is on the roadmap.
        Until then the method is honestly named 'duplicate' in the UI.
        """
        if not (current_user.is_admin or current_user.is_clerk):
            flash('Only admins and clerks can regenerate reports.', 'error')
            return redirect(url_for('report.list'))

        report = GeneratedReport.query.get_or_404(report_id)

        if not os.path.exists(report.file_path):
            flash('Source report file not found on disk.', 'error')
            return redirect(
                url_for('main.report_preview_specific', report_id=report_id)
            )

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"copy_{timestamp}_{report.filename}"
            new_filepath = os.path.join(
                current_app.config['REPORT_FOLDER'],
                new_filename,
            )

            shutil.copy2(report.file_path, new_filepath)

            new_report = GeneratedReport(
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
                url_for('main.report_preview_specific', report_id=new_report.id)
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error regenerating report {report_id}: {e}")
            flash(f'Regeneration failed: {str(e)}', 'error')
            return redirect(url_for('report.list'))

    # ==================== BULK CLEANUP ====================

    @staticmethod
    @login_required
    def cleanup_reports():
        """Archive old DB records and delete stale files (admins only)."""
        if not current_user.is_admin:
            flash('Only admins can run report cleanup.', 'error')
            return redirect(url_for('main.dashboard'))

        try:
            days_to_keep = current_app.config.get('REPORT_RETENTION_DAYS', 7)

            # 1. Remove stale files from disk
            file_result = FileCleanupService.cleanup_old_files(
                days_to_keep=days_to_keep
            )

            # 2. Auto-archive old DB records whose files have been removed
            cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
            old_reports = GeneratedReport.query.filter(
                GeneratedReport.generated_at < cutoff,
                GeneratedReport.is_archived == False,
            ).all()

            for r in old_reports:
                r.is_archived = True
                r.archived_at = datetime.utcnow()

            db.session.commit()

            flash(
                f'Cleanup complete: '
                f'{file_result.get("deleted_count", 0)} files removed, '
                f'{len(old_reports)} reports archived.',
                'success'
            )

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error in report cleanup: {e}")
            flash(f'Cleanup failed: {str(e)}', 'error')

        return redirect(url_for('report.list'))