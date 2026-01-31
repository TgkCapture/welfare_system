# app/controllers/report_controller.py
from flask import render_template, send_file, flash, redirect, url_for, session, make_response, current_app, jsonify, request
from flask_login import current_user, login_required
import os
import pandas as pd
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import shutil
from sqlalchemy import or_, and_
import tempfile
from io import BytesIO

from app.models.report import GeneratedReport, ReportAccessLog
from app.models.user import User
from app.services.image_generator import ImageGenerator
from app.services.pdf_service import PDFGenerator
from app.services.file_cleanup import FileCleanupService

class ReportController:
    """Handles report-related business logic with database storage"""
    
    # REPORT GENERATION & PREVIEW
    
    @staticmethod
    @login_required
    def report_preview():
        """Preview generated report from session"""
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
    def save_report_to_db(report_data, file_path):
        """Save report metadata to database"""
        try:
            # Extract data from report_data
            month = report_data.get('month')
            year = report_data.get('year')
            filename = report_data.get('report_filename', 
                f"contributions_report_{month}_{year}.pdf")
            
            # Get file size
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
            
            # Create report record
            report = GeneratedReport(
                month=month,
                year=year,
                report_type='contributions',
                filename=filename,
                file_path=file_path,
                generated_by=current_user.id,
                file_size=file_size,
                total_contributions=report_data.get('total_contributions', 0),
                contributors_count=report_data.get('num_contributors', 0),
                defaulters_count=report_data.get('num_missing', 0),
                money_dispensed=report_data.get('money_dispensed'),
                total_book_balance=report_data.get('total_book_balance')
            )
            
            from app import db
            db.session.add(report)
            db.session.commit()
            
            # Log the access
            ReportController.log_report_access(report.id, 'generate')
            
            # Store report ID in session for easy access
            session['last_report_id'] = report.id
            
            return report.id
            
        except Exception as e:
            current_app.logger.error(f"Error saving report to database: {str(e)}")
            from app import db
            db.session.rollback()
            return None
   
   # DOWNLOAD FUNCTIONS

    @staticmethod
    @login_required
    def download_report(report_id=None):
        """Download generated PDF report"""
        try:
            if report_id:
                # Download specific report from database
                report = GeneratedReport.query.get_or_404(report_id)
                
                # Check permissions
                if not ReportController.can_access_report(current_user, report):
                    flash('You do not have permission to access this report', 'error')
                    return redirect(url_for('report.list'))
                
                file_path = report.file_path
                download_filename = report.filename
                
                # Log the access
                ReportController.log_report_access(report.id, 'download')
                
            else:
                # Download from session (newly generated report)
                if 'report_path' not in session:
                    flash('No report available for download', 'error')
                    return redirect(url_for('main.dashboard'))
                
                file_path = session['report_path']
                download_filename = session.get('report_data', {}).get(
                    'report_filename',
                    f"contributions_report_{datetime.now().strftime('%Y%m%d')}.pdf"
                )
            
            if not os.path.exists(file_path):
                flash('Report file not found', 'error')
                return redirect(url_for('main.dashboard'))
            
            return send_file(
                file_path,
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
    def download_paid_members(report_id=None):
        """Download paid members as PNG image"""
        try:
            if report_id:
                # Download for specific report
                report = GeneratedReport.query.get_or_404(report_id)
                
                # Check permissions
                if not ReportController.can_access_report(current_user, report):
                    flash('You do not have permission to access this report', 'error')
                    return redirect(url_for('report.list'))
                
                #TODO: Get data from stored report (you might need to store the raw data)
                
                flash('Paid members image not available for archived reports', 'info')
                return redirect(url_for('main.report_preview_specific', report_id=report_id))
            
            # Download from session (newly generated report)
            if 'report_data' not in session:
                flash('No report data available', 'error')
                return redirect(url_for('main.report_preview'))
            
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
    
    # REPORT VIEWING & MANAGEMENT

    @staticmethod
    @login_required
    def reports_list():
        """View all available reports for current user"""
        # Get available reports based on user role
        available_reports = ReportController._get_available_reports_for_user(current_user)
        
        return render_template('main/reports_list.html',
                             version=current_app.version,
                             reports=available_reports,
                             user_role=current_user.role,
                             month_names=current_app.config.get('MONTH_NAMES', [
                                 'January', 'February', 'March', 'April', 'May', 'June',
                                 'July', 'August', 'September', 'October', 'November', 'December'
                             ]))
    
    @staticmethod
    @login_required
    def report_preview_specific(report_id):
        """Preview a specific report from database"""
        report = GeneratedReport.query.get_or_404(report_id)
        
        # Check permissions
        if not ReportController.can_access_report(current_user, report):
            flash('You do not have permission to access this report', 'error')
            return redirect(url_for('report.list'))
        
        # Log the access
        ReportController.log_report_access(report.id, 'preview')
        
        return render_template(
            'main/report_preview_specific.html',
            version=current_app.version,
            report=report,
            month_names=current_app.config.get('MONTH_NAMES', [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]),
            current_date=datetime.now()
        )
    
    @staticmethod
    @login_required
    def paid_members_view():
        """View paid members list for current report"""
        if 'report_data' not in session:
            flash('No report data available. Please generate a report first.', 'info')
            return redirect(url_for('main.dashboard'))
        
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
                             total_paid=len(paid_members),
                             total_contributions=report_data['total_contributions'])
    
    @staticmethod
    @login_required
    def paid_members_for_report(report_id):
        """View paid members for a specific report"""
        report = GeneratedReport.query.get_or_404(report_id)
        
        # Check permissions
        if not ReportController.can_access_report(current_user, report):
            flash('You do not have permission to access this report', 'error')
            return redirect(url_for('report.list'))
        
        # TODO: retrieve the actual data
        flash('Paid members data not stored for archived reports', 'info')
        return redirect(url_for('main.report_preview_specific', report_id=report_id))
    
    @staticmethod
    def _get_paid_members_data():
        """Get paid members data for dashboard statistics"""
        try:
             
            return 42  #TODO: aggregate data from reports 
        except Exception as e:
            current_app.logger.error(f"Error getting paid members data: {str(e)}")
            return 0
    
    # REPORT MANAGEMENT (ADMIN/CLERK)

    @staticmethod
    @login_required
    def regenerate_report(report_id):
        """Regenerate a report from stored data"""
        if not current_user.is_admin and not current_user.is_clerk:
            flash('Only admins and clerks can regenerate reports', 'error')
            return redirect(url_for('report.list'))
        
        report = GeneratedReport.query.get_or_404(report_id)
        
        try:
            # TODO: regenerate from source data
            original_path = report.file_path
            if not os.path.exists(original_path):
                flash('Original report file not found', 'error')
                return redirect(url_for('main.report_preview_specific', report_id=report_id))
            
            # Create new filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            new_filename = f"regenerated_{timestamp}_{report.filename}"
            new_filepath = os.path.join(
                current_app.config['REPORT_FOLDER'],
                new_filename
            )
            
            # Copy the file
            shutil.copy2(original_path, new_filepath)
            
            # Create new report record
            new_report = GeneratedReport(
                month=report.month,
                year=report.year,
                report_type=report.report_type,
                filename=new_filename,
                file_path=new_filepath,
                generated_by=current_user.id,
                file_size=os.path.getsize(new_filepath),
                total_contributions=report.total_contributions,
                contributors_count=report.contributors_count,
                defaulters_count=report.defaulters_count,
                money_dispensed=report.money_dispensed,
                total_book_balance=report.total_book_balance
            )
            
            from app import db
            db.session.add(new_report)
            db.session.commit()
            
            # Log the access
            ReportController.log_report_access(new_report.id, 'regenerate')
            
            flash(f'Report for {report.month}/{report.year} has been regenerated', 'success')
            return redirect(url_for('main.report_preview_specific', report_id=new_report.id))
            
        except Exception as e:
            current_app.logger.error(f"Error regenerating report: {str(e)}")
            flash(f'Error regenerating report: {str(e)}', 'error')
            return redirect(url_for('report.list'))
    
    @staticmethod
    @login_required
    def archive_report(report_id):
        """Archive a report (admins only)"""
        if not current_user.is_admin:
            flash('Only admins can archive reports', 'error')
            return redirect(url_for('report.list'))
        
        report = GeneratedReport.query.get_or_404(report_id)
        
        try:
            report.is_archived = True
            report.archived_at = datetime.utcnow()
            
            from app import db
            db.session.commit()
            
            flash(f'Report for {report.month}/{report.year} has been archived', 'success')
            return redirect(url_for('report.list'))
            
        except Exception as e:
            current_app.logger.error(f"Error archiving report: {str(e)}")
            flash(f'Error archiving report: {str(e)}', 'error')
            return redirect(url_for('report.list'))
    
    @staticmethod
    @login_required
    def restore_report(report_id):
        """Restore an archived report (admins only)"""
        if not current_user.is_admin:
            flash('Only admins can restore reports', 'error')
            return redirect(url_for('report.list'))
        
        report = GeneratedReport.query.get_or_404(report_id)
        
        try:
            report.is_archived = False
            report.archived_at = None
            
            from app import db
            db.session.commit()
            
            flash(f'Report for {report.month}/{report.year} has been restored', 'success')
            return redirect(url_for('report.list'))
            
        except Exception as e:
            current_app.logger.error(f"Error restoring report: {str(e)}")
            flash(f'Error restoring report: {str(e)}', 'error')
            return redirect(url_for('report.list'))
    
    @staticmethod
    @login_required
    def delete_report(report_id):
        """Delete a report (admins only)"""
        if not current_user.is_admin:
            flash('Only admins can delete reports', 'error')
            return redirect(url_for('report.list'))
        
        report = GeneratedReport.query.get_or_404(report_id)
        
        try:
            # Delete the file
            if os.path.exists(report.file_path):
                os.remove(report.file_path)
            
            # Delete access logs
            ReportAccessLog.query.filter_by(report_id=report_id).delete()
            
            # Delete the report record
            from app import db
            db.session.delete(report)
            db.session.commit()
            
            flash(f'Report for {report.month}/{report.year} has been deleted', 'success')
            return redirect(url_for('report.list'))
            
        except Exception as e:
            current_app.logger.error(f"Error deleting report: {str(e)}")
            flash(f'Error deleting report: {str(e)}', 'error')
            return redirect(url_for('report.list'))
    
    @staticmethod
    @login_required
    def cleanup_reports():
        """Clean up old reports (admins only)"""
        if not current_user.is_admin:
            flash('Only admins can cleanup reports', 'error')
            return redirect(url_for('main.dashboard'))
        
        try:
            # Get cleanup days from config
            days_to_keep = current_app.config.get('REPORT_RETENTION_DAYS', 7)
            
            # Run cleanup
            result = FileCleanupService.cleanup_old_files(days_to_keep=days_to_keep)
            
            # Also mark old reports as archived in database
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            from app import db
            old_reports = GeneratedReport.query.filter(
                GeneratedReport.generated_at < cutoff_date,
                GeneratedReport.is_archived == False
            ).all()
            
            for report in old_reports:
                report.is_archived = True
                report.archived_at = datetime.utcnow()
            
            db.session.commit()
            
            flash(
                f'Cleanup completed: {result.get("deleted_count", 0)} files removed, '
                f'{len(old_reports)} reports archived',
                'success'
            )
            return redirect(url_for('report.list'))
            
        except Exception as e:
            current_app.logger.error(f"Error in report cleanup: {str(e)}")
            flash(f'Error in cleanup: {str(e)}', 'error')
            return redirect(url_for('report.list'))
    
    # UTILITY FUNCTIONS

    @staticmethod
    def can_access_report(user, report):
        """Check if user can access a report"""
        if user.is_admin:
            return True
        elif user.is_clerk:
            # Clerks can access reports they generated or all if configured
            return report.generated_by == user.id or current_app.config.get('CLERKS_SEE_ALL_REPORTS', False)
        else:  # Viewer
            # Viewers can access all non-archived reports
            return not report.is_archived
    
    @staticmethod
    def log_report_access(report_id, action):
        """Log report access for auditing"""
        try:
            log = ReportAccessLog(
                report_id=report_id,
                user_id=current_user.id,
                action=action
            )
            
            from app import db
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error logging report access: {str(e)}")
            db.session.rollback()
    
    @staticmethod
    def _get_available_reports_for_user(user):
        """Get list of available reports for a specific user"""
        try:
            query = GeneratedReport.query
            
            if not user.is_admin:
                # For non-admins, filter by permissions
                if user.is_clerk and not current_app.config.get('CLERKS_SEE_ALL_REPORTS', False):
                    # Clerks only see their own reports
                    query = query.filter(GeneratedReport.generated_by == user.id)
                else:
                    # Viewers see non-archived reports
                    query = query.filter(GeneratedReport.is_archived == False)
            
            # Order by most recent first
            reports = query.order_by(GeneratedReport.generated_at.desc()).all()
            
            return [{
                'id': report.id,
                'month': report.month,
                'year': report.year,
                'total_contributions': report.total_contributions,
                'contributors': report.contributors_count,
                'defaulters': report.defaulters_count,
                'generated_date': report.generated_at.strftime('%Y-%m-%d %H:%M'),
                'generated_by': report.generator.email if report.generator else 'Unknown',
                'file_size_mb': round(report.file_size / (1024 * 1024), 2) if report.file_size else 0,
                'is_archived': report.is_archived,
                'download_url': url_for('main.download_report', report_id=report.id),
                'preview_url': url_for('main.report_preview_specific', report_id=report.id),
                'paid_members_url': url_for('main.paid_members_for_report', report_id=report.id)
            } for report in reports]
            
        except Exception as e:
            current_app.logger.error(f"Error getting reports for user: {str(e)}")
            return []
    
    @staticmethod
    def get_report_statistics():
        """Get comprehensive report statistics"""
        from app import db
        from sqlalchemy import func
        
        try:
            total_reports = GeneratedReport.query.count()
            active_reports = GeneratedReport.query.filter_by(is_archived=False).count()
            archived_reports = GeneratedReport.query.filter_by(is_archived=True).count()
            
            # Total contributions across all reports
            total_contributions = db.session.query(
                func.sum(GeneratedReport.total_contributions)
            ).scalar() or 0
            
            # Average contributors per report
            avg_contributors = db.session.query(
                func.avg(GeneratedReport.contributors_count)
            ).scalar() or 0
            
            # Reports by year
            reports_by_year = db.session.query(
                GeneratedReport.year,
                func.count(GeneratedReport.id)
            ).group_by(GeneratedReport.year).all()
            
            # Recent activity
            recent_accesses = ReportAccessLog.query.order_by(
                ReportAccessLog.accessed_at.desc()
            ).limit(10).all()
            
            return {
                'total_reports': total_reports,
                'active_reports': active_reports,
                'archived_reports': archived_reports,
                'total_contributions': total_contributions,
                'avg_contributors': round(avg_contributors, 1),
                'reports_by_year': dict(reports_by_year),
                'recent_accesses': recent_accesses
            }
            
        except Exception as e:
            current_app.logger.error(f"Error getting report statistics: {str(e)}")
            return {}
    
    @staticmethod
    def export_reports_data():
        """Export reports data for analysis"""
        try:
            reports = GeneratedReport.query.all()
            
            # Create DataFrame
            data = []
            for report in reports:
                data.append({
                    'id': report.id,
                    'month': report.month,
                    'year': report.year,
                    'report_type': report.report_type,
                    'generated_by': report.generator.email if report.generator else '',
                    'generated_at': report.generated_at,
                    'total_contributions': report.total_contributions,
                    'contributors_count': report.contributors_count,
                    'defaulters_count': report.defaulters_count,
                    'money_dispensed': report.money_dispensed,
                    'total_book_balance': report.total_book_balance,
                    'is_archived': report.is_archived,
                    'archived_at': report.archived_at,
                    'file_size_mb': round(report.file_size / (1024 * 1024), 2) if report.file_size else 0
                })
            
            df = pd.DataFrame(data)
            
            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Reports', index=False)
            
            output.seek(0)
            
            # Return as file download
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'reports_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
            )
            
        except Exception as e:
            current_app.logger.error(f"Error exporting reports data: {str(e)}")
            flash('Error exporting reports data', 'error')
            return redirect(url_for('report.list'))
    
    @staticmethod
    def api_reports_list():
        """API endpoint for reports list"""
        from flask import jsonify
        reports = ReportController._get_available_reports_for_user(current_user)
        return jsonify({'reports': reports})
    
    @staticmethod
    def api_report_details(report_id):
        """API endpoint for report details"""
        from flask import jsonify
        report = GeneratedReport.query.get_or_404(report_id)
        
        if not ReportController.can_access_report(current_user, report):
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify(report.to_dict())
    
    @staticmethod
    def api_search_reports():
        """API endpoint for searching reports"""
        from flask import request, jsonify
        from sqlalchemy import and_
        
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        
        query = GeneratedReport.query
        
        if month:
            query = query.filter_by(month=month)
        if year:
            query = query.filter_by(year=year)
        
        # Apply user permissions
        if not current_user.is_admin:
            if current_user.is_clerk and not current_app.config.get('CLERKS_SEE_ALL_REPORTS', False):
                query = query.filter(GeneratedReport.generated_by == current_user.id)
            else:
                query = query.filter(GeneratedReport.is_archived == False)
        
        reports = query.order_by(GeneratedReport.generated_at.desc()).limit(50).all()
        
        return jsonify({
            'reports': [{
                'id': r.id,
                'month': r.month,
                'year': r.year,
                'total_contributions': r.total_contributions,
                'contributors': r.contributors_count,
                'defaulters': r.defaulters_count,
                'generated_at': r.generated_at.isoformat() if r.generated_at else None,
                'is_archived': r.is_archived
            } for r in reports]
        })