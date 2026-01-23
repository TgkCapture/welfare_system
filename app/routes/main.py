# app/routes/main.py
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, session, send_file, make_response, current_app
from flask_login import login_required, current_user
from app.decorators.permissions import role_required, permission_required
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
import pandas as pd
from sqlalchemy import desc, func
from datetime import timedelta
from app.extensions import db

from app.models.setting import Setting
from app.models.user import User
from app.services.excel_parser import ExcelParser
from app.services.report_generator import ReportGenerator
from app.services.image_generator import ImageGenerator
from app.services.google_sheets_service import GoogleSheetsService
from app.services.pdf_service import PDFGenerator
from app.services.file_cleanup import FileCleanupService

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
    """Main dashboard - redirects based on user role"""
    if current_user.is_admin or current_user.is_clerk:
        return redirect(url_for('main.upload_dashboard'))
    else:
        return redirect(url_for('main.viewer_dashboard'))

@main.route('/upload-dashboard')
@permission_required('upload_files')
def upload_dashboard():
    """Dashboard for users who can upload files (Admin & Clerk)"""
    from app.models.setting import Setting
    
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

@main.route('/viewer-dashboard')
@login_required
def viewer_dashboard():
    """Dashboard for viewers - shows available reports and paid members"""
    current_date = datetime.now()
    
    # Month names for the template
    month_names = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    # Get available reports from session or database
    available_reports = get_available_reports()
    
    # Get paid members data (for future implementation)
    paid_members_data = get_paid_members_data()
    
    # Get recent activity
    recent_activity = get_recent_activity()
    
    return render_template('main/viewer_dashboard.html',
                         version=current_app.version,
                         user_role=current_user.role,
                         available_reports=available_reports,
                         paid_members_data=paid_members_data,
                         recent_activity=recent_activity,
                         month_names=month_names, 
                         current_date=current_date)

def get_available_reports():
    """Get list of available reports (placeholder )"""
    
    if 'report_data' in session:
        report_data = session['report_data']
        return [{
            'month': report_data['month'],
            'year': report_data['year'],
            'total_contributions': report_data['total_contributions'],
            'contributors': report_data['num_contributors'],
            'defaulters': report_data['num_missing'],
            'generated_date': datetime.now().strftime('%Y-%m-%d'),
            'download_url': url_for('main.download_report')
        }]
    
    return []

def get_paid_members_data():
    """Get paid members data"""
    return {
        'total_paid': 0,
        'members': [],
        'last_updated': None
    }

def get_recent_activity():
    """Get recent activity """

    return []

@main.route('/upload', methods=['POST'])
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
            from app.services.file_cleanup import FileCleanupService
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

@main.route('/admin/cleanup', methods=['GET', 'POST'])
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

@main.route('/admin/storage-status')
@login_required
def storage_status():
    """API endpoint to check storage status"""
    folder_sizes = FileCleanupService.get_folder_sizes()
    return jsonify(folder_sizes)

@main.route('/reports')
@login_required
def reports_list():
    """View all available reports"""
    # Get all reports from database or storage
    available_reports = get_available_reports()
    
    return render_template('main/reports_list.html',
                         version=current_app.version,
                         reports=available_reports,
                         user_role=current_user.role)

@main.route('/paid-members')
@login_required
def paid_members_view():
    """View paid members list"""
    if 'report_data' not in session:
        flash('No report data available. Please generate a report first.', 'info')
        return redirect(url_for('main.viewer_dashboard'))
    
    report_data = session['report_data']
    
    # Convert data to DataFrame for processing
    data = pd.DataFrame(report_data['data'])
    
    paid_members = []
    try:
        month_col = report_data['month_col']
        name_col = report_data['name_col']
        
        for _, row in data.iterrows():
            member_name = row.get(name_col, '')
            payment = row.get(month_col, 0)
            
            try:
                payment_value = float(payment)
                if payment_value > 0:
                    paid_members.append({
                        'name': member_name,
                        'amount': payment_value,
                        'status': 'Paid'
                    })
            except (ValueError, TypeError):
                pass
        
    except Exception as e:
        current_app.logger.error(f"Error processing paid members: {str(e)}")
        paid_members = []
    
    return render_template('main/paid_members.html',
                         version=current_app.version,
                         paid_members=paid_members,
                         month=report_data['month'],
                         year=report_data['year'],
                         total_paid=len(paid_members))

@main.route('/admin')
@role_required('admin')
def admin_dashboard():
    """Admin dashboard with system overview and analytics"""
    from app.models.user import User
    from app.models.setting import Setting
    import os
    
    # Get user statistics
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    users_by_role = db.session.query(
        User.role, 
        func.count(User.id).label('count')
    ).group_by(User.role).all()
    
    # Get recent logins (last 7 days)
    seven_days_ago = datetime.now() - timedelta(days=7)
    recent_logins = User.query.filter(
        User.last_login.isnot(None),
        User.last_login >= seven_days_ago
    ).order_by(
        User.last_login.desc()
    ).limit(10).all()
    
    # Get system statistics
    try:
        # File statistics
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
        
        upload_size = get_folder_size(upload_folder)
        report_size = get_folder_size(report_folder)
        
        # Count files
        def count_files(folder_path):
            if not os.path.exists(folder_path):
                return 0
            count = 0
            for _, _, filenames in os.walk(folder_path):
                count += len(filenames)
            return count
        
        upload_count = count_files(upload_folder)
        report_count = count_files(report_folder)
        
        file_stats = {
            'upload_folder_size': upload_size,
            'report_folder_size': report_size,
            'upload_file_count': upload_count,
            'report_file_count': report_count,
            'total_size': upload_size + report_size
        }
    except Exception as e:
        current_app.logger.error(f"Error getting file stats: {str(e)}")
        file_stats = {}
    
    # Get recent reports from session
    recent_reports = []
    if 'report_data' in session:
        report_data = session['report_data']
        recent_reports = [{
            'month': report_data['month'],
            'year': report_data['year'],
            'total_contributions': report_data['total_contributions'],
            'contributors': report_data['num_contributors'],
            'generated_date': datetime.now().strftime('%Y-%m-%d')
        }]
    
    # Get Google Sheets status
    sheet_url = Setting.get_value('google_sheets_url', '')
    sheets_status = {
        'configured': bool(sheet_url),
        'url': sheet_url
    }
    
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

@main.route('/admin/users')
@role_required('admin')
def admin_users():
    """User management page - list all users"""
    from app.models.user import User
    
    users = User.query.order_by(
        User.created_at.desc()
    ).all()
    
    return render_template(
        'main/admin_users.html',
        version=current_app.version,
        users=users,
        current_user=current_user
    )

@main.route('/admin/users/create', methods=['GET', 'POST'])
@role_required('admin')
def create_user():
    """Create a new user"""
    from app.auth.forms import RegisterForm
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        User = get_user_model()
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Email already registered', 'danger')
            return redirect(url_for('main.create_user'))
        
        try:
            new_user = User(
                email=form.email.data,
                password=generate_password_hash(form.password.data, method='scrypt'),
                role=form.role.data
            )
            db.session.add(new_user)
            db.session.commit()
            
            flash(f'User {new_user.email} created successfully as {new_user.role}!', 'success')
            return redirect(url_for('main.admin_users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'User creation failed: {str(e)}', 'danger')
    
    return render_template(
        'main/create_user.html',
        version=current_app.version,
        form=form
    )

def get_user_model():
    """Get the User model - handles circular imports"""
    from app.models.user import User
    return User

@main.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_user(user_id):
    """Edit user details"""
    from app.auth.forms import UserEditForm
    from app.models.user import User
    
    user = User.query.get_or_404(user_id)
    
    # Prevent editing self (admin should use profile page)
    if user.id == current_user.id:
        flash('Please use your profile page to edit your own account.', 'info')
        return redirect(url_for('auth.profile'))
    
    form = UserEditForm(obj=user)
    
    if form.validate_on_submit():
        try:
            user.email = form.email.data
            user.role = form.role.data
            user.is_active = form.is_active.data
            
            # Update password if provided
            if form.new_password.data:
                user.password = generate_password_hash(form.new_password.data, method='scrypt')
            
            db.session.commit()
            flash(f'User {user.email} updated successfully!', 'success')
            return redirect(url_for('main.admin_users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Update failed: {str(e)}', 'danger')
    
    return render_template(
        'main/edit_user.html',
        version=current_app.version,
        form=form,
        user=user
    )

@main.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@role_required('admin')
def delete_user(user_id):
    """Delete a user"""
    from app.models.user import User
    
    user = User.query.get_or_404(user_id)
    
    # Prevent self-deletion
    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('main.admin_users'))
    
    try:
        email = user.email
        db.session.delete(user)
        db.session.commit()
        flash(f'User {email} deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Deletion failed: {str(e)}', 'danger')
    
    return redirect(url_for('main.admin_users'))

@main.route('/admin/users/<int:user_id>/toggle-active', methods=['POST'])
@role_required('admin')
def toggle_user_active(user_id):
    """Toggle user active status"""
    from app.models.user import User
    
    user = User.query.get_or_404(user_id)
    
    # Prevent deactivating self
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('main.admin_users'))
    
    try:
        user.is_active = not user.is_active
        db.session.commit()
        
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {user.email} {status} successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Update failed: {str(e)}', 'danger')
    
    return redirect(url_for('main.admin_users'))