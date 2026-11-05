# app/controllers/settings_controller.py
"""
Group settings (requires edit_settings).

Each group has its own Google Sheet URL and report retention period,
stored in its GroupSettings row.
"""
import re

from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user

from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.group import new_access_code
from app.models.tenancy import current_group
from app.services import audit, logo, setup
from app.services.branding import is_valid_color

MAX_RETENTION_DAYS = 3650


class SettingsController:
    """Handles group settings business logic."""

    # ==================== SETTINGS PAGE ====================

    @staticmethod
    @permission_required('edit_settings')
    def settings():
        """Settings page.

        GET  → render form pre-populated with current values.
        POST → validate and persist changes.
        """
        if request.method == 'POST':
            if request.form.get('section') == 'branding':
                return SettingsController._handle_branding_update()
            return SettingsController._handle_settings_update()

        return SettingsController._render_settings()

    @staticmethod
    def _handle_settings_update():
        """Persist submitted settings values."""
        settings = current_group().settings
        sheet_url = request.form.get('sheet_url', '').strip()
        retention = request.form.get('report_retention_days', '').strip()

        # Basic sanity check — must look like a URL if provided
        if sheet_url and not sheet_url.startswith(('http://', 'https://')):
            flash('Google Sheets URL must start with http:// or https://', 'danger')
            return redirect(url_for('main.settings'))

        if retention and not (retention.isdigit() and 1 <= int(retention) <= MAX_RETENTION_DAYS):
            flash(f'Retention must be a whole number of days between 1 and {MAX_RETENTION_DAYS}.',
                  'danger')
            return redirect(url_for('main.settings'))

        settings.google_sheet_url = sheet_url or None
        settings.report_retention_days = int(retention) if retention else None
        db.session.commit()

        audit.record('settings.data_source', 'Changed the Google Sheet and report retention',
                     details={'google_sheet_url': sheet_url or None,
                              'report_retention_days': int(retention) if retention else None})
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('main.settings'))

    @staticmethod
    def _handle_branding_update():
        """How the group is named on its pages and reports."""
        settings = current_group().settings
        text = lambda name: ' '.join(request.form.get(name, '').split())
        display_name, short_name = text('display_name'), text('short_name')
        report_title, currency = text('report_title'), text('currency').upper()
        color = request.form.get('primary_color', '').strip()

        problems = []
        if not display_name or len(display_name) > 150:
            problems.append('The group name is needed (up to 150 characters).')
        if len(short_name) > 30:
            problems.append('The short name can be up to 30 characters.')
        if len(report_title) > 200:
            problems.append('The report title can be up to 200 characters.')
        if not re.fullmatch(r'[A-Z]{3}', currency):
            problems.append('The currency must be a three-letter code, such as MWK.')
        if not is_valid_color(color):
            problems.append('Choose a colour.')
        if problems:
            for problem in problems:
                flash(problem, 'danger')
            return redirect(url_for('main.settings'))

        settings.display_name, settings.short_name = display_name, short_name or None
        settings.report_title, settings.currency = report_title or None, currency
        settings.primary_color = color.lower()
        db.session.commit()

        group = current_group()
        upload = request.files.get('logo')
        try:
            if upload and upload.filename:
                logo.save(group, upload)
            elif request.form.get('remove_logo'):
                logo.remove(group)
        except logo.LogoError as e:
            audit.record('settings.branding', 'Changed the branding (the new logo was refused)',
                         details={'display_name': display_name, 'color': color.lower()})
            flash(f'Branding saved, but the logo was not: {e}', 'warning')
            return redirect(url_for('main.settings'))
        logo_note = (' and uploaded a new logo' if upload and upload.filename
                     else ' and removed the logo' if request.form.get('remove_logo') else '')
        audit.record('settings.branding', f'Changed the branding{logo_note}',
                     details={'display_name': display_name, 'short_name': short_name or None,
                              'report_title': report_title or None, 'currency': currency,
                              'color': color.lower()})
        setup.mark(group, 'branding')
        flash('Branding updated.', 'success')
        return redirect(url_for('main.settings'))

    # ==================== PUBLIC PAGES ====================

    @staticmethod
    @permission_required('edit_settings')
    def public_pages():
        """What the group's public pages show, and the group access code."""
        group = current_group()
        settings = group.settings
        action = request.form.get('action')

        if action == 'options':
            months = request.form.get('public_months_back', '').strip()
            if not (months.isdigit() and 1 <= int(months) <= 120):
                flash('Months that can be browsed must be between 1 and 120.', 'danger')
            else:
                settings.public_paid_enabled = bool(request.form.get('public_paid_enabled'))
                settings.public_show_amounts = bool(request.form.get('public_show_amounts'))
                settings.public_show_totals = bool(request.form.get('public_show_totals'))
                settings.public_months_back = int(months)
                db.session.commit()
                audit.record('settings.public', 'Changed what the public pages show',
                             details={'paid_list': settings.public_paid_enabled,
                                      'amounts': settings.public_show_amounts,
                                      'totals': settings.public_show_totals,
                                      'months_back': settings.public_months_back})
                flash('Public page options saved.', 'success')
        elif action == 'new_code':
            settings.access_code, settings.access_code_enabled = new_access_code(), True
            db.session.commit()
            audit.record('settings.access_code', 'Made a new group access code')
            flash('New group code made. Share it in the group: the old code no longer works.', 'success')
        elif action == 'set_code':
            code = ''.join(request.form.get('code', '').split()).upper()
            if not re.fullmatch(r'[A-Z0-9]{4,20}', code):
                flash('A group code must be 4 to 20 letters or digits.', 'danger')
            else:
                settings.access_code, settings.access_code_enabled = code, True
                db.session.commit()
                audit.record('settings.access_code', 'Changed the group access code')
                flash('Group code changed. Share it in the group: the old code no longer works.', 'success')
        elif action == 'toggle_code':
            settings.access_code_enabled = not settings.access_code_enabled
            if settings.access_code_enabled and not settings.access_code:
                settings.access_code = new_access_code()
            db.session.commit()
            audit.record('settings.access_code', 'Turned the group access code '
                         + ('on' if settings.access_code_enabled else 'off'))
            flash('Group code turned ' + ('on.' if settings.access_code_enabled
                                          else 'off: anyone with the link can see who has paid.'),
                  'success' if settings.access_code_enabled else 'warning')
        if action:
            return redirect(url_for('main.public_pages'))
        setup.mark(group, 'public')     # seen: what members see and the code to share

        return render_template('main/public_pages.html', version=current_app.version, settings=settings,
                               slug=group.slug)

    @staticmethod
    def _render_settings():
        """Render the settings page with current values."""
        settings = current_group().settings

        return render_template(
            'main/settings.html',
            version=current_app.version,
            settings=settings,
            sheet_url=settings.google_sheet_url or '',
            retention_days=settings.report_retention_days,
            default_retention_days=current_app.config.get('REPORT_RETENTION_DAYS', 7),
            max_retention_days=MAX_RETENTION_DAYS,
            service_account_email=SettingsController._service_account_email(),
            custom_layout=bool(settings.sheet_mapping),
        )

    @staticmethod
    def _service_account_email():
        from app.services.google_sheets_service import GoogleSheetsService
        return GoogleSheetsService().service_account_email()

    # ==================== STATUS HELPERS ====================

    @staticmethod
    @login_required
    def get_google_sheets_status():
        """Return whether the current group has a Google Sheet configured."""
        group = current_group()
        sheet_url = group.settings.google_sheet_url if group else None

        return {
            'configured': bool(sheet_url),
            # Only expose the raw URL to settings editors; others just need configured: bool
            'url': sheet_url if current_user.has_permission('edit_settings') else None,
        }
