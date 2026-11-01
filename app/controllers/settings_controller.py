# app/controllers/settings_controller.py
"""
Settings management.

Only officers with edit_settings may write settings. The values are still
global; step 1e moves them into each group's settings.
"""
from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user

from app.decorators.permissions import permission_required
from app.models.setting import Setting


class SettingsController:
    """Handles system settings business logic."""

    # ==================== SETTINGS PAGE ====================

    @staticmethod
    @permission_required('edit_settings')
    def settings():
        """Settings page.

        GET  → render form pre-populated with current values.
        POST → validate and persist changes.
        """
        if request.method == 'POST':
            return SettingsController._handle_settings_update()

        return SettingsController._render_settings()

    @staticmethod
    def _handle_settings_update():
        """Persist submitted settings values."""
        sheet_url = request.form.get('sheet_url', '').strip()

        # Basic sanity check — must look like a URL if provided
        if sheet_url and not sheet_url.startswith(('http://', 'https://')):
            flash('Google Sheets URL must start with http:// or https://', 'danger')
            return redirect(url_for('main.settings'))

        Setting.set_value('google_sheets_url', sheet_url)

        current_app.logger.info(
            f"Settings updated by {current_user.email}: "
            f"google_sheets_url={'[set]' if sheet_url else '[cleared]'}"
        )
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('main.settings'))

    @staticmethod
    def _render_settings():
        """Render the settings page with current values."""
        sheet_url = Setting.get_value('google_sheets_url', '')

        return render_template(
            'main/settings.html',
            version=current_app.version,
            sheet_url=sheet_url,
        )

    # ==================== STATUS HELPERS ====================

    @staticmethod
    @login_required
    def get_google_sheets_status():
        """Return Google Sheets configuration status.

        """
        sheet_url = Setting.get_value('google_sheets_url', '')

        return {
            'configured': bool(sheet_url),
            'url': sheet_url if current_user.has_permission('edit_settings') else None,
            # Only expose the raw URL to settings editors; others just need configured: bool
        }

    @staticmethod
    @login_required
    def get_all_settings():
        """Return all settings as a dict — edit_settings only.

        Useful for a future settings API or debug page.
        """
        if not current_user.has_permission('edit_settings'):
            return {}

        return {
            'google_sheets_url': Setting.get_value('google_sheets_url', ''),
            'report_retention_days': Setting.get_value(
                'report_retention_days',
                str(current_app.config.get('REPORT_RETENTION_DAYS', 7))
            ),
        }