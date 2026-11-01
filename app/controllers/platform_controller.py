# app/controllers/platform_controller.py
"""
Platform administration for superadmins.

Step 1b provides a read-only overview of groups; creating and managing
groups from the browser arrives in step 1d (use the CLI until then).
"""
from flask import render_template
from sqlalchemy import func

from app.decorators.permissions import superadmin_required
from app.extensions import db
from app.models.group import Group
from app.models.report import GeneratedReport
from app.models.user import User


class PlatformController:

    @staticmethod
    @superadmin_required
    def dashboard():
        """List every group with its officer and report counts."""
        officers = (
            db.session.query(User.group_id, func.count(User.id))
            .filter(User.group_id.isnot(None), User.is_active.is_(True))
            .group_by(User.group_id)
        )
        reports = (
            db.session.query(GeneratedReport.group_id, func.count(GeneratedReport.id))
            .group_by(GeneratedReport.group_id)
        )
        officer_counts, report_counts = dict(officers.all()), dict(reports.all())

        groups = [
            {
                'group':    g,
                'officers': officer_counts.get(g.id, 0),
                'reports':  report_counts.get(g.id, 0),
            }
            for g in Group.query.order_by(Group.name).all()
        ]
        return render_template('platform/dashboard.html', groups=groups)
