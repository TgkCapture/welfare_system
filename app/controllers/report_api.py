# app/controllers/report_api.py
"""
Report API endpoints, statistics and data export.

All routes here return JSON (or a file download for export).
They are intended for AJAX calls from the dashboard and for any
future external API consumers.
"""
from datetime import datetime
from io import BytesIO

import pandas as pd
from flask import current_app, flash, jsonify, redirect, request, send_file, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models.report import GeneratedReport, ReportAccessLog
from app.controllers.report_controller import ReportController


class ReportAPI:
    """JSON API and export endpoints for reports."""

    # ==================== LIST & SEARCH ====================

    @staticmethod
    @login_required
    def api_reports_list():
        """GET /api/reports — paginated list for the current user."""
        reports = ReportController._get_available_reports_for_user(current_user)
        return jsonify({'reports': reports, 'count': len(reports)})

    @staticmethod
    @login_required
    def api_search_reports():
        """GET /api/reports/search?month=&year= — filtered report list."""
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)

        query = GeneratedReport.query

        if month:
            query = query.filter_by(month=month)
        if year:
            query = query.filter_by(year=year)

        # Enforce the same visibility rules as the list view
        if not current_user.is_admin:
            if (
                current_user.is_clerk
                and not current_app.config.get('CLERKS_SEE_ALL_REPORTS', False)
            ):
                query = query.filter(GeneratedReport.generated_by == current_user.id)
            else:
                query = query.filter(GeneratedReport.is_archived == False)

        reports = query.order_by(GeneratedReport.generated_at.desc()).limit(50).all()

        return jsonify({
            'reports': [
                {
                    'id': r.id,
                    'month': r.month,
                    'year': r.year,
                    'total_contributions': r.total_contributions,
                    'contributors': r.contributors_count,
                    'defaulters': r.defaulters_count,
                    'generated_at': (
                        r.generated_at.isoformat() if r.generated_at else None
                    ),
                    'is_archived': r.is_archived,
                }
                for r in reports
            ]
        })

    # ==================== SINGLE REPORT DETAIL ====================

    @staticmethod
    @login_required
    def api_report_details(report_id):
        """GET /api/reports/<id> — full detail for one report."""
        report = GeneratedReport.query.get_or_404(report_id)

        if not ReportController.can_access_report(current_user, report):
            return jsonify({'error': 'Access denied.'}), 403

        return jsonify(report.to_dict())

    # ==================== STATISTICS ====================

    @staticmethod
    @login_required
    def api_report_statistics():
        """GET /api/reports/stats — aggregate statistics (admin only)."""
        if not current_user.is_admin:
            return jsonify({'error': 'Admin access required.'}), 403

        try:
            stats = ReportAPI._build_statistics()
            return jsonify(stats)
        except Exception as e:
            current_app.logger.error(f"Error building report statistics: {e}")
            return jsonify({'error': 'Could not load statistics.'}), 500

    @staticmethod
    def _build_statistics():
        """Compile aggregate report statistics from the database."""
        total_reports = GeneratedReport.query.count()
        active_reports = GeneratedReport.query.filter_by(is_archived=False).count()
        archived_reports = GeneratedReport.query.filter_by(is_archived=True).count()

        total_contributions = (
            db.session.query(func.sum(GeneratedReport.total_contributions)).scalar() or 0
        )
        avg_contributors = (
            db.session.query(func.avg(GeneratedReport.contributors_count)).scalar() or 0
        )

        reports_by_year = db.session.query(
            GeneratedReport.year,
            func.count(GeneratedReport.id),
        ).group_by(GeneratedReport.year).all()

        recent_accesses = (
            ReportAccessLog.query
            .order_by(ReportAccessLog.accessed_at.desc())
            .limit(10)
            .all()
        )

        return {
            'total_reports': total_reports,
            'active_reports': active_reports,
            'archived_reports': archived_reports,
            'total_contributions': float(total_contributions),
            'avg_contributors': round(float(avg_contributors), 1),
            'reports_by_year': dict(reports_by_year),
            'recent_accesses': [
                {
                    'report_id': a.report_id,
                    'user_id': a.user_id,
                    'action': a.action,
                    'accessed_at': a.accessed_at.isoformat() if a.accessed_at else None,
                }
                for a in recent_accesses
            ],
        }

    # ==================== EXPORT ====================

    @staticmethod
    @login_required
    def export_reports_data():
        """GET /api/reports/export — download all reports as an Excel file.

        Admin only — exposes financial totals across all groups.
        """
        if not current_user.is_admin:
            flash('Only admins can export report data.', 'error')
            return redirect(url_for('report.list'))

        try:
            reports = GeneratedReport.query.all()

            rows = [
                {
                    'id': r.id,
                    'month': r.month,
                    'year': r.year,
                    'report_type': r.report_type,
                    'generated_by': r.generator.email if r.generator else '',
                    'generated_at': r.generated_at,
                    'total_contributions': r.total_contributions,
                    'contributors_count': r.contributors_count,
                    'defaulters_count': r.defaulters_count,
                    'money_dispensed': r.money_dispensed,
                    'total_book_balance': r.total_book_balance,
                    'is_archived': r.is_archived,
                    'archived_at': r.archived_at,
                    'file_size_mb': (
                        round(r.file_size / (1024 * 1024), 2) if r.file_size else 0
                    ),
                }
                for r in reports
            ]

            df = pd.DataFrame(rows)
            output = BytesIO()

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Reports', index=False)

            output.seek(0)

            return send_file(
                output,
                mimetype=(
                    'application/vnd.openxmlformats-officedocument'
                    '.spreadsheetml.sheet'
                ),
                as_attachment=True,
                download_name=(
                    f'reports_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
                ),
            )

        except Exception as e:
            current_app.logger.error(f"Error exporting report data: {e}", exc_info=True)
            flash('Error exporting report data.', 'error')
            return redirect(url_for('report.list'))