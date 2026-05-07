# app/controllers/welfare_controller.py
"""
Welfare rules — public-facing, no authentication required.

"""
from flask import render_template, current_app

from app.controllers.report_controller import ReportController


class WelfareController:
    """Handles welfare rules page and associated downloads."""

    @staticmethod
    def welfare_rules():
        """Public endpoint — render the welfare rules page.

        No @login_required: members who are not yet registered
        should still be able to read the rules.
        """
        return render_template(
            'main/welfare_rules.html',
            version=current_app.version,
        )

    @staticmethod
    def download_welfare_rules_pdf():
        """Public endpoint — download welfare rules as a PDF.

        Delegates generation to ReportController so all PDF logic
        stays in one place.
        """
        return ReportController.download_welfare_rules_pdf()