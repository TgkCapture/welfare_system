# app/controllers/workbook_controller.py
"""
The group's standard workbook: template download, sync history and warnings
(upload_data), and the group's payout purposes (edit_settings).
"""
from datetime import datetime

from flask import current_app, flash, redirect, render_template, request, send_file, url_for

from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.ledger import PayoutPurpose, SyncRun, YearSummary
from app.models.tenancy import current_group
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
            purpose.name = name
            db.session.commit()
            flash(f'Purpose renamed to {name}. Update existing Payouts rows to match.', 'success')
        return redirect(url_for('main.payout_purposes'))

    @staticmethod
    @permission_required('edit_settings')
    def toggle_payout_purpose(purpose_id):
        """Retire or restore a purpose. Retired ones leave the template's dropdown."""
        purpose = PayoutPurpose.get_for_group_or_404(purpose_id)
        purpose.is_active = not purpose.is_active
        db.session.commit()
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
