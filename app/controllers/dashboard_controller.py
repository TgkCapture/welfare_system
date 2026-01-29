# app/controllers/dashboard_controller.py
from flask import flash, render_template, redirect, request, url_for, session, jsonify, current_app
from flask_login import login_required, current_user
from app.decorators.permissions import role_required
from datetime import datetime, timedelta
import os
from sqlalchemy import func
from app.extensions import db

from app.models.user import User
from app.services.file_cleanup import FileCleanupService

class DashboardController:
    """Handles dashboard display logic only"""
    
    @staticmethod
    @login_required
    def dashboard():
        """Main dashboard - redirects based on user role"""
        if current_user.is_admin:
            return redirect(url_for('main.admin_dashboard'))
        elif current_user.is_clerk:
            return redirect(url_for('main.clerk_dashboard'))
        else:
            return redirect(url_for('main.viewer_dashboard'))
    
    @staticmethod
    @role_required('admin')
    def admin_dashboard():
        """Admin dashboard with system overview"""
        # Get user statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        users_by_role = db.session.query(
            User.role, 
            func.count(User.id).label('count')
        ).group_by(User.role).all()
        
        # Get recent logins
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_logins = User.query.filter(
            User.last_login.isnot(None),
            User.last_login >= seven_days_ago
        ).order_by(User.last_login.desc()).limit(10).all()
        
        # Get system statistics
        file_stats = DashboardController._get_file_statistics()
        
        # Get recent reports from session
        recent_reports = DashboardController._get_recent_reports()
        
        # Get Google Sheets status
        from app.controllers.settings_controller import SettingsController
        sheets_status = SettingsController.get_google_sheets_status()
        
        return render_template(
            'main/admin_dashboard.html',
            version=current_app.version,
            total_users=total_users,
            active_users=active_users,
            users_by_role=users_by_role,
            recent_logins=recent_logins,
            file_stats=file_stats,
            recent_reports=recent_reports,
            sheets_status=sheets_status,
            current_date=datetime.now()
        )
    
    @staticmethod
    @role_required('clerk')
    def clerk_dashboard():
        """Dashboard for clerks"""
        current_date = datetime.now()
        
        # Month names for the template
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        
        # Get Google Sheets status
        from app.controllers.settings_controller import SettingsController
        sheets_status = SettingsController.get_google_sheets_status()
        
        # Get recent reports
        from app.controllers.report_controller import ReportController
        recent_reports = ReportController._get_available_reports()

        from app.controllers.report_controller import ReportController
        paid_members_data = ReportController._get_paid_members_data()
        
        # Get clerk's activity statistics
        try:
            reports_generated = len(recent_reports)
            
            # Get recent login activity
            user = User.query.get(current_user.id)
            last_login = user.last_login.strftime('%B %d, %Y %I:%M %p') if user.last_login else 'Never'
            
        except Exception as e:
            current_app.logger.error(f"Error getting clerk stats: {str(e)}")
            reports_generated = 0
            last_login = 'Unknown'
        
        return render_template(
            'main/clerk_dashboard.html',
            version=current_app.version,
            current_date=current_date,
            month_names=month_names,
            sheets_status=sheets_status,
            recent_reports=recent_reports,
            paid_members_data=paid_members_data,
            reports_generated=reports_generated,
            last_login=last_login,
            user=current_user
        )
    
    @staticmethod
    @login_required
    def viewer_dashboard():
        """Dashboard for viewers"""
        current_date = datetime.now()
        
        # Month names for the template
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        
        # Get available reports
        from app.controllers.report_controller import ReportController
        available_reports = ReportController._get_available_reports()
        
        return render_template('main/viewer_dashboard.html',
                             version=current_app.version,
                             user_role=current_user.role,
                             available_reports=available_reports,
                             paid_members_data=0, #TODO: fix this
                             month_names=month_names, 
                             current_date=current_date)
    
    @staticmethod
    def _get_file_statistics():
        """Get file storage statistics"""
        upload_folder = current_app.config.get('UPLOAD_FOLDER', '')
        report_folder = current_app.config.get('REPORT_FOLDER', '')
        
        def get_folder_size(folder_path):
            if not os.path.exists(folder_path):
                return 0
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(folder_path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        total_size += os.path.getsize(fp)
            return total_size
        
        def count_files(folder_path):
            if not os.path.exists(folder_path):
                return 0
            count = 0
            for _, _, filenames in os.walk(folder_path):
                count += len(filenames)
            return count
        
        upload_size = get_folder_size(upload_folder)
        report_size = get_folder_size(report_folder)
        
        return {
            'upload_folder_size': upload_size,
            'report_folder_size': report_size,
            'upload_file_count': count_files(upload_folder),
            'report_file_count': count_files(report_folder),
            'total_size': upload_size + report_size
        }
    
    @staticmethod
    def _get_recent_reports():
        """Get recent reports from session"""
        if 'report_data' in session:
            report_data = session['report_data']
            return [{
                'month': report_data['month'],
                'year': report_data['year'],
                'total_contributions': report_data['total_contributions'],
                'contributors': report_data['num_contributors'],
                'generated_date': datetime.now().strftime('%Y-%m-%d')
            }]
        return []
    
    @staticmethod
    @role_required('admin') 
    def cleanup_files():
        """Admin endpoint to cleanup old files"""
        folder_sizes = None
        cleanup_result = None
        
        if request.method == 'POST':
            days_to_keep = request.form.get('days_to_keep', 7, type=int)
            cleanup_result = FileCleanupService.cleanup_old_files(days_to_keep)
            
            if cleanup_result.get('success'):
                flash(f"Cleaned up {cleanup_result['deleted_count']} old files", 'success')
            else:
                flash(f"Cleanup failed: {cleanup_result.get('error')}", 'error')
        
        folder_sizes = FileCleanupService.get_folder_sizes()
        
        return render_template(
            'main/cleanup.html',
            version=current_app.version,
            folder_sizes=folder_sizes,
            cleanup_result=cleanup_result
        )
    
    @staticmethod
    @login_required
    def storage_status():
        """API endpoint to check storage status"""
        folder_sizes = FileCleanupService.get_folder_sizes()
        return jsonify(folder_sizes)
    
    @staticmethod
    def version():
        """API endpoint to get application version"""
        return f"Current version: {current_app.version}"
    
    @staticmethod
    def health_check():
        """Health check endpoint for monitoring"""
        return {
            'status': 'healthy',
            'version': current_app.version,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def after_request(response):
        """Clean up session data after request"""
        session.modified = True
        return response