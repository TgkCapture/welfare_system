# app/controllers/member_controller.py
"""
Members screen (manage_members): list, rename, merge, deactivate, the
personal history link and the lookup PIN. Plus the public personal history
page that the link opens (no account needed; the token is the key).

Members whose names come from the standard workbook (they have a Member ID)
are renamed and retired in the workbook too, or the next sync undoes it;
the screens say so.
"""
from flask import abort, current_app, flash, make_response, redirect, render_template, request, url_for

from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.group import Group
from app.models.ledger import SyncRun
from app.models.member import Member, MemberAlias, normalise_name
from app.models.tenancy import current_group
from app.services import member_service
from app.services.branding import use_group_brand
from app.services.member_service import MemberError
from app.services.standard_workbook import MONTHS


class MemberController:

    # ==================== LIST ====================

    @staticmethod
    @permission_required('manage_members')
    def members():
        """The group's members; ?q= searches names and IDs, ?run= shows a sync's new names."""
        query = Member.for_group()
        q = request.args.get('q', '').strip()
        run = None
        if q:
            like = f'%{normalise_name(q)}%'
            alias_ids = MemberAlias.for_group().filter(MemberAlias.normalised_name.like(like)) \
                .with_entities(MemberAlias.member_id)
            query = query.filter(db.or_(Member.normalised_name.like(like), Member.code.ilike(f'%{q}%'),
                                        Member.id.in_(alias_ids)))
        if request.args.get('run', type=int):
            run = SyncRun.get_for_group_or_404(request.args.get('run', type=int))
            names = {normalise_name(n) for n in run.details.get('new_members', [])}
            query = query.filter(Member.normalised_name.in_(names))

        members = query.order_by(Member.is_active.desc(), Member.display_name).all()
        return render_template('main/members.html', version=current_app.version,
                               members=members, q=q, run=run,
                               total=Member.for_group().count())

    # ==================== DETAIL ====================

    @staticmethod
    @permission_required('manage_members')
    def member(member_id):
        member = Member.get_for_group_or_404(member_id)
        return MemberController._render_member(member)

    @staticmethod
    def _render_member(member, new_pin=None):
        duplicates = member_service.possible_duplicates(member)
        others = [m for m in Member.for_group().filter(Member.id != member.id).order_by(Member.display_name)
                  if m not in duplicates]
        return render_template(
            'main/member_detail.html', version=current_app.version,
            member=member, history=member_service.history(member), months=MONTHS,
            duplicates=duplicates, others=others, new_pin=new_pin,
            history_url=url_for('group.member_history', slug=current_group().slug,
                                token=member.history_token, _external=True),
        )

    # ==================== CHANGES ====================

    @staticmethod
    @permission_required('manage_members')
    def rename(member_id):
        member = Member.get_for_group_or_404(member_id)
        old = member.display_name
        try:
            member_service.rename(member, request.form.get('name', ''))
        except MemberError as e:
            flash(str(e), 'danger')
        else:
            flash(f'{old} renamed to {member.display_name}. The old spelling is kept for matching.', 'success')
            MemberController._workbook_reminder(member, 'name')
        return redirect(url_for('main.member', member_id=member.id))

    @staticmethod
    @permission_required('manage_members')
    def toggle(member_id):
        member = Member.get_for_group_or_404(member_id)
        member.is_active = not member.is_active
        db.session.commit()
        flash(f"{member.display_name} {'restored' if member.is_active else 'retired'}. "
              f"{'' if member.is_active else 'Their personal link no longer opens.'}", 'success')
        MemberController._workbook_reminder(member, 'Left month')
        return redirect(url_for('main.member', member_id=member.id))

    @staticmethod
    @permission_required('manage_members')
    def merge(member_id):
        """Merge this member into another (two records of one person).

        From the monthly check page (htmx), the answer is a short note that
        replaces the name in place; otherwise it redirects with messages.
        """
        source = Member.get_for_group_or_404(member_id)
        target_id = request.form.get('into', type=int)
        target = Member.for_group().filter_by(id=target_id).first() if target_id else None
        inline = bool(request.headers.get('HX-Request'))
        if target is None:
            return MemberController._merge_answer(inline, source, error='Choose the member to merge into.')

        name = source.display_name
        try:
            notes = member_service.merge(source, target)
        except MemberError as e:
            return MemberController._merge_answer(inline, source, error=str(e))
        if inline:
            return render_template('main/_merge_result.html', name=name, target=target, notes=notes)
        flash(f'{name} merged into {target.display_name}. Their payments and names now belong to '
              f'{target.display_name}.', 'success')
        for note in notes:
            flash(note, 'warning')
        return redirect(url_for('main.member', member_id=target.id))

    @staticmethod
    def _merge_answer(inline, source, error):
        if inline:
            return render_template('main/_merge_result.html', error=error, name=source.display_name)
        flash(error, 'danger')
        return redirect(url_for('main.member', member_id=source.id))

    @staticmethod
    @permission_required('manage_members')
    def remove_alias(member_id, alias_id):
        member = Member.get_for_group_or_404(member_id)
        alias = MemberAlias.for_group().filter_by(id=alias_id, member_id=member.id).first()
        if alias is None:
            abort(404)
        member_service.remove_alias(alias)
        flash('Spelling removed. Sheet rows with it will no longer match this member.', 'success')
        return redirect(url_for('main.member', member_id=member.id))

    @staticmethod
    @permission_required('manage_members')
    def regenerate_link(member_id):
        member = Member.get_for_group_or_404(member_id)
        member_service.regenerate_link(member)
        flash('New personal link made. The old link no longer works: share the new one.', 'success')
        return redirect(url_for('main.member', member_id=member.id))

    @staticmethod
    @permission_required('manage_members')
    def set_pin(member_id):
        """Make a new PIN and show it once (it isn't stored or sent anywhere else)."""
        member = Member.get_for_group_or_404(member_id)
        pin = member_service.new_pin(member)
        response = make_response(MemberController._render_member(member, new_pin=pin))
        response.headers['Cache-Control'] = 'no-store'
        return response

    @staticmethod
    @permission_required('manage_members')
    def clear_pin(member_id):
        member = Member.get_for_group_or_404(member_id)
        member_service.clear_pin(member)
        flash('PIN removed. The member can still use their personal link.', 'success')
        return redirect(url_for('main.member', member_id=member.id))

    @staticmethod
    def _workbook_reminder(member, what):
        if member.code:
            flash(f'{member.display_name} has Member ID {member.code}: change their {what} on the '
                  "workbook's Members sheet too, or the next sync will change it back.", 'info')

    # ==================== PUBLIC HISTORY ====================

    @staticmethod
    def public_history(slug, token):
        """A member's own contribution history, opened by their personal link."""
        group = Group.query.filter_by(slug=slug, is_active=True).first()
        member = (Member.for_group(group.id).filter_by(history_token=token, is_active=True).first()
                  if group else None)
        if member is None:
            abort(404)
        use_group_brand(group)

        response = make_response(render_template(
            'public/member_history.html', group=group, member=member,
            history=member_service.history(member), months=MONTHS,
        ))
        # The link is the key: keep it out of search engines, caches and referrers
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
