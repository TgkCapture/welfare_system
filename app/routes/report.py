# app/routes/report.py
"""
Report blueprint.

Controllers are now split across three classes — imports reflect that.

  ReportController    — generation, preview, download
  ReportManagement    — archive / restore / delete / cleanup / regenerate
  ReportAPI           — JSON endpoints, statistics, export
"""
from flask import Blueprint

from app.controllers.report_controller import ReportController
from app.controllers.report_management import ReportManagement
from app.controllers.report_api import ReportAPI

report = Blueprint('report', __name__, url_prefix='/reports')

# ==================== LIST & PREVIEW ====================
report.route('/',                      endpoint='list')(ReportController.reports_list)
report.route('/preview',               endpoint='preview')(ReportController.report_preview)
report.route('/<int:report_id>',       endpoint='preview_specific')(ReportController.report_preview_specific)

# ==================== DOWNLOADS ====================
report.route('/download',              endpoint='download')(ReportController.download_report)
report.route('/download/<int:report_id>', endpoint='download_specific')(ReportController.download_report)

report.route('/paid-members/download', endpoint='download_paid_members')(ReportController.download_paid_members)
report.route('/paid-members/download/<int:report_id>', endpoint='download_paid_members_specific')(ReportController.download_paid_members)

report.route('/welfare-rules/download', endpoint='download_welfare_rules')(ReportController.download_welfare_rules_pdf)

# ==================== PAID MEMBERS VIEW ====================
report.route('/paid-members',                   endpoint='paid_members')(ReportController.paid_members_view)
report.route('/<int:report_id>/paid-members',   endpoint='paid_members_for_report')(ReportController.paid_members_for_report)

# ==================== REPORT MANAGEMENT ====================
# Methods that mutate report state — ReportManagement
report.route('/<int:report_id>/regenerate', methods=['POST'], endpoint='regenerate')(ReportManagement.regenerate_report)
report.route('/<int:report_id>/archive',    methods=['POST'], endpoint='archive')(ReportManagement.archive_report)
report.route('/<int:report_id>/restore',    methods=['POST'], endpoint='restore')(ReportManagement.restore_report)
report.route('/<int:report_id>/delete',     methods=['POST'], endpoint='delete')(ReportManagement.delete_report)
report.route('/cleanup',                    methods=['POST'], endpoint='cleanup')(ReportManagement.cleanup_reports)

# ==================== STATISTICS & EXPORT ====================
report.route('/stats',   endpoint='stats')(ReportAPI.api_report_statistics)
report.route('/export',  endpoint='export')(ReportAPI.export_reports_data)

# ==================== JSON API ====================
report.route('/api/list',              endpoint='api_list')(ReportAPI.api_reports_list)
report.route('/api/search',            endpoint='api_search')(ReportAPI.api_search_reports)
report.route('/api/<int:report_id>',   endpoint='api_detail')(ReportAPI.api_report_details)