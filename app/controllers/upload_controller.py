# app/controllers/upload_controller.py
"""
File upload and report generation.

Officers with upload_data can upload Excel files or sync any Google Sheet;
officers with generate_reports can sync the group's linked Google Sheet.
Either way the month's report is made from what was stored.
"""
from datetime import datetime
import os

from flask import (
    current_app, flash, redirect, render_template,
    request, url_for,
)
from flask_login import current_user

from app.controllers.report_controller import ReportController
from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.ledger import SyncRun
from app.models.member import PeriodSummary
from app.models.tenancy import current_group
from app.services import audit
from app.services.excel_parser import ExcelParser
from app.services.pdf_service import PDFGenerator
from app.services.file_cleanup import FileCleanupService
from app.services.file_processor import FileProcessor
from app.services.group_storage import group_folder
from app.services.period_store import PeriodStore
from app.services.standard_sync import StandardSync
from app.services.sheet_mapping import SheetMapping
from app.services.standard_workbook import StandardWorkbook

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]


class UploadController:
    """Handles file upload, Excel parsing and report generation."""

    # ==================== UPLOAD DASHBOARD ====================

    @staticmethod
    @permission_required('upload_data', 'generate_reports')
    def upload_dashboard():
        """Step 1 of the monthly cycle: choose the month and where the data comes from."""
        group = current_group()
        latest = (PeriodSummary.for_group(group.id)
                  .order_by(PeriodSummary.year.desc(), PeriodSummary.month.desc()).first())
        year, month = UploadController._suggested_month(latest)
        last_run = SyncRun.for_group(group.id).order_by(SyncRun.synced_at.desc()).first()

        return render_template(
            'main/upload_dashboard.html',
            version=current_app.version,
            sheet_url=group.settings.google_sheet_url or '',
            year=year,
            month=month,
            this_year=datetime.now().year,
            month_names=MONTH_NAMES,
            latest_label=f'{MONTH_NAMES[latest.month - 1]} {latest.year}' if latest else None,
            standard=bool(last_run and last_run.layout == 'standard'),
            sheet_only=not current_user.has_permission('upload_data'),
        )

    @staticmethod
    def _suggested_month(latest):
        """The month after the last one synced, but never a month still to come."""
        now = datetime.now()
        if latest is None:
            return now.year, now.month
        year, month = (latest.year + 1, 1) if latest.month == 12 else (latest.year, latest.month + 1)
        return (year, month) if (year, month) <= (now.year, now.month) else (latest.year, latest.month)

    # ==================== UPLOAD & GENERATE ====================

    @staticmethod
    @permission_required('upload_data', 'generate_reports')
    def upload():
        """Handle Excel file upload and trigger report generation."""
        filepath = None

        try:
            # --- 1. Save uploaded file (generate_reports alone: the group's own sheet) ---
            saved_url = None
            if not current_user.has_permission('upload_data'):
                saved_url = current_group().settings.google_sheet_url
                if not saved_url:
                    flash("Your group's Google Sheet isn't linked yet. Ask the Chairperson to add it "
                          'in Settings.', 'error')
                    return redirect(url_for('main.upload_dashboard'))
            filepath = FileProcessor.process_upload(request, sheet_url=saved_url)

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

            # --- 3–4. Read the workbook and store it ---
            group = current_group()
            source = 'google_sheets' if FileProcessor.uses_google_sheets(request) else 'upload'
            if StandardWorkbook.is_standard(filepath):
                # Standard layout: every year and month in the workbook is stored
                run = StandardSync.sync(group, filepath, user=current_user, source=source)
            else:
                # Older layout: only the chosen month is read
                mapping = SheetMapping.from_dict(group.settings.sheet_mapping)
                parsed = ExcelParser.parse_excel(filepath, year=year, month=month, mapping=mapping)
                run = UploadController._record_legacy_sync(
                    group, PeriodStore.sync(group, parsed, user=current_user, source=source), source,
                    parsed.get('warnings', []),
                )

            audit.record('sync.run', 'Synced the workbook from '
                         + ('the Google Sheet' if source == 'google_sheets' else 'an uploaded file'),
                         details={'sync_run_id': run.id, 'layout': run.layout,
                                  'warnings': len(run.warnings or [])})

            # --- 5. Generate the PDF from the stored month ---
            data = PeriodStore.report_data(group.id, year, month)
            if data is None:
                flash(f'The workbook was synced, but it has no contributions for '
                      f'{MONTH_NAMES[month - 1]} {year} yet, so no report was made.', 'warning')
                return redirect(url_for('main.sync_run', run_id=run.id))
            report_path = PDFGenerator.save_contribution_report(data, group_folder('reports'))

            # --- 6. Record the report; remember it for preview / download ---
            report_id = UploadController._save_report_to_db(data, report_path)
            if report_id:
                ReportController.remember_report(report_id, run.id)

            # --- 7. Background cleanup ---
            UploadController._run_background_cleanup()

            # The check page shows the new names and warnings itself
            return redirect(url_for('report.preview'))

        except ValueError as e:
            current_app.logger.warning(f"Upload validation error: {e}")
            flash(_ascii_safe(str(e)), 'error')
            return redirect(url_for('main.upload_dashboard'))

        except Exception as e:
            current_app.logger.error(f"Upload error: {e}", exc_info=True)
            flash(f'Error generating report: {_ascii_safe(str(e))}', 'error')
            return redirect(url_for('main.upload_dashboard'))

        finally:
            # Always remove the uploaded copy, even if generation failed
            if filepath:
                FileProcessor.cleanup_file(filepath)

    # ==================== PRIVATE HELPERS ====================

    @staticmethod
    def _save_report_to_db(data, report_path):
        """Record the generated report; returns its id, or None on failure."""
        try:
            report_data = {
                'month': MONTH_NAMES.index(data.get('month')) + 1  # convert to int
                        if data.get('month') in MONTH_NAMES else data.get('month'),
                'year':                data.get('year'),
                'report_filename':     os.path.basename(report_path),  # ← from actual path
                'total_contributions': data.get('total_contributions', 0),
                'num_contributors':    data.get('num_contributors', 0),
                'num_missing':         data.get('num_missing', 0),
                'money_dispensed':     data.get('money_dispensed'),
                'total_book_balance':  data.get('total_book_balance'),
            }
            return ReportController.save_report_to_db(report_data, report_path)
        except Exception as e:
            current_app.logger.warning(f"Could not save report to DB: {e}")
            return None

    @staticmethod
    def _record_legacy_sync(group, result, source, warnings=()):
        """Record an older-layout sync with the parser's warnings and any repeated names."""
        month_name = MONTH_NAMES[result['month'] - 1]
        run = SyncRun(
            group_id=group.id, synced_by=current_user.id, source=source, layout='legacy',
            warnings=list(warnings) + [
                {'where': f"{result['year']} sheet, {month_name}",
                 'message': f'{name} is listed more than once; the amounts were added together.'}
                for name in sorted(set(result['repeated_names']))
            ],
            details={'years': [result['year']], 'months': [[result['year'], result['month']]],
                     'new_members': result['new_members']},
        )
        db.session.add(run)
        db.session.commit()
        return run

    @staticmethod
    def _run_background_cleanup():
        """Expire the group's old files; other groups are left to the daily job."""
        try:
            FileCleanupService.cleanup_group(current_group())
        except Exception as e:
            current_app.logger.warning(f"Background cleanup failed: {e}")


def _ascii_safe(text: str) -> str:
    """Return an ASCII-safe version of *text* for use in flash messages.

    Non-ASCII characters (e.g. em dash \u2014 from member names) are
    replaced with '?' so they never cause encoding errors in the session.
    """
    return text.encode('ascii', errors='replace').decode('ascii')