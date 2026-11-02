# app/controllers/upload_controller.py
"""
File upload and report generation.

Officers with upload_data can upload Excel files and trigger report generation.
"""
from datetime import datetime
import os

from flask import (
    current_app, flash, redirect, render_template,
    request, url_for,
)
from flask_login import current_user
from markupsafe import Markup

from app.controllers.report_controller import ReportController
from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.ledger import SyncRun
from app.models.report import GeneratedReport
from app.models.tenancy import current_group
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
    @permission_required('upload_data')
    def upload_dashboard():
        """Landing page for officers with upload_data."""
        current_date = datetime.now()
        sheet_url = current_group().settings.google_sheet_url or ''
        recent_reports = UploadController._get_recent_reports_for_user()

        return render_template(
            'main/upload_dashboard.html',
            version=current_app.version,
            sheet_url=sheet_url,
            year=current_date.year,
            month=current_date.month,
            month_names=MONTH_NAMES,
            recent_reports=recent_reports,
        )

    # ==================== UPLOAD & GENERATE ====================

    @staticmethod
    @permission_required('upload_data')
    def upload():
        """Handle Excel file upload and trigger report generation."""
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
                ReportController.remember_report(report_id)

            # --- 7. Background cleanup ---
            UploadController._run_background_cleanup()

            flash('Report generated successfully!', 'success')
            UploadController._flash_sync_notes(run)
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
    def _flash_sync_notes(run):
        """Point the officer at new names and warnings from the sync."""
        new_members = run.details.get('new_members', [])
        if new_members:
            names = ', '.join(new_members[:10])
            more = len(new_members) - 10
            flash(
                f"{len(new_members)} new member(s) added: {names}"
                f"{f' and {more} more' if more > 0 else ''}. "
                "If any is a respelling of an existing member, they can be merged.",
                'info',
            )
        if run.warnings:
            flash(
                Markup('The workbook raised {} warning(s). <a href="{}">Review them</a>.').format(
                    len(run.warnings), url_for('main.sync_run', run_id=run.id)),
                'warning',
            )

    @staticmethod
    def _run_background_cleanup():
        """Expire the group's old files; other groups are left to the daily job."""
        try:
            FileCleanupService.cleanup_group(current_group())
        except Exception as e:
            current_app.logger.warning(f"Background cleanup failed: {e}")

    @staticmethod
    def _get_recent_reports_for_user():
        try:
            reports = (
                GeneratedReport.for_group()
                .filter_by(generated_by=current_user.id)
                .order_by(GeneratedReport.generated_at.desc())
                .limit(5)
                .all()
            )
            
            processed_reports = []
            for r in reports:
                # Handle month safely - could be int, str, or None
                month_display = r.month
                if r.month is not None:
                    try:
                        # Try to convert to int if it's a string
                        month_num = int(r.month) if isinstance(r.month, str) else r.month
                        # Check if it's a valid month number (1-12)
                        if isinstance(month_num, int) and 1 <= month_num <= 12:
                            month_display = MONTH_NAMES[month_num - 1]
                        else:
                            # If it's a number but out of range, keep as is
                            month_display = str(r.month)
                    except (ValueError, TypeError):
                        # If conversion fails, keep original value
                        month_display = str(r.month)
                else:
                    month_display = 'Unknown'
                
                processed_reports.append({
                    'id': r.id,
                    'month': month_display,
                    'year': r.year,
                    'total_contributions': r.total_contributions,
                    'contributors': r.contributors_count,
                    'generated_date': r.generated_at.strftime('%d %b %Y %H:%M'),
                })
            
            return processed_reports
            
        except Exception as e:
            current_app.logger.error(f"Error fetching recent reports: {e}")
            return []


def _ascii_safe(text: str) -> str:
    """Return an ASCII-safe version of *text* for use in flash messages.

    Non-ASCII characters (e.g. em dash \u2014 from member names) are
    replaced with '?' so they never cause encoding errors in the session.
    """
    return text.encode('ascii', errors='replace').decode('ascii')