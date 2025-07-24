# === app/main/routes.py ===
from flask import Blueprint, render_template, request, redirect, url_for, current_app, send_file, flash, session
from flask_login import login_required
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from .utils import parse_excel, generate_report

main = Blueprint('main', __name__)

@main.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@main.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No file part in request', 'error')
        return redirect(url_for('main.dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # Ensure upload directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)
        
        try:
            data = parse_excel(filepath)
            report_path = generate_report(data, filename)
        except ValueError as e:
            flash(f'Error parsing Excel file: {str(e)}', 'error')
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            flash(f'Error generating report: {str(e)}', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Store report info in session
        session['report_path'] = report_path
        session['report_data'] = {
            'month': data.get('month', 'Unknown'),
            'year': data.get('year', 'Unknown'),
            'total': float(data.get('total_contributions', 0)),
            'contributors': int(data.get('num_contributors', 0)),
            'defaulters': int(data.get('num_missing', 0)),
            'report_filename': f"contributions_report_{data.get('month', 'unknown')}_{data.get('year', 'unknown')}.pdf"
        }
        
        return redirect(url_for('main.report_preview'))
        
    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        flash('An error occurred while processing your file', 'error')
        return redirect(url_for('main.dashboard'))

@main.route('/report-preview')
@login_required
def report_preview():
    if 'report_data' not in session:
        flash('No report data available', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template(
        'report_preview.html',
        month=session['report_data']['month'],
        year=session['report_data']['year'],
        total=session['report_data']['total'],
        contributors=session['report_data']['contributors'],
        defaulters=session['report_data']['defaulters'],
        filename=session['report_data']['report_filename']
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