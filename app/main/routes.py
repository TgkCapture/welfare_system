# === app/main/routes.py ===
from flask import Blueprint, make_response, render_template, request, redirect, url_for, current_app, send_file, flash, session, jsonify, send_from_directory
from flask_login import login_required, current_user
import os
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime
import io
from .utils import parse_excel, generate_report, generate_paid_members_image
from app.google_sheets import google_sheets_service
from app.models import Setting
from app.main.pdf_utils import PDFGenerator, ShareUtils, WelfareRulesData

main = Blueprint('main', __name__)

@main.route('/')
@login_required
def dashboard():
    # Get the stored Google Sheets URL if available
    sheet_url = Setting.get_value('google_sheets_url', current_app.config.get('DEFAULT_SHEET_URL', ''))
    
    current_date = datetime.now()
    current_year = current_date.year
    current_month = current_date.month
    
    return render_template('dashboard.html', 
                         version=current_app.version, 
                         datetime=datetime,
                         sheet_url=sheet_url,
                         year=current_year,  
                         month=current_month)  

@main.route('/version')
def version():
    return f"Current version: {current_app.version}"

@main.route('/upload', methods=['POST'])
@login_required
def upload():
    # Check if using Google Sheets
    use_google_sheets = request.form.get('use_google_sheets') == 'on'
    sheet_url = request.form.get('sheet_url', '')
    filepath = None
    
    try:
        # Process the file (same logic for both sources)
        year = request.form.get('year', type=int)
        month = request.form.get('month', type=int)
        
        if not year or not month:
            flash('Year and month are required', 'error')
            return redirect(url_for('main.dashboard'))
        
        if use_google_sheets and sheet_url:
            current_app.logger.info(f"Fetching data from Google Sheets: {sheet_url} for year {year}")
            
            excel_data = google_sheets_service.get_sheet_as_excel(sheet_url, sheet_name=str(year))
            if excel_data is None:
                flash('Failed to fetch data from Google Sheets. Please check the URL and credentials.', 'error')
                return redirect(url_for('main.dashboard'))
            
            # Save temporarily
            filename = f"google_sheet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            
            with open(filepath, 'wb') as f:
                f.write(excel_data.getvalue())

            Setting.set_value('google_sheets_url', sheet_url)
            current_app.logger.info(f"Saved Google Sheets data to: {filepath}")
            
        else:
            # Original file upload logic
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(url_for('main.dashboard'))
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(url_for('main.dashboard'))
            
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            current_app.logger.info(f"Saved uploaded file to: {filepath}")
        
        data = parse_excel(filepath, year=year, month=month)
        
        report_data = {
            'data': data['data'].to_dict('records'),
            'month_col': data['month_col'],
            'name_col': data['name_col'],
            'month': data['month'],
            'year': data['year'],
            'total_contributions': float(data['total_contributions']),
            'num_contributors': int(data['num_contributors']),
            'num_missing': int(data['num_missing']),
            'money_dispensed': float(data['money_dispensed']) if data.get('money_dispensed') is not None else None,
            'total_book_balance': float(data['total_book_balance']) if data.get('total_book_balance') is not None else None,
            'report_filename': f"contributions_report_{data['year']}_{data['month']}.pdf"
        }
        
        # Store in session
        session['report_data'] = report_data
        
        report_path = generate_report(data, filename)
        session['report_path'] = report_path
        
        # Clean up temporary file if from Google Sheets
        if use_google_sheets and filepath and os.path.exists(filepath):
            os.remove(filepath)
            current_app.logger.info(f"Cleaned up temporary file: {filepath}")
        
        return redirect(url_for('main.report_preview'))
        
    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")

        if use_google_sheets and filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
                
        flash(f'Error generating report: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        sheet_url = request.form.get('sheet_url', '')
        Setting.set_value('google_sheets_url', sheet_url)
        flash('Settings updated successfully', 'success')
        return redirect(url_for('main.settings'))
    
    sheet_url = Setting.get_value('google_sheets_url', '')
    return render_template('settings.html', sheet_url=sheet_url)

@main.route('/report-preview')
@login_required
def report_preview():
    if 'report_data' not in session:
        flash('No report data available', 'error')
        return redirect(url_for('main.dashboard'))
    
    report_data = session['report_data']
    
    return render_template(
        'report_preview.html',
        month=report_data['month'],
        year=report_data['year'],
        total_contributions=report_data['total_contributions'],  
        contributors=report_data['num_contributors'],  
        defaulters=report_data['num_missing'],  
        money_dispensed=report_data.get('money_dispensed'),
        total_book_balance=report_data.get('total_book_balance'),
        filename=report_data['report_filename']
    )

@main.route('/download-report')
@login_required
def download_report():
    if 'report_path' not in session:
        flash('No report available for download', 'error')
        return redirect(url_for('main.dashboard'))
    
    report_path = session['report_path']
    if not os.path.exists(report_path):
        flash('Report file not found', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        download_filename = session.get('report_data', {}).get(
            'report_filename',
            f"contributions_report_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        
        return send_file(
            report_path,
            as_attachment=True,
            download_name=download_filename
        )
    except Exception as e:
        flash(f'Error downloading report: {str(e)}', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/download-paid-members')
@login_required
def download_paid_members():
    if 'report_data' not in session:
        flash('No report data available', 'error')
        return redirect(url_for('main.report_preview'))
    
    try:
        report_data = session['report_data']

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
        
        img_buffer = generate_paid_members_image(data)
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

# ==================== WELFARE RULES ROUTES ====================

@main.route('/rules')
@main.route('/welfare-rules')
def welfare_rules():
    """Public endpoint for welfare rules - no login required"""
    # Get welfare rules data from centralized source
    welfare_data = WelfareRulesData.get_summary()
    
    return render_template('welfare_rules.html', 
                         version=current_app.version,
                         welfare_data=welfare_data,
                         funeral_eligibility=WelfareRulesData.get_funeral_eligibility(),
                         penalty_info=WelfareRulesData.get_penalty_info(),
                         benefit_scenarios=WelfareRulesData.get_benefit_scenarios())

@main.route('/welfare-rules/pdf')
def download_welfare_rules_pdf():
    """Download welfare rules as PDF using ReportLab"""
    try:
        # Generate PDF using ReportLab
        pdf_content = PDFGenerator.generate_welfare_rules_pdf()
        
        # Create response
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = \
            'attachment; filename=mzugoss_welfare_rules_v2.pdf'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"PDF download failed: {str(e)}")
        flash('PDF generation is temporarily unavailable. Please try the HTML download option instead.', 'warning')
        return redirect(url_for('main.welfare_rules'))

@main.route('/welfare-rules/html-download')
def download_welfare_rules_html():
    """Download welfare rules as HTML file"""
    try:
        # Read the HTML template
        html_content = render_template(
            'welfare_rules_pdf.html', 
            now=datetime.now(), 
            version='2.0'
        )
        
        # Create response
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html'
        response.headers['Content-Disposition'] = \
            'attachment; filename=mzugoss_welfare_rules_v2.html'
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"HTML download failed: {str(e)}")
        flash('HTML download failed. Please try again later.', 'error')
        return redirect(url_for('main.welfare_rules'))

@main.route('/welfare-rules/print')
def print_welfare_rules():
    """Special print-friendly version of welfare rules"""
    return render_template('welfare_rules_print.html',
                         version=current_app.version,
                         welfare_data=WelfareRulesData.get_summary(),
                         funeral_eligibility=WelfareRulesData.get_funeral_eligibility(),
                         penalty_info=WelfareRulesData.get_penalty_info(),
                         benefit_scenarios=WelfareRulesData.get_benefit_scenarios())

@main.route('/welfare-rules/share/<share_type>')
def share_welfare_rules(share_type):
    """Share welfare rules on different platforms"""
    valid_share_types = ['whatsapp', 'email', 'sms', 'twitter', 'facebook']
    
    if share_type not in valid_share_types:
        flash('Invalid share type', 'error')
        return redirect(url_for('main.welfare_rules'))
    
    try:
        share_url = ShareUtils.get_share_url(share_type)
        return redirect(share_url)
    except Exception as e:
        current_app.logger.error(f"Share error: {str(e)}")
        flash('Sharing failed. Please copy the link manually.', 'error')
        return redirect(url_for('main.welfare_rules'))

@main.route('/welfare-rules/copy-link')
def copy_welfare_rules_link():
    """API endpoint to get share link for copying"""
    share_text = ShareUtils.get_share_text('general')
    return jsonify({
        'success': True,
        'url': share_text['url'],
        'message': 'Link copied to clipboard'
    })

@main.route('/welfare-rules/api/data')
def welfare_rules_api_data():
    """API endpoint for welfare rules data (for AJAX requests)"""
    try:
        return jsonify({
            'success': True,
            'summary': WelfareRulesData.get_summary(),
            'funeral_eligibility': WelfareRulesData.get_funeral_eligibility(),
            'penalty_info': WelfareRulesData.get_penalty_info(),
            'benefit_scenarios': WelfareRulesData.get_benefit_scenarios()
        })
    except Exception as e:
        current_app.logger.error(f"API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ==================== STATIC FILES ====================

@main.route('/static/css/pdf_styles.css')
def serve_pdf_styles():
    """Serve PDF CSS file"""
    return send_from_directory('static/css', 'pdf_styles.css')

@main.route('/static/js/welfare_rules.js')
def serve_welfare_rules_js():
    """Serve welfare rules JavaScript file"""
    return send_from_directory('static/js', 'welfare_rules.js')

@main.route('/static/css/welfare_rules.css')
def serve_welfare_rules_css():
    """Serve welfare rules CSS file"""
    return send_from_directory('static/css', 'welfare_rules.css')

# ==================== HEALTH CHECK ====================

@main.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'version': current_app.version,
        'timestamp': datetime.now().isoformat()
    })