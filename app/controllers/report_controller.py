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

from app.decorators.permissions import permission_required
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
    @permission_required('view_reports')
    def report_preview():
        """Preview a freshly generated report stored in the session."""
        data = ReportController.session_report()
        if data is None:
            flash('No report data available. Please generate a report first.', 'error')
            return redirect(url_for('main.dashboard'))

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
    @permission_required('view_reports')
    def report_preview_specific(report_id):
        """Preview a specific archived report from the database."""
        report = GeneratedReport.get_for_group_or_404(report_id)

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
    @permission_required('view_reports')
    def download_report(report_id=None):
        """Download a PDF report.
        """
        try:
            if report_id:
                report = GeneratedReport.get_for_group_or_404(report_id)

                if not ReportController.can_access_report(current_user, report):
                    flash('You do not have permission to access this report.', 'error')
                    return redirect(url_for('report.list'))

                file_path = report.file_path
                download_name = report.filename
                ReportController._log_access(report.id, 'download')

            else:
                data = ReportController.session_report()
                if data is None or 'report_path' not in session:
                    flash('No report available for download.', 'error')
                    return redirect(url_for('main.dashboard'))

                file_path = session['report_path']
                download_name = data.get(
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
    @permission_required('view_reports')
    def download_paid_members(report_id=None):
        """Download the paid-members list as a PNG image.
        """
        try:
            if report_id:
                report = GeneratedReport.get_for_group_or_404(report_id)

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
                    url_for('report.preview_specific', report_id=report_id)
                )

            data = ReportController.session_report()
            if data is None:
                flash('No report data available.', 'error')
                return redirect(url_for('main.dashboard'))

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
                return redirect(url_for('report.preview'))

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
            return redirect(url_for('report.preview'))

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
    @permission_required('view_reports')
    def paid_members_view():
        """Render the paid-members list for the current session report."""
        data = ReportController.session_report()
        if data is None:
            flash('No report data available. Please generate a report first.', 'info')
            return redirect(url_for('main.dashboard'))

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
    @permission_required('view_reports')
    def paid_members_for_report(report_id):
        """View paid members for a specific archived report."""
        report = GeneratedReport.get_for_group_or_404(report_id)

        if not ReportController.can_access_report(current_user, report):
            flash('You do not have permission to access this report.', 'error')
            return redirect(url_for('report.list'))

        # Raw member data is not stored per-report yet
        flash(
            'Paid-members detail is only available for newly generated reports.',
            'info',
        )
        return redirect(
            url_for('report.preview_specific', report_id=report_id)
        )

    # ==================== REPORTS LIST ====================

    @staticmethod
    @permission_required('view_reports')
    def reports_list():
        """Render the full report listing for the current user."""
        available_reports = ReportController._get_available_reports_for_user(current_user)

        return render_template(
            'main/reports_list.html',
            version=current_app.version,
            reports=available_reports,
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

            month_val = report_data.get('month')
            if isinstance(month_val, str):
                try:
                    month_val = MONTH_NAMES.index(month_val) + 1  # 'May' → 5
                except ValueError:
                    month_val = None  # fallback

            report = GeneratedReport(
                group_id=current_user.group_id,
                month=month_val,          # ← always an int now
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

    # ==================== SESSION REPORT ====================
    #
    # A freshly uploaded report is kept in the session for preview and
    # download. It is tagged with the officer who generated it and cleared
    # on login and logout, so it can never reach another officer.

    SESSION_REPORT_KEYS = ('report_data', 'report_path', 'report_owner_id', 'last_report_id')

    @staticmethod
    def store_session_report(serialized: dict) -> None:
        """Keep a freshly generated report for the current officer."""
        session.update(serialized)
        session['report_owner_id'] = current_user.id

    @staticmethod
    def session_report():
        """Return the session report's data if the current officer generated it."""
        if 'report_data' not in session or session.get('report_owner_id') != current_user.id:
            return None
        return session['report_data']

    @staticmethod
    def clear_session_report() -> None:
        for key in ReportController.SESSION_REPORT_KEYS:
            session.pop(key, None)

    # ==================== SHARED UTILITIES ====================

    @staticmethod
    def can_access_report(user, report):
        """Return True if ``user`` is allowed to access ``report``.

        Officers see their own group's reports; archived ones need manage_reports.
        """
        if report.group_id != user.group_id or not user.has_permission('view_reports'):
            return False
        return not report.is_archived or user.has_permission('manage_reports')

    @staticmethod
    def _log_access(report_id, action):
        """Write an access-log entry — failures are silently swallowed."""
        try:
            log = ReportAccessLog(
                group_id=current_user.group_id,
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
            query = GeneratedReport.for_group(user.group_id)

            if not user.has_permission('manage_reports'):
                query = query.filter(GeneratedReport.is_archived.is_(False))

            reports = query.order_by(GeneratedReport.generated_at.desc()).all()

            return [
                {
                    'id': r.id,
                    'month': int(r.month) if r.month is not None else None,  # Convert to int
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
                    'download_url': url_for('report.download_specific', report_id=r.id),
                    'preview_url': url_for('report.preview_specific', report_id=r.id),
                    'paid_members_url': url_for('report.paid_members_for_report', report_id=r.id),
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