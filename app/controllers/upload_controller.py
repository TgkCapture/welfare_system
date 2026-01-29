# app/controllers/upload_controller.py
from flask import render_template, request, flash, redirect, url_for, session, current_app
from flask_login import login_required, current_user
from app.decorators.permissions import permission_required
from datetime import datetime

from app.models.setting import Setting
from app.services.excel_parser import ExcelParser
from app.services.report_generator import ReportGenerator
from app.services.file_cleanup import FileCleanupService
from app.services.file_processor import FileProcessor
from app.services.report_serializer import ReportDataSerializer

class UploadController:
    """Handles file upload business logic"""
    
    @staticmethod
    @permission_required('upload_files')
    def upload_dashboard():
        """Dashboard for users who can upload files (Admin & Clerk)"""
        sheet_url = Setting.get_value('google_sheets_url', current_app.config.get('DEFAULT_SHEET_URL', ''))
        current_date = datetime.now()
        
        # Month names for the template
        month_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        
        recent_reports = []  # Placeholder for now
        
        return render_template('main/upload_dashboard.html', 
                             version=current_app.version,
                             sheet_url=sheet_url,
                             year=current_date.year,  
                             month=current_date.month,
                             month_names=month_names,
                             user_role=current_user.role,
                             recent_reports=recent_reports)
    
    @staticmethod
    @permission_required('upload_files')
    def upload():
        """Handle file upload and report generation"""
        try:
            # Process upload
            filepath = FileProcessor.process_upload(request)
            
            # Get year and month
            year = request.form.get('year', type=int)
            month = request.form.get('month', type=int)
            
            if not year or not month:
                flash('Year and month are required', 'error')
                return redirect(url_for('main.upload_dashboard'))
            
            # Parse Excel data
            data = ExcelParser.parse_excel(filepath, year=year, month=month)
            
            # Generate report
            report_path = ReportGenerator.generate_contribution_report(
                data, 
                current_app.config['REPORT_FOLDER']
            )
            
            # Store in session
            session.update(ReportDataSerializer.serialize(data, report_path))
            
            # Cleanup temporary file
            FileProcessor.cleanup_file(filepath)
            
            # Run quick cleanup of very old files (> 30 days)
            try:
                FileCleanupService.cleanup_old_files(days_to_keep=30)
            except Exception as e:
                current_app.logger.warning(f"Quick cleanup failed: {str(e)}")
            
            flash('Report generated successfully!', 'success')
            return redirect(url_for('main.report_preview'))
            
        except ValueError as e:
            current_app.logger.warning(f"Upload validation error: {str(e)}")
            flash(str(e), 'error')
            return redirect(url_for('main.upload_dashboard'))
            
        except Exception as e:
            current_app.logger.error(f"Upload error: {str(e)}")
            flash(f'Error generating report: {str(e)}', 'error')
            return redirect(url_for('main.upload_dashboard'))