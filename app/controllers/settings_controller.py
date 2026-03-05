# app/controllers/settings_controller.py
from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required
from app.models.setting import Setting

class SettingsController:
    """Handles system settings business logic"""
    
    @staticmethod
    @login_required
    def settings():
        """Application settings page"""
        if request.method == 'POST':
            sheet_url = request.form.get('sheet_url', '')
            Setting.set_value('google_sheets_url', sheet_url)
            flash('Settings updated successfully', 'success')
            return redirect(url_for('main.settings'))
        
        sheet_url = Setting.get_value('google_sheets_url', '')
        return render_template('main/settings.html', 
                             version=current_app.version,
                             sheet_url=sheet_url)
    
    @staticmethod
    @login_required
    def get_google_sheets_status():
        """Get Google Sheets configuration status"""
        sheet_url = Setting.get_value('google_sheets_url', '')
        return {
            'configured': bool(sheet_url),
            'url': sheet_url
        }