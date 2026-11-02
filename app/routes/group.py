# app/routes/group.py
"""
Per-group pages, under /g/<slug>/.

The group's officer login, and its public pages for members: home, rules,
paid list (behind the group access code), name + PIN lookup and personal
history links.
"""
from flask import Blueprint

from app.controllers.auth_controller import AuthController
from app.controllers.member_controller import MemberController
from app.controllers.public_controller import PublicController
from app.controllers.welfare_controller import WelfareController

group = Blueprint('group', __name__, url_prefix='/g/<slug>')

# ==================== AUTH ====================
group.route('/login', methods=['GET', 'POST'], endpoint='login')(AuthController.group_login)

# ==================== PUBLIC ====================
group.route('/', endpoint='landing')(PublicController.landing)
group.route('/paid', methods=['GET', 'POST'], endpoint='paid')(PublicController.paid)
group.route('/check', methods=['GET', 'POST'], endpoint='check')(PublicController.check)
group.route('/m/<token>', endpoint='member_history')(MemberController.public_history)
group.route('/rules', endpoint='rules')(WelfareController.public_rules)
group.route('/rules.pdf', endpoint='rules_pdf')(WelfareController.public_rules_pdf)
