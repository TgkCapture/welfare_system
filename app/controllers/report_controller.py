# app/controllers/report_controller.py
from flask import render_template, send_file, flash, redirect, url_for, session, make_response, current_app
from flask_login import current_user, login_required
import os
import pandas as pd
from datetime import datetime

from app.services.image_generator import ImageGenerator
from app.services.pdf_service import PDFGenerator

class ReportController:
    """Handles report-related business logic"""
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
    @login_required
    def download_paid_members():
        """Download paid members as PNG image"""
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
    
    @staticmethod
    @login_required
    def reports_list():
        """View all available reports"""
        # Get all reports from database or storage
        available_reports = ReportController._get_available_reports()
        
        return render_template('main/reports_list.html',
                             version=current_app.version,
                             reports=available_reports,
                             user_role=current_user.role)
    
    @staticmethod
    def _get_available_reports():
        """Get list of available reports"""
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
    
    @staticmethod
    def _get_paid_members_data():
        """Get paid members data"""
        return {
            'total_paid': 0,
            'members': [],
            'last_updated': None
        }
    
    @staticmethod
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
    
    @staticmethod
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