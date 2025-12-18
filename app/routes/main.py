# app/routes/main.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, make_response, current_app
from flask_login import login_required, current_user
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import pandas as pd

from app.models.setting import Setting
from app.services.excel_parser import ExcelParser
from app.services.report_generator import ReportGenerator
from app.services.image_generator import ImageGenerator
from app.services.google_sheets_service import GoogleSheetsService
from app.services.pdf_service import PDFGenerator

main = Blueprint('main', __name__)

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

class ReportDataSerializer:
    """Utility class for serializing report data"""
    
    @staticmethod
    def serialize(data, report_path):
        """Serialize report data for session storage"""
        # Ensure data['data'] is a DataFrame
        if isinstance(data['data'], pd.DataFrame):
            data_dict = data['data'].to_dict('records')
        else:
            data_dict = data['data']
        
        # Convert numeric values
        money_dispensed = data.get('money_dispensed')
        total_book_balance = data.get('total_book_balance')
        
        # Handle None values for numeric fields
        if money_dispensed is not None:
            try:
                money_dispensed = float(money_dispensed)
            except (ValueError, TypeError):
                money_dispensed = None
        
        if total_book_balance is not None:
            try:
                total_book_balance = float(total_book_balance)
            except (ValueError, TypeError):
                total_book_balance = None
        
        return {
            'report_data': {
                'data': data_dict,
                'month_col': data['month_col'],
                'name_col': data['name_col'],
                'month': data['month'],
                'year': data['year'],
                'total_contributions': float(data['total_contributions']),
                'num_contributors': int(data['num_contributors']),
                'num_missing': int(data['num_missing']),
                'money_dispensed': money_dispensed,
                'total_book_balance': total_book_balance,
                'report_filename': f"contributions_report_{data['year']}_{data['month']}.pdf"
            },
            'report_path': report_path
        }

@main.route('/')
@login_required
def dashboard():
    from app.models.setting import Setting
    
    sheet_url = Setting.get_value('google_sheets_url', current_app.config.get('DEFAULT_SHEET_URL', ''))
    current_date = datetime.now()
    
    # Month names for the template
    month_names = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    return render_template('main/dashboard.html', 
                         version=current_app.version,
                         sheet_url=sheet_url,
                         year=current_date.year,  
                         month=current_date.month,
                         month_names=month_names)

@main.route('/upload', methods=['POST'])
@login_required
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
            return redirect(url_for('main.dashboard'))
        
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
        
        return redirect(url_for('main.report_preview'))
        
    except ValueError as e:
        current_app.logger.warning(f"Upload validation error: {str(e)}")
        flash(str(e), 'error')
        return redirect(url_for('main.dashboard'))
        
    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/report-preview')
@login_required
def report_preview():
    """Preview generated report"""
    if 'report_data' not in session:
        flash('No report data available. Please generate a report first.', 'error')
        return redirect(url_for('main.dashboard'))
    
    report_data = session['report_data']
    
    return render_template(
        'main/report_preview.html',
        version=current_app.version,
        month=report_data['month'],
        year=report_data['year'],
        total_contributions=report_data['total_contributions'],
        contributors=report_data['num_contributors'],
        defaulters=report_data['num_missing'],
        money_dispensed=report_data.get('money_dispensed'),
        total_book_balance=report_data.get('total_book_balance'),
        filename=report_data['report_filename'],
        current_date=datetime.now()
    )

@main.route('/download-report')
@login_required
def download_report():
    """Download generated PDF report"""
    if 'report_path' not in session:
        flash('No report available for download', 'error')
        return redirect(url_for('main.dashboard'))
    
    report_path = session['report_path']
    
    if not os.path.exists(report_path):
        flash('Report file not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # Get filename from session or use default
        download_filename = session.get('report_data', {}).get(
            'report_filename',
            f"contributions_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        
        return send_file(
            report_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype='application/pdf'
        )
    except Exception as e:
        current_app.logger.error(f"Error downloading report: {str(e)}")
        flash(f'Error downloading report: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/download-paid-members')
@login_required
def download_paid_members():
    """Download paid members as PNG image"""
    if 'report_data' not in session:
        flash('No report data available', 'error')
        return redirect(url_for('main.report_preview'))
    
    try:
        report_data = session['report_data']

        # Convert data back to DataFrame if needed
        data = {
            'data': pd.DataFrame(report_data['data']),
            'month_col': report_data['month_col'],
            'name_col': report_data['name_col'],
            'month': report_data['month'],
            'year': report_data['year'],
            'total_contributions': report_data['total_contributions'],
            'num_contributors': report_data['num_contributors'],
            'num_missing': report_data['num_missing'],
            'money_dispensed': report_data.get('money_dispensed'),
            'total_book_balance': report_data.get('total_book_balance')
        }
        
        # Generate image
        img_buffer = ImageGenerator.generate_paid_members_image(data)
        
        if img_buffer is None:
            flash('No paid members to display', 'info')
            return redirect(url_for('main.report_preview'))
            
        return send_file(
            img_buffer,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"paid_members_{data['month']}_{data['year']}.png"
        )
    except Exception as e:
        current_app.logger.error(f"Error generating image: {str(e)}")
        flash('Error generating paid members image', 'error')
        return redirect(url_for('main.report_preview'))

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Application settings page"""
    from app.models.setting import Setting
    
    if request.method == 'POST':
        sheet_url = request.form.get('sheet_url', '')
        Setting.set_value('google_sheets_url', sheet_url)
        flash('Settings updated successfully', 'success')
        return redirect(url_for('main.settings'))
    
    sheet_url = Setting.get_value('google_sheets_url', '')
    return render_template('main/settings.html', 
                         version=current_app.version,
                         sheet_url=sheet_url)

@main.route('/welfare-rules')
def welfare_rules():
    """Public endpoint for welfare rules - no login required"""
    return render_template('main/welfare_rules.html', 
                         version=current_app.version)

@main.route('/download-welfare-rules-pdf')
def download_welfare_rules_pdf():
    """Download welfare rules as PDF using ReportLab"""
    try:
        # Generate PDF
        pdf_content = PDFGenerator.generate_welfare_rules_pdf()
        
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = \
            'attachment; filename=mzugoss_welfare_rules.pdf'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"PDF download failed: {str(e)}")
        # Fallback to print functionality
        flash('PDF generation unavailable. Using print to PDF instead.', 'warning')
        return redirect(url_for('main.welfare_rules'))

@main.route('/version')
def version():
    """API endpoint to get application version"""
    return f"Current version: {current_app.version}"

@main.route('/api/health')
def health_check():
    """Health check endpoint for monitoring"""
    return {
        'status': 'healthy',
        'version': current_app.version,
        'timestamp': datetime.now().isoformat()
    }

# Session cleanup middleware
@main.after_request
def after_request(response):
    """Clean up session data after request"""
    # Clear flash messages after they're displayed
    session.modified = True
    return response