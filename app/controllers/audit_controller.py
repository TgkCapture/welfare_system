# app/controllers/audit_controller.py
"""
The group's audit log (manage_users): every change officers made, sign-ins,
and anything platform support looked at. Read-only; ?area= narrows it.
"""
from flask import current_app, render_template, request

from app.decorators.permissions import permission_required
from app.services import audit


class AuditController:

    @staticmethod
    @permission_required('manage_users')
    def audit_log():
        area = request.args.get('area') if request.args.get('area') in audit.AREAS else None
        page = audit.events(area=area, page=request.args.get('page', 1, type=int))
        return render_template('main/audit_log.html', version=current_app.version, page=page,
                               icons=audit.ICONS, areas=audit.AREAS, area=area)
