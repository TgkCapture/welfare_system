# === app/main/routes.py ===
from flask import Blueprint, render_template, request, redirect, url_for, current_app, send_file, flash, session
from flask_login import login_required
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from .utils import parse_excel, generate_report, generate_paid_members_image

main = Blueprint('main', __name__)

@main.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html', version=current_app.version, datetime=datetime)

@main.route('/version')
def version():
    return f"Current version: {current_app.version}"

@main.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('main.dashboard'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Get year and month from form
        year = request.form.get('year', type=int)
        month = request.form.get('month', type=int)
        
        data = parse_excel(filepath, year=year, month=month)
        report_path = generate_report(data, filename)
        
        # Store report info in session
        session['report_path'] = report_path
        session['report_data'] = {
            'month': data['month'],
            'year': data['year'],
            'total': data['total_contributions'],
            'contributors': data['num_contributors'],
            'defaulters': data['num_missing'],
            'report_filename': f"contributions_report_{data['year']}_{data['month']}.pdf"
        }
        
        return redirect(url_for('main.report_preview'))
        
    except Exception as e:
        current_app.logger.error(f"Upload error: {str(e)}")
        flash(f'Error generating report: {str(e)}', 'error')
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

@main.route('/download-paid-members')
@login_required
def download_paid_members():
    if 'report_data' not in session:
        flash('No report data available', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        img_buffer = generate_paid_members_image(session['report_data'])
        if img_buffer is None:
            flash('No paid members to display', 'info')
            return redirect(url_for('main.report_preview'))
            
        return send_file(img_buffer,
                        mimetype='image/png',
                        as_attachment=True,
                        download_name=f"paid_members_{session['report_data']['month']}_{session['report_data']['year']}.png")
    except Exception as e:
        current_app.logger.error(f"Error generating image: {str(e)}")
        flash('Error generating paid members image', 'error')
        return redirect(url_for('main.report_preview'))        