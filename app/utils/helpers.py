# app/utils/helpers.py
from datetime import datetime
import os

from flask import current_app

from app.models.setting import Setting
from app.services.google_sheets_service import GoogleSheetsService

class FileProcessor:
    @staticmethod
    def process_upload(request):
        """Process file upload from request"""
        use_google_sheets = request.form.get('use_google_sheets') == 'on'
        
        if use_google_sheets:
            return FileProcessor._process_google_sheets(request)
        else:
            return FileProcessor._process_file_upload(request)
    
    @staticmethod
    def _process_google_sheets(request):
        """Process Google Sheets upload"""
        sheet_url = request.form.get('sheet_url', '')
        year = request.form.get('year', type=int)
        
        # Save Google Sheets URL
        Setting.set_value('google_sheets_url', sheet_url)
        
        # Get data from Google Sheets
        excel_data = GoogleSheetsService().get_sheet_as_excel(sheet_url, sheet_name=str(year))
        if excel_data is None:
            raise ValueError("Failed to fetch data from Google Sheets")
        
        # Save temporarily
        filename = f"google_sheet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        with open(filepath, 'wb') as f:
            f.write(excel_data.getvalue())
        
        return filepath
    
    @staticmethod
    def _process_file_upload(request):
        """Process file upload from form"""
        from werkzeug.utils import secure_filename
        
        if 'file' not in request.files:
            raise ValueError("No file selected")
        
        file = request.files['file']
        if file.filename == '':
            raise ValueError("No file selected")
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        return filepath
    
    @staticmethod
    def cleanup_file(filepath):
        """Clean up temporary file if needed"""
        if filepath and os.path.exists(filepath) and 'google_sheet' in os.path.basename(filepath):
            try:
                os.remove(filepath)
            except:
                pass

class ReportDataSerializer:
    @staticmethod
    def serialize(data, report_path):
        """Serialize report data for session storage"""
        return {
            'report_data': {
                'data': data['data'].to_dict('records'),
                'month_col': data['month_col'],
                'name_col': data['name_col'],
                'month': data['month'],
                'year': data['year'],
                'total_contributions': float(data['total_contributions']),
                'num_contributors': int(data['num_contributors']),
                'num_missing': int(data['num_missing']),
                'money_dispensed': float(data['money_dispensed']) if data.get('money_dispensed') else None,
                'total_book_balance': float(data['total_book_balance']) if data.get('total_book_balance') else None,
                'report_filename': f"contributions_report_{data['year']}_{data['month']}.pdf"
            },
            'report_path': report_path
        }