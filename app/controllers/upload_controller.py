# app/controllers/upload_controller.py
"""
File upload and report generation.
"""
from datetime import datetime

from flask import (
    current_app, flash, redirect, render_template,
    request, session, url_for,
)
from flask_login import current_user

from app.decorators.permissions import permission_required
from app.models.setting import Setting
from app.models.report import GeneratedReport
from app.services.excel_parser import ExcelParser
from app.services.report_generator import ReportGenerator
from app.services.file_cleanup import FileCleanupService
from app.services.file_processor import FileProcessor
from app.services.report_serializer import ReportDataSerializer

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]


class UploadController:
    """Handles file upload, Excel parsing and report generation."""

    # ==================== UPLOAD DASHBOARD ====================

    @staticmethod
    @permission_required('upload_files')
    def upload_dashboard():
        """Landing page for upload-capable users (Admin & Clerk).
        """
        current_date = datetime.now()
        sheet_url = Setting.get_value(
            'google_sheets_url',
            current_app.config.get('DEFAULT_SHEET_URL', '')
        )

        recent_reports = UploadController._get_recent_reports_for_user()

        return render_template(
            'main/upload_dashboard.html',
            version=current_app.version,
            sheet_url=sheet_url,
            year=current_date.year,
            month=current_date.month,
            month_names=MONTH_NAMES,
            user_role=current_user.role,
            recent_reports=recent_reports,
        )

    # ==================== UPLOAD & GENERATE ====================

    @staticmethod
    @permission_required('upload_files')
    def upload():
        """Handle Excel file upload and trigger report generation.
        """
        filepath = None

        try:
            # --- 1. Save uploaded file ---
            filepath = FileProcessor.process_upload(request)

            # --- 2. Validate year / month ---
            year = request.form.get('year', type=int)
            month = request.form.get('month', type=int)

            if not year or not month:
                flash('Year and month are required.', 'error')
                return redirect(url_for('main.upload_dashboard'))

            if not (1 <= month <= 12):
                flash('Month must be between 1 and 12.', 'error')
                return redirect(url_for('main.upload_dashboard'))

            if year < 2000 or year > datetime.now().year + 1:
                flash('Please enter a valid year.', 'error')
                return redirect(url_for('main.upload_dashboard'))

            # --- 3. Parse Excel ---
            data = ExcelParser.parse_excel(filepath, year=year, month=month)

            # --- 4. Generate PDF report ---
            report_path = ReportGenerator.generate_contribution_report(
                data,
                current_app.config['REPORT_FOLDER'],
            )

            # --- 5. Store in session for preview / download ---
            session.update(ReportDataSerializer.serialize(data, report_path))

            # --- 6. Persist metadata to DB ---
            UploadController._save_report_to_db(data, report_path)

            # --- 7. Background cleanup ---
            UploadController._run_background_cleanup()

            flash('Report generated successfully!', 'success')
            return redirect(url_for('report.preview'))

        except ValueError as e:
            # Expected validation errors from ExcelParser / FileProcessor
            current_app.logger.warning(f"Upload validation error: {e}")
            flash(str(e), 'error')
            return redirect(url_for('main.upload_dashboard'))

        except Exception as e:
            current_app.logger.error(f"Upload error: {e}", exc_info=True)
            flash(f'Error generating report: {str(e)}', 'error')
            return redirect(url_for('main.upload_dashboard'))

        finally:
            # Always clean up the temp file even if generation failed
            if filepath:
                FileProcessor.cleanup_file(filepath)

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _save_report_to_db(data, report_path):
        """Persist report metadata to the database.

        Failures are logged but do not abort the user's workflow — the
        session already holds the data so preview/download still works.
        """
        try:
            from app.controllers.report_controller import ReportController
            report_data = {
                'month': data.get('month'),
                'year': data.get('year'),
                'report_filename': data.get('report_filename'),
                'total_contributions': data.get('total_contributions', 0),
                'num_contributors': data.get('num_contributors', 0),
                'num_missing': data.get('num_missing', 0),
                'money_dispensed': data.get('money_dispensed'),
                'total_book_balance': data.get('total_book_balance'),
            }
            ReportController.save_report_to_db(report_data, report_path)
        except Exception as e:
            current_app.logger.warning(f"Could not save report to DB: {e}")

    @staticmethod
    def _run_background_cleanup():
        """Remove files older than 30 days — non-fatal if it fails."""
        try:
            FileCleanupService.cleanup_old_files(days_to_keep=30)
        except Exception as e:
            current_app.logger.warning(f"Background cleanup failed: {e}")

    @staticmethod
    def _get_recent_reports_for_user():
        """Fetch the 5 most recent reports generated by the current user.

        Returns an empty list on any error so the dashboard still renders.
        """
        try:
            reports = (
                GeneratedReport.query
                .filter_by(generated_by=current_user.id)
                .order_by(GeneratedReport.generated_at.desc())
                .limit(5)
                .all()
            )
            return [
                {
                    'id': r.id,
                    'month': MONTH_NAMES[r.month - 1] if 1 <= r.month <= 12 else r.month,
                    'year': r.year,
                    'total_contributions': r.total_contributions,
                    'contributors': r.contributors_count,
                    'generated_date': r.generated_at.strftime('%d %b %Y %H:%M'),
                }
                for r in reports
            ]
        except Exception as e:
            current_app.logger.error(f"Error fetching recent reports: {e}")
            return []