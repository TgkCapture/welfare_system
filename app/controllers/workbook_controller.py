# app/controllers/workbook_controller.py
"""
The group's standard workbook: template download, sync history and warnings
(upload_data), and the group's payout purposes (edit_settings).
"""
import calendar
from datetime import datetime

from flask import current_app, flash, redirect, render_template, request, send_file, url_for

from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.ledger import PayoutPurpose, SyncRun, YearSummary
from app.models.tenancy import current_group
from app.services import audit
from app.services.excel_parser import ExcelParser
from app.services.file_processor import FileProcessor
from app.services.sheet_mapping import FINANCIALS, SHEET_MODES, SheetMapping
from app.services.standard_workbook import StandardWorkbook
from app.services.workbook_template import build_template

PURPOSE_MAX_LENGTH = 80


class WorkbookController:

    # ==================== WORKBOOK PAGE ====================

    @staticmethod
    @permission_required('upload_data')
    def workbook():
        """Template download, the calculated yearly balances and recent syncs."""
        return render_template(
            'main/workbook.html',
            version=current_app.version,
            year=datetime.now().year,
            years=YearSummary.for_group().order_by(YearSummary.year.desc()).all(),
            runs=SyncRun.for_group().order_by(SyncRun.synced_at.desc()).limit(10).all(),
        )

    @staticmethod
    @permission_required('upload_data')
    def download_template():
        """The standard workbook for a year, pre-filled with the group's members and rates."""
        year = request.form.get('year', type=int)
        if not year or not 2000 <= year <= datetime.now().year + 1:
            flash('Please choose a valid year.', 'danger')
            return redirect(url_for('main.workbook'))

        group = current_group()
        buffer = build_template(group, year)
        db.session.commit()   # keeps any Member IDs given to members for the template
        audit.record('workbook.template', f'Downloaded the {year} workbook template', details={'year': year})
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'{group.slug}_contributions_{year}.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )

    # ==================== SYNC RESULTS ====================

    @staticmethod
    @permission_required('upload_data')
    def sync_run(run_id):
        """Everything one sync stored, and the warnings it raised."""
        run = SyncRun.get_for_group_or_404(run_id)
        return render_template('main/sync_run.html', version=current_app.version, run=run)

    # ==================== LAYOUT (older workbooks) ====================

    @staticmethod
    @permission_required('edit_settings')
    def layout():
        """Where to find things in a workbook that isn't the standard layout.

        POST with action=test reads a sample file with the submitted settings
        (without saving them); action=save saves them; action=reset goes back
        to reading the original Mzugoss layout automatically.
        """
        group = current_group()
        mapping = SheetMapping.from_dict(group.settings.sheet_mapping)
        preview = None
        action = request.form.get('action')

        if action == 'reset':
            group.settings.sheet_mapping = None
            db.session.commit()
            audit.record('workbook.layout', 'Cleared the workbook layout settings (automatic reading)')
            flash('Layout settings cleared: workbooks are read automatically again.', 'success')
            return redirect(url_for('main.workbook_layout'))

        if action in ('test', 'save'):
            mapping = SheetMapping.from_form(request.form)
            problems = mapping.errors()
            for problem in problems:
                flash(problem, 'danger')
            if not problems and action == 'save':
                group.settings.sheet_mapping = None if mapping.is_automatic() else mapping.to_dict()
                db.session.commit()
                audit.record('workbook.layout', 'Changed the workbook layout settings',
                             details={'mapping': group.settings.sheet_mapping})
                flash('Layout settings saved. They apply to the next upload or sync.', 'success')
                return redirect(url_for('main.workbook_layout'))
            if not problems and action == 'test':
                preview = WorkbookController._preview(mapping)

        return render_template(
            'main/workbook_layout.html', version=current_app.version,
            mapping=mapping, sheet_modes=SHEET_MODES, financials=FINANCIALS, preview=preview,
            month_names=list(calendar.month_name)[1:], year=request.form.get('year', type=int) or datetime.now().year,
            month=request.form.get('month', type=int) or datetime.now().month,
        )

    @staticmethod
    def _preview(mapping):
        """Read the uploaded sample with *mapping*; the file is deleted afterwards."""
        year, month = request.form.get('year', type=int), request.form.get('month', type=int)
        if not year or not month or not 1 <= month <= 12:
            return {'error': 'Choose the year and month to read.'}
        try:
            path = FileProcessor._process_file_upload(request)
        except ValueError as e:
            return {'error': str(e)}
        try:
            if StandardWorkbook.is_standard(path):
                return {'standard': True}
            parsed = ExcelParser.parse_excel(path, year=year, month=month, mapping=mapping)
            df = parsed['data']
            return {
                'sheet': parsed['sheet'], 'name_col': parsed['name_col'], 'month_col': parsed['month_col'],
                'rows': [(r[parsed['name_col']], r[parsed['month_col']]) for _, r in df.head(15).iterrows()],
                'row_count': len(df), 'total': parsed['total_contributions'],
                'paid': parsed['num_contributors'], 'unpaid': parsed['num_missing'],
                'money_dispensed': parsed['money_dispensed'], 'book_balance': parsed['total_book_balance'],
                'warnings': parsed['warnings'],
            }
        except ValueError as e:
            return {'error': str(e)}
        except Exception as e:
            current_app.logger.warning(f'Layout preview failed: {e}')
            return {'error': "The file couldn't be read as a spreadsheet."}
        finally:
            FileProcessor.cleanup_file(path)

    # ==================== PAYOUT PURPOSES ====================

    @staticmethod
    @permission_required('edit_settings')
    def payout_purposes():
        """List the group's payout purposes; POST adds one."""
        if request.method == 'POST':
            name = WorkbookController._purpose_name()
            if name:
                db.session.add(PayoutPurpose(group_id=current_group().id, name=name))
                db.session.commit()
                audit.record('workbook.purpose', f'Added the payout purpose {name}')
                flash(f'Purpose {name} added.', 'success')
            return redirect(url_for('main.payout_purposes'))

        return render_template(
            'main/payout_purposes.html',
            version=current_app.version,
            purposes=PayoutPurpose.for_group().order_by(PayoutPurpose.is_active.desc(),
                                                        PayoutPurpose.name).all(),
        )

    @staticmethod
    @permission_required('edit_settings')
    def rename_payout_purpose(purpose_id):
        purpose = PayoutPurpose.get_for_group_or_404(purpose_id)
        name = WorkbookController._purpose_name(exclude_id=purpose.id)
        if name:
            old = purpose.name
            purpose.name = name
            db.session.commit()
            audit.record('workbook.purpose', f'Renamed the payout purpose {old} to {name}')
            flash(f'Purpose renamed to {name}. Update existing Payouts rows to match.', 'success')
        return redirect(url_for('main.payout_purposes'))

    @staticmethod
    @permission_required('edit_settings')
    def toggle_payout_purpose(purpose_id):
        """Retire or restore a purpose. Retired ones leave the template's dropdown."""
        purpose = PayoutPurpose.get_for_group_or_404(purpose_id)
        purpose.is_active = not purpose.is_active
        db.session.commit()
        audit.record('workbook.purpose',
                     f"{'Restored' if purpose.is_active else 'Retired'} the payout purpose {purpose.name}")
        flash(f"Purpose {purpose.name} {'restored' if purpose.is_active else 'retired'}.", 'success')
        return redirect(url_for('main.payout_purposes'))

    @staticmethod
    def _purpose_name(exclude_id=None):
        """The submitted purpose name, or None (with a message) if it can't be used."""
        name = ' '.join(request.form.get('name', '').split())
        if not name or len(name) > PURPOSE_MAX_LENGTH:
            flash(f'A purpose needs a name of up to {PURPOSE_MAX_LENGTH} characters.', 'danger')
            return None
        clash = PayoutPurpose.for_group().filter(db.func.lower(PayoutPurpose.name) == name.lower())
        if exclude_id is not None:
            clash = clash.filter(PayoutPurpose.id != exclude_id)
        if clash.first():
            flash(f'Your group already has a purpose called {name}.', 'danger')
            return None
        return name
