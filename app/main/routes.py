# app/main/routes.py
from flask import render_template, request, flash, redirect, url_for, send_file
from flask_login import login_required, current_user
from app import db
from app.main.forms import ReportForm, UploadForm
from app.reports.generators import generate_monthly_report, generate_yearly_report
import pandas as pd
import os
from datetime import datetime
from werkzeug.utils import secure_filename

@main.route('/', methods=['GET', 'POST'])
@login_required
def index():
    form = ReportForm()
    if form.validate_on_submit():
        month = form.month.data
        year = form.year.data
        report_type = form.report_type.data
        
        # Generate report based on selection
        if report_type == 'monthly':
            report_path = generate_monthly_report(year, month)
            filename = f"mzugoss_report_{month}_{year}.pdf"
        else:
            report_path = generate_yearly_report(year)
            filename = f"mzugoss_report_{year}.pdf"
            
        return send_file(report_path, as_attachment=True, download_name=filename)
    
    return render_template('index.html', form=form)

@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        file = form.file.data
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process the uploaded file
            try:
                process_uploaded_file(filepath, current_user.group_id)
                flash('File uploaded and processed successfully!', 'success')
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'danger')
            
            return redirect(url_for('main.index'))
    
    return render_template('upload.html', form=form)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls', 'csv'}

def process_uploaded_file(filepath, group_id):
    # Read and process the Excel file
    # This would be customized based on your specific Excel structure
    pass