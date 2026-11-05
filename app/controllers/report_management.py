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
from app.services import audit
from app.services.file_cleanup import FileCleanupService
from app.services.group_storage import group_folder
from app.controllers.report_controller import ReportController
from app.services.pdf_service import PDFGenerator
from app.services.period_store import PeriodStore


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
            audit.record('report.archive', f'Archived the {report.month}/{report.year} report',
                         details={'report_id': report.id})

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
            audit.record('report.restore', f'Restored the {report.month}/{report.year} report',
                         details={'report_id': report.id})

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
            audit.record('report.delete', f'Deleted the {report.month}/{report.year} report',
                         details={'report_id': report_id})

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
        """Build the report again as a new record (generate_reports).

        The PDF is made afresh from the month's stored contributions, so it
        reflects the latest sync. A month synced before contributions were
        stored has nothing to rebuild from, so its PDF is copied instead.
        """
        report = GeneratedReport.get_for_group_or_404(report_id)
        data = PeriodStore.report_data(report.group_id, report.year, report.month)

        if data is None and not os.path.exists(report.file_path):
            flash('Source report file not found on disk.', 'error')
            return redirect(
                url_for('report.preview_specific', report_id=report_id)
            )

        try:
            if data is not None:
                new_filepath = PDFGenerator.save_contribution_report(data, group_folder('reports'))
                totals = {
                    'total_contributions': data['total_contributions'],
                    'contributors_count':  data['num_contributors'],
                    'defaulters_count':    data['num_missing'],
                    'money_dispensed':     data['money_dispensed'],
                    'total_book_balance':  data['total_book_balance'],
                }
                message = (f'The {report.month}/{report.year} report was rebuilt from the latest '
                           'synced contributions.')
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                new_filepath = os.path.join(group_folder('reports'), f"copy_{timestamp}_{report.filename}")
                shutil.copy2(report.file_path, new_filepath)
                totals = {
                    'total_contributions': report.total_contributions,
                    'contributors_count':  report.contributors_count,
                    'defaulters_count':    report.defaulters_count,
                    'money_dispensed':     report.money_dispensed,
                    'total_book_balance':  report.total_book_balance,
                }
                message = (f'A copy of the {report.month}/{report.year} report has been created '
                           '(its month has no stored contributions to rebuild from).')

            new_report = GeneratedReport(
                group_id=report.group_id,
                month=report.month,
                year=report.year,
                report_type=report.report_type,
                filename=os.path.basename(new_filepath),
                file_path=new_filepath,
                generated_by=current_user.id,
                file_size=os.path.getsize(new_filepath),
                **totals,
            )

            db.session.add(new_report)
            db.session.commit()

            ReportController._log_access(new_report.id, 'regenerate')
            audit.record('report.regenerate', f'Rebuilt the {report.month}/{report.year} report',
                         details={'report_id': new_report.id, 'from_report_id': report.id})

            flash(message, 'success')
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
            audit.record('storage.cleanup', f'Cleaned up old report files: {result["deleted_count"]} removed, '
                         f'{result["reports_archived"]} reports archived')
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