# app/routes/report.py
from flask import Blueprint
from app.controllers.report_controller import ReportController

report = Blueprint('report', __name__, url_prefix='/reports')

# ==================== REPORT VIEWING ====================
report.route('/', endpoint='list')(ReportController.reports_list)
report.route('/preview', endpoint='preview')(ReportController.report_preview)
report.route('/<int:report_id>', endpoint='preview_specific')(ReportController.report_preview_specific)

# ==================== REPORT DOWNLOAD ====================
report.route('/download', endpoint='download')(ReportController.download_report)
report.route('/download/<int:report_id>', endpoint='download_specific')(ReportController.download_report)
report.route('/paid-members/download', endpoint='download_paid_members')(ReportController.download_paid_members)
report.route('/paid-members/download/<int:report_id>', endpoint='download_paid_members_specific')(ReportController.download_paid_members)
report.route('/welfare-rules/download', endpoint='download_welfare_rules')(ReportController.download_welfare_rules_pdf)

# ==================== PAID MEMBERS VIEW ====================
report.route('/paid-members')(ReportController.paid_members_view)
report.route('/<int:report_id>/paid-members')(ReportController.paid_members_for_report)

# ==================== REPORT MANAGEMENT ====================
report.route('/<int:report_id>/regenerate')(ReportController.regenerate_report)
report.route('/<int:report_id>/archive')(ReportController.archive_report)
report.route('/<int:report_id>/restore')(ReportController.restore_report)
report.route('/<int:report_id>/delete')(ReportController.delete_report)
report.route('/cleanup')(ReportController.cleanup_reports)

# ==================== REPORT STATISTICS ====================
report.route('/stats')(ReportController.get_report_statistics)
report.route('/export')(ReportController.export_reports_data)

# ==================== API ENDPOINTS ====================
report.route('/api/list')(ReportController.api_reports_list)
report.route('/api/<int:report_id>')(ReportController.api_report_details)
report.route('/api/search')(ReportController.api_search_reports)