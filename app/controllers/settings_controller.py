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
from app.models.tenancy import current_group
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

        current_app.logger.info(
            f"Settings updated by {current_user.email} (group {settings.group_id}): "
            f"google_sheet_url={'[set]' if sheet_url else '[cleared]'}, "
            f"report_retention_days={retention or 'default'}"
        )
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
        flash('Branding updated.', 'success')
        return redirect(url_for('main.settings'))

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
