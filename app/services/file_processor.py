# app/services/file_processor.py
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from flask import current_app

class FileProcessor:
    """Utility class for processing file uploads"""
    
    @staticmethod
    def process_upload(request):
        """Process file upload from request"""
        use_google_sheets = request.form.get('input_method') == 'sheets' or request.form.get('use_google_sheets') == 'on'
        
        if use_google_sheets:
            return FileProcessor._process_google_sheets(request)
        else:
            return FileProcessor._process_file_upload(request)
    
    @staticmethod
    def _process_google_sheets(request):
        """Process Google Sheets upload"""
        from app.services.google_sheets_service import GoogleSheetsService
        from app.models.setting import Setting
        
        sheet_url = request.form.get('sheet_url', '')
        year = request.form.get('year', type=int)
        
        if not sheet_url:
            raise ValueError("Google Sheets URL is required")
        
        if not year:
            raise ValueError("Year is required")
        
        # Save Google Sheets URL
        Setting.set_value('google_sheets_url', sheet_url)
        
        # Get data from Google Sheets
        google_sheets_service = GoogleSheetsService()
        google_sheets_service.init_app(current_app)
        excel_data = google_sheets_service.get_sheet_as_excel(sheet_url, sheet_name=str(year))
        
        if excel_data is None:
            raise ValueError("Failed to fetch data from Google Sheets. Please check the URL and credentials.")
        
        # Save temporarily
        filename = f"google_sheet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        with open(filepath, 'wb') as f:
            f.write(excel_data.getvalue())
        
        current_app.logger.info(f"Saved Google Sheets data to: {filepath}")
        return filepath
    
    @staticmethod
    def _process_file_upload(request):
        """Process file upload from form"""
        if 'file' not in request.files:
            raise ValueError("No file selected")
        
        file = request.files['file']
        if file.filename == '':
            raise ValueError("No file selected")
        
        # Check file extension
        allowed_extensions = {'xlsx', 'xls', 'csv'}
        filename = secure_filename(file.filename)
        if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            raise ValueError("Invalid file type. Please upload Excel (.xlsx, .xls) or CSV files.")
        
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        current_app.logger.info(f"Saved uploaded file to: {filepath}")
        return filepath
    
    @staticmethod
    def cleanup_file(filepath):
        """Clean up temporary file if needed"""
        if filepath and os.path.exists(filepath) and 'google_sheet' in os.path.basename(filepath):
            try:
                os.remove(filepath)
                current_app.logger.info(f"Cleaned up temporary file: {filepath}")
            except Exception as e:
                current_app.logger.error(f"Error cleaning up file {filepath}: {str(e)}")