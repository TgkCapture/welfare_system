# === app/main/routes.py ===
from flask import Blueprint, render_template, request, redirect, url_for, current_app, send_file
from flask_login import login_required
import os
from werkzeug.utils import secure_filename
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
        return redirect(url_for('main.dashboard'))
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('main.dashboard'))
    filename = secure_filename(file.filename)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    return redirect(url_for('main.report', filename=filename))

@main.route('/report/<filename>')
@login_required
def report(filename):
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    data = parse_excel(filepath)
    report_path = generate_report(data, filename)
    return send_file(report_path, as_attachment=True)