# app/controllers/public_controller.py
"""
A group's public pages for its members (no accounts), under /g/<slug>/:

  /              the group's home: links to the rules, paid list and lookup
  /paid          who has paid, behind the group access code
  /check         a member's own history, by name and PIN

The rules and the personal history link live in their own controllers.
Every page shows the group's branding, asks search engines not to index it,
and says when the data was last updated. Access code and PIN attempts share
one rate limit per IP (PUBLIC_LOOKUP_RATE_LIMIT).
"""
import calendar

from flask import abort, current_app, make_response, render_template, request, send_file

from app.extensions import limiter
from app.models.group import Group
from app.services import logo, member_service, public_access
from app.services.branding import use_group_brand
from app.services.standard_workbook import MONTHS


def _lookup_rate_limit():
    return current_app.config.get('PUBLIC_LOOKUP_RATE_LIMIT', '10 per minute;30 per hour')


_limit_attempts = limiter.shared_limit(_lookup_rate_limit, scope='public-lookup', methods=['POST'])


class PublicController:

    @staticmethod
    def landing(slug):
        group = PublicController._group(slug)
        return PublicController._page('public/landing.html', group,
                                      last_updated=public_access.last_updated(group))

    @staticmethod
    @_limit_attempts
    def paid(slug):
        group = PublicController._group(slug)
        if not group.settings.public_paid_enabled:
            abort(404)

        if public_access.needs_code(group):
            wrong = False
            if request.method == 'POST':
                wrong = not public_access.try_code(group, request.form.get('code', ''))
            if public_access.needs_code(group):
                return PublicController._page('public/access_code.html', group, wrong=wrong)

        months = public_access.browsable_months(group)
        period = PublicController._requested_period()
        if period not in months:
            period = months[0] if months else None
        return PublicController._page(
            'public/paid.html', group, months=months, period=period,
            month_name=calendar.month_name[period[1]] if period else None,
            paid=public_access.paid_list(group, *period) if period else None,
            settings=group.settings,
        )

    @staticmethod
    @_limit_attempts
    def check(slug):
        group = PublicController._group(slug)
        failed = False
        if request.method == 'POST':
            member = public_access.lookup(group, request.form.get('name', ''), request.form.get('pin', ''))
            if member is not None:
                return PublicController._page('public/member_history.html', group, member=member,
                                              history=member_service.history(member), months=MONTHS)
            failed = True
        return PublicController._page('public/check.html', group, failed=failed)

    @staticmethod
    def logo(slug):
        """The group's logo. Its URL carries the file name, so it can be cached for long."""
        group = Group.query.filter_by(slug=slug, is_active=True).first()
        path = logo.path_for(group) if group else None
        if path is None:
            abort(404)
        return send_file(path, mimetype='image/png', max_age=7 * 24 * 3600)

    # ==================== HELPERS ====================

    @staticmethod
    def _requested_period():
        """(year, month) from ?period=2026-3, or None."""
        year, _, month = request.args.get('period', '').partition('-')
        return (int(year), int(month)) if year.isdigit() and month.isdigit() else None

    @staticmethod
    def _group(slug):
        group = Group.query.filter_by(slug=slug, is_active=True).first()
        if group is None:
            abort(404)
        use_group_brand(group)
        return group

    @staticmethod
    def _page(template, group, **context):
        response = make_response(render_template(template, group=group, **context))
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        # Pages after a code or PIN hold private data: never cache them
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
