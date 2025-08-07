# === app/main/routes.py ===
from flask import Blueprint, render_template, request, redirect, url_for, current_app, send_file, flash, session, jsonify
from flask_login import login_required
import os
import pandas as pd
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

        year = request.form.get('year', type=int)
        month = request.form.get('month', type=int)
        
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
        
        # Generate and store report path
        report_path = generate_report(data, filename)
        session['report_path'] = report_path
        
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