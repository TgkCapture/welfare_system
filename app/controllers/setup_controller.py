# app/controllers/setup_controller.py
"""
The setup checklist page, and hiding or showing it on the dashboard
(officers who manage officers or edit settings).
"""
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.tenancy import current_group
from app.services import audit, setup, support


class SetupController:

    @staticmethod
    @login_required
    def checklist():
        if current_user.is_superadmin and not support.is_active():
            return redirect(url_for('platform.dashboard'))
        group = current_group()
        return render_template('main/setup.html', version=current_app.version, **setup.progress(group),
                               dismissed=group.settings.setup_dismissed)

    @staticmethod
    @login_required
    def toggle():
        """Hide the checklist from the dashboard, or bring it back."""
        if not (current_user.has_permission('manage_users') or current_user.has_permission('edit_settings')):
            abort(403)
        settings = current_group().settings
        settings.setup_dismissed = request.form.get('action') == 'hide'
        db.session.commit()
        audit.record('settings.setup', 'Hid the setup checklist' if settings.setup_dismissed
                     else 'Showed the setup checklist again')
        if settings.setup_dismissed:
            flash('Setup checklist hidden. You can always find it under Settings.', 'info')
            return redirect(url_for('main.dashboard'))
        return redirect(url_for('main.setup'))
