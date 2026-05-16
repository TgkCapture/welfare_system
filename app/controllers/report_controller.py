# app/controllers/report_controller.py
"""
Core report operations: generation, preview and download.
"""
import os
from datetime import datetime

import pandas as pd
from flask import (
    current_app, flash, make_response, redirect,
    render_template, send_file, session, url_for,
)
from flask_login import current_user, login_required

from app.extensions import db
from app.models.report import GeneratedReport, ReportAccessLog
from app.services.image_generator import ImageGenerator
from app.services.pdf_service import PDFGenerator

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]


class ReportController:
    """Report generation, preview and download."""

    # ==================== PREVIEW ====================

    @staticmethod
    @login_required
    def report_preview():
        """Preview a freshly generated report stored in the session."""
        if 'report_data' not in session:
            flash('No report data available. Please generate a report first.', 'error')
            return redirect(url_for('main.dashboard'))

        data = session['report_data']

        return render_template(
            'main/report_preview.html',
            version=current_app.version,
            month=data.get('month'),
            year=data.get('year'),
            total_contributions=data.get('total_contributions'),
            contributors=data.get('num_contributors'),
            defaulters=data.get('num_missing'),
            money_dispensed=data.get('money_dispensed'),
            total_book_balance=data.get('total_book_balance'),
            filename=data.get('report_filename'),
            current_date=datetime.now(),
        )

    @staticmethod
    @login_required
    def report_preview_specific(report_id):
        """Preview a specific archived report from the database."""
        report = GeneratedReport.query.get_or_404(report_id)

        if not ReportController.can_access_report(current_user, report):
            flash('You do not have permission to access this report.', 'error')
            return redirect(url_for('report.list'))

        ReportController._log_access(report.id, 'preview')

        return render_template(
            'main/report_preview_specific.html',
            version=current_app.version,
            report=report,
            month_names=MONTH_NAMES,
            current_date=datetime.now(),
        )

    # ==================== DOWNLOAD ====================

    @staticmethod
    @login_required
    def download_report(report_id=None):
        """Download a PDF report.
        """
        try:
            if report_id:
                report = GeneratedReport.query.get_or_404(report_id)

                if not ReportController.can_access_report(current_user, report):
                    flash('You do not have permission to access this report.', 'error')
                    return redirect(url_for('report.list'))

                file_path = report.file_path
                download_name = report.filename
                ReportController._log_access(report.id, 'download')

            else:
                if 'report_path' not in session:
                    flash('No report available for download.', 'error')
                    return redirect(url_for('main.dashboard'))

                file_path = session['report_path']
                download_name = session.get('report_data', {}).get(
                    'report_filename',
                    f"report_{datetime.now().strftime('%Y%m%d')}.pdf",
                )

            if not os.path.exists(file_path):
                flash('Report file not found on disk.', 'error')
                return redirect(url_for('main.dashboard'))

            return send_file(
                file_path,
                as_attachment=True,
                download_name=download_name,
                mimetype='application/pdf',
            )

        except Exception as e:
            current_app.logger.error(f"Error downloading report: {e}", exc_info=True)
            flash(f'Error downloading report: {str(e)}', 'error')
            return redirect(url_for('main.dashboard'))

    @staticmethod
    @login_required
    def download_paid_members(report_id=None):
        """Download the paid-members list as a PNG image.
        """
        try:
            if report_id:
                report = GeneratedReport.query.get_or_404(report_id)

                if not ReportController.can_access_report(current_user, report):
                    flash('You do not have permission to access this report.', 'error')
                    return redirect(url_for('report.list'))

                # Raw data is not yet persisted — inform the user clearly
                flash(
                    'Paid-members image is only available for newly generated reports. '
                    'Re-upload the source file to regenerate it.',
                    'info',
                )
                return redirect(
                    url_for('main.report_preview_specific', report_id=report_id)
                )

            if 'report_data' not in session:
                flash('No report data available.', 'error')
                return redirect(url_for('main.report_preview'))

            data = session['report_data']
            image_data = {
                'data': pd.DataFrame(data['data']),
                'month_col': data['month_col'],
                'name_col': data['name_col'],
                'month': data['month'],
                'year': data['year'],
                'total_contributions': data['total_contributions'],
                'num_contributors': data['num_contributors'],
                'num_missing': data['num_missing'],
                'money_dispensed': data.get('money_dispensed'),
                'total_book_balance': data.get('total_book_balance'),
            }

            img_buffer = ImageGenerator.generate_paid_members_image(image_data)

            if img_buffer is None:
                flash('No paid members to display.', 'info')
                return redirect(url_for('main.report_preview'))

            return send_file(
                img_buffer,
                mimetype='image/png',
                as_attachment=True,
                download_name=(
                    f"paid_members_{image_data['month']}_{image_data['year']}.png"
                ),
            )

        except Exception as e:
            current_app.logger.error(f"Error generating paid-members image: {e}", exc_info=True)
            flash('Error generating paid members image.', 'error')
            return redirect(url_for('main.report_preview'))

    @staticmethod
    def download_welfare_rules_pdf():
        """Generate and download the welfare rules PDF."""
        try:
            pdf_content = PDFGenerator.generate_welfare_rules_pdf()
            response = make_response(pdf_content)
            response.headers['Content-Type'] = 'application/pdf'
            response.headers['Content-Disposition'] = (
                'attachment; filename=mzugoss_welfare_rules.pdf'
            )
            return response

        except Exception as e:
            current_app.logger.error(f"Welfare rules PDF failed: {e}", exc_info=True)
            flash('PDF generation unavailable. Use print-to-PDF instead.', 'warning')
            return redirect(url_for('main.welfare_rules'))

    # ==================== PAID MEMBERS VIEW ====================

    @staticmethod
    @login_required
    def paid_members_view():
        """Render the paid-members list for the current session report."""
        if 'report_data' not in session:
            flash('No report data available. Please generate a report first.', 'info')
            return redirect(url_for('main.dashboard'))

        data = session['report_data']
        paid_members = ReportController._extract_paid_members(data)

        return render_template(
            'main/paid_members.html',
            version=current_app.version,
            paid_members=paid_members,
            month=data['month'],
            year=data['year'],
            total_paid=len(paid_members),
            total_contributions=data['total_contributions'],
        )

    @staticmethod
    @login_required
    def paid_members_for_report(report_id):
        """View paid members for a specific archived report."""
        report = GeneratedReport.query.get_or_404(report_id)

        if not ReportController.can_access_report(current_user, report):
            flash('You do not have permission to access this report.', 'error')
            return redirect(url_for('report.list'))

        # Raw member data is not stored per-report yet
        flash(
            'Paid-members detail is only available for newly generated reports.',
            'info',
        )
        return redirect(
            url_for('main.report_preview_specific', report_id=report_id)
        )

    # ==================== REPORTS LIST ====================

    @staticmethod
    @login_required
    def reports_list():
        """Render the full report listing for the current user."""
        available_reports = ReportController._get_available_reports_for_user(current_user)

        return render_template(
            'main/reports_list.html',
            version=current_app.version,
            reports=available_reports,
            user_role=current_user.role,
            month_names=MONTH_NAMES,
        )

    # ==================== DB PERSISTENCE ====================

    @staticmethod
    @login_required
    def save_report_to_db(report_data, file_path):
        """Persist report metadata and return the new record's ID.
        """
        try:
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            report = GeneratedReport(
                month=report_data.get('month'),
                year=report_data.get('year'),
                report_type='contributions',
                filename=(
                    report_data.get('report_filename')
                    or os.path.basename(file_path)
                ),
                file_path=file_path,
                generated_by=current_user.id,
                file_size=file_size,
                total_contributions=report_data.get('total_contributions', 0),
                contributors_count=report_data.get('num_contributors', 0),
                defaulters_count=report_data.get('num_missing', 0),
                money_dispensed=report_data.get('money_dispensed'),
                total_book_balance=report_data.get('total_book_balance'),
            )

            db.session.add(report)
            db.session.commit()

            ReportController._log_access(report.id, 'generate')
            session['last_report_id'] = report.id

            return report.id

        except Exception as e:
            current_app.logger.error(f"Error saving report to DB: {e}", exc_info=True)
            db.session.rollback()
            return None

    # ==================== SHARED UTILITIES ====================

    @staticmethod
    def can_access_report(user, report):
        """Return True if ``user`` is allowed to access ``report``."""
        if user.is_admin:
            return True
        if user.is_clerk:
            return (
                report.generated_by == user.id
                or current_app.config.get('CLERKS_SEE_ALL_REPORTS', False)
            )
        # Viewers: non-archived reports only
        return not report.is_archived

    @staticmethod
    def _log_access(report_id, action):
        """Write an access-log entry — failures are silently swallowed."""
        try:
            log = ReportAccessLog(
                report_id=report_id,
                user_id=current_user.id,
                action=action,
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error logging report access: {e}")
            db.session.rollback()

    @staticmethod
    def _get_available_reports_for_user(user):
        """Return a list of report dicts the given user may see."""
        try:
            query = GeneratedReport.query

            if not user.is_admin:
                if user.is_clerk and not current_app.config.get('CLERKS_SEE_ALL_REPORTS', False):
                    query = query.filter(GeneratedReport.generated_by == user.id)
                else:
                    query = query.filter(GeneratedReport.is_archived == False)

            reports = query.order_by(GeneratedReport.generated_at.desc()).all()

            return [
                {
                    'id': r.id,
                    'month': r.month,
                    'year': r.year,
                    'total_contributions': r.total_contributions,
                    'contributors': r.contributors_count,
                    'defaulters': r.defaulters_count,
                    'generated_date': r.generated_at.strftime('%Y-%m-%d %H:%M'),
                    'generated_by': r.generator.email if r.generator else 'Unknown',
                    'file_size_mb': (
                        round(r.file_size / (1024 * 1024), 2) if r.file_size else 0
                    ),
                    'is_archived': r.is_archived,
                    'download_url': url_for('main.download_report', report_id=r.id),
                    'preview_url': url_for('main.report_preview_specific', report_id=r.id),
                    'paid_members_url': url_for('main.paid_members_for_report', report_id=r.id),
                }
                for r in reports
            ]

        except Exception as e:
            current_app.logger.error(f"Error fetching reports for user: {e}")
            return []

    @staticmethod
    def _extract_paid_members(report_data):
        """Parse session report data and return a list of paid member dicts."""
        paid = []
        try:
            df = pd.DataFrame(report_data['data'])
            month_col = report_data['month_col']
            name_col = report_data['name_col']

            for _, row in df.iterrows():
                try:
                    amount = float(row.get(month_col, 0) or 0)
                    if amount > 0:
                        paid.append({
                            'name': row.get(name_col, ''),
                            'amount': amount,
                            'status': 'Paid',
                        })
                except (ValueError, TypeError):
                    pass

        except Exception as e:
            current_app.logger.error(f"Error extracting paid members: {e}")

        return paid