# app/controllers/report_controller.py
"""
Core report operations: generation, preview and download.
"""
import os
from datetime import datetime

from flask import (
    current_app, flash, redirect,
    render_template, send_file, session, url_for,
)
from flask_login import current_user, login_required

from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.ledger import SyncRun
from app.models.member import Member, normalise_name
from app.models.report import GeneratedReport, ReportAccessLog
from app.models.tenancy import current_group, current_group_id
from app.services import member_service
from app.services.image_generator import ImageGenerator
from app.services.period_store import PeriodStore

MONTH_NAMES = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December',
]


class ReportController:
    """Report generation, preview and download."""

    # ==================== PREVIEW ====================
    #
    # The routes without a report id act on the report the officer generated
    # last (remembered in the session by id only); the rest take an id.
    # Member detail comes from the stored contributions for that month.

    @staticmethod
    @permission_required('view_reports')
    def report_preview():
        """Steps 2 and 3 of the monthly cycle: check what the sync found, then share it."""
        report = ReportController.session_report()
        if report is None:
            flash('No report data available. Please generate a report first.', 'error')
            return redirect(url_for('main.dashboard'))

        group = current_group()
        run = (SyncRun.for_group().filter_by(id=session.get('last_run_id')).first()
               if session.get('last_run_id') else None)
        month = MONTH_NAMES[report.month - 1]
        period = f'{report.year}-{report.month}'
        paid_url = url_for('group.paid', slug=group.slug, period=period, _external=True)
        code = group.settings.access_code if group.settings.access_code_enabled else None

        return render_template(
            'main/report_preview.html',
            version=current_app.version,
            report=report,
            month=month,
            year=report.year,
            run=run,
            new_members=ReportController._new_members(run),
            paid_url=paid_url if group.settings.public_paid_enabled else None,
            share_text=ReportController._share_text(month, report.year, paid_url, code,
                                                    group.settings.public_paid_enabled),
        )

    @staticmethod
    def _new_members(run):
        """The sync's new names, each with members it may be a respelling of (manage_members only)."""
        if run is None or not current_user.has_permission('manage_members'):
            return []
        names = {normalise_name(n) for n in (run.details or {}).get('new_members', [])}
        members = Member.for_group().filter(Member.normalised_name.in_(names)).order_by(Member.display_name).all()
        return [(m, member_service.possible_duplicates(m)) for m in members]

    @staticmethod
    def _share_text(month, year, paid_url, code, paid_enabled):
        """A message officers can paste into the group chat."""
        lines = [f'{month} {year} contributions are now updated.']
        if paid_enabled:
            lines.append(f'See who has paid: {paid_url}')
            if code:
                lines.append(f'Group code: {code}')
        lines.append(f"Check your own: {url_for('group.check', slug=current_group().slug, _external=True)}")
        return '\n'.join(lines)

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
        """Download a report's PDF."""
        report = ReportController._report_or_none(report_id)
        if report is None:
            return ReportController._no_report_redirect(report_id)

        try:
            if not os.path.exists(report.file_path):
                flash('Report file not found on disk.', 'error')
                return redirect(url_for('main.dashboard'))

            ReportController._log_access(report.id, 'download')
            return send_file(
                report.file_path,
                as_attachment=True,
                download_name=report.filename,
                mimetype='application/pdf',
            )

        except Exception as e:
            current_app.logger.error(f"Error downloading report: {e}", exc_info=True)
            flash(f'Error downloading report: {str(e)}', 'error')
            return redirect(url_for('main.dashboard'))

    @staticmethod
    @permission_required('view_reports')
    def download_paid_members(report_id=None):
        """Download a report month's paid-members list as a PNG image."""
        report = ReportController._report_or_none(report_id)
        if report is None:
            return ReportController._no_report_redirect(report_id)

        data = PeriodStore.report_data(report.group_id, report.year, report.month)
        if data is None:
            return ReportController._not_stored_redirect(report)

        try:
            img_buffer = ImageGenerator.generate_paid_members_image(data)

            if img_buffer is None:
                flash('No paid members to display.', 'info')
                return redirect(url_for('report.preview_specific', report_id=report.id))

            return send_file(
                img_buffer,
                mimetype='image/png',
                as_attachment=True,
                download_name=f"paid_members_{data['month']}_{data['year']}.png",
            )

        except Exception as e:
            current_app.logger.error(f"Error generating paid-members image: {e}", exc_info=True)
            flash('Error generating paid members image.', 'error')
            return redirect(url_for('report.preview_specific', report_id=report.id))

    # ==================== PAID MEMBERS VIEW ====================

    @staticmethod
    @permission_required('view_reports')
    def paid_members_view():
        """Paid members for the report the officer just generated."""
        report = ReportController.session_report()
        if report is None:
            flash('No report data available. Please generate a report first.', 'info')
            return redirect(url_for('main.dashboard'))
        return ReportController._render_paid_members(report)

    @staticmethod
    @permission_required('view_reports')
    def paid_members_for_report(report_id):
        """Paid members for a specific report's month."""
        report = ReportController._report_or_none(report_id)
        if report is None:
            return ReportController._no_report_redirect(report_id)
        return ReportController._render_paid_members(report)

    @staticmethod
    def _render_paid_members(report):
        data = PeriodStore.report_data(report.group_id, report.year, report.month)
        if data is None:
            return ReportController._not_stored_redirect(report)

        paid_members = PeriodStore.paid_members(report.group_id, report.year, report.month)
        return render_template(
            'main/paid_members.html',
            version=current_app.version,
            report=report,
            paid_members=paid_members,
            month=MONTH_NAMES[report.month - 1],
            year=report.year,
            total_paid=len(paid_members),
            total_contributions=data['total_contributions'],   # money received, not credit
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
                group_id=current_group_id(),
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
            return report.id

        except Exception as e:
            current_app.logger.error(f"Error saving report to DB: {e}", exc_info=True)
            db.session.rollback()
            return None

    # ==================== SESSION REPORT ====================
    #
    # Only the id of the officer's latest report is kept in the session,
    # tagged with the officer and cleared on login and logout. The data
    # itself is stored in the DB, scoped to the group.

    SESSION_REPORT_KEYS = ('last_report_id', 'last_run_id', 'report_owner_id',
                           'report_data', 'report_path')   # last two: pre-2a cookies

    @staticmethod
    def remember_report(report_id: int, run_id: int = None) -> None:
        """Remember the report the current officer just generated, and the sync behind it."""
        session['last_report_id'] = report_id
        session['last_run_id'] = run_id
        session['report_owner_id'] = current_user.id
        session.pop('report_data', None)
        session.pop('report_path', None)

    @staticmethod
    def session_report():
        """The current officer's latest report, if they may still see it."""
        if session.get('report_owner_id') != current_user.id or 'last_report_id' not in session:
            return None
        report = GeneratedReport.for_group().filter_by(id=session['last_report_id']).first()
        if report is None or not ReportController.can_access_report(current_user, report):
            return None
        return report

    @staticmethod
    def clear_session_report() -> None:
        for key in ReportController.SESSION_REPORT_KEYS:
            session.pop(key, None)

    @staticmethod
    def _report_or_none(report_id):
        """The report with *report_id* (404 if not in the group), or the session's."""
        if report_id is None:
            return ReportController.session_report()
        report = GeneratedReport.get_for_group_or_404(report_id)
        return report if ReportController.can_access_report(current_user, report) else None

    @staticmethod
    def _no_report_redirect(report_id):
        if report_id is None:
            flash('No report available. Please generate a report first.', 'error')
            return redirect(url_for('main.dashboard'))
        flash('You do not have permission to access this report.', 'error')
        return redirect(url_for('report.list'))

    @staticmethod
    def _not_stored_redirect(report):
        flash(
            "Member detail for this month isn't stored yet: the report was generated "
            "before contributions were kept. Upload or sync the month again to see it.",
            'info',
        )
        return redirect(url_for('report.preview_specific', report_id=report.id))

    # ==================== SHARED UTILITIES ====================

    @staticmethod
    def can_access_report(user, report):
        """Return True if ``user`` is allowed to access ``report``.

        Officers see their own group's reports; archived ones need manage_reports.
        """
        if report.group_id != current_group_id() or not user.has_permission('view_reports'):
            return False
        return not report.is_archived or user.has_permission('manage_reports')

    @staticmethod
    def _log_access(report_id, action):
        """Write an access-log entry — failures are silently swallowed."""
        try:
            log = ReportAccessLog(
                group_id=current_group_id(),
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
