# app/controllers/welfare_controller.py
"""
Welfare rules: each group's own, written by its officers (edit_rules).

  /g/<slug>/rules, /g/<slug>/rules.pdf   public, for the group's members
  /welfare-rules, /welfare-rules/download
      an officer's own group; for visitors (old shared links) the group they
      last used, or the only group, or else the group finder
  /settings/rules/...                    the editor
"""
from flask import (
    abort, current_app, flash, make_response, redirect, render_template, request, url_for,
)
from flask_login import current_user

from app.controllers.auth_controller import LAST_GROUP_COOKIE
from app.decorators.permissions import permission_required
from app.extensions import db
from app.models.group import Group
from app.models.rules import RuleSection
from app.models.tenancy import current_group
from app.services import audit
from app.services.branding import brand_for, use_group_brand
from app.services.pdf_service import PDFGenerator
from app.services.rules_markup import parse

TITLE_MAX, SUBTITLE_MAX = 120, 200


class WelfareController:

    # ==================== VIEW ====================

    @staticmethod
    def welfare_rules():
        """The signed-in officer's group rules; visitors are sent to a group's public page."""
        group = current_group()
        if group is not None:
            return render_template('main/welfare_rules.html', version=current_app.version,
                                   sections=WelfareController._sections(group))
        target = WelfareController._visitor_group()
        return redirect(url_for('group.rules', slug=target.slug) if target else url_for('auth.login'))

    @staticmethod
    def download_welfare_rules_pdf():
        group = current_group()
        if group is not None:
            return WelfareController._pdf(group)
        target = WelfareController._visitor_group()
        return redirect(url_for('group.rules_pdf', slug=target.slug) if target else url_for('auth.login'))

    @staticmethod
    def public_rules(slug):
        group = WelfareController._active_group(slug)
        use_group_brand(group)
        response = make_response(render_template(
            'public/rules.html', group=group, sections=WelfareController._sections(group)))
        response.headers['X-Robots-Tag'] = 'noindex'
        return response

    @staticmethod
    def public_rules_pdf(slug):
        return WelfareController._pdf(WelfareController._active_group(slug))

    # ==================== EDITOR ====================

    @staticmethod
    @permission_required('edit_rules')
    def editor():
        """The group's sections in order; POST adds one at the end."""
        if request.method == 'POST':
            fields = WelfareController._submitted()
            if fields:
                last = RuleSection.for_group().with_entities(db.func.max(RuleSection.position)).scalar()
                section = RuleSection(group_id=current_group().id, position=(last or 0) + 1, **fields)
                db.session.add(section)
                db.session.commit()
                audit.record('rules.add', f'Added the rules section {section.title}',
                             details={'section_id': section.id})
                flash(f'Section {section.title} added.', 'success')
                return redirect(url_for('main.edit_rule_section', section_id=section.id))
            return redirect(url_for('main.rules_editor'))

        return render_template('main/rules_editor.html', version=current_app.version,
                               sections=RuleSection.ordered().all())

    @staticmethod
    @permission_required('edit_rules')
    def edit_section(section_id):
        section = RuleSection.get_for_group_or_404(section_id)
        if request.method == 'POST':
            fields = WelfareController._submitted()
            if fields:
                before = {'title': section.title, 'subtitle': section.subtitle, 'body': section.body}
                for key, value in fields.items():
                    setattr(section, key, value)
                db.session.commit()
                # The previous wording is kept so an unwanted edit can be put back
                audit.record('rules.edit', f'Edited the rules section {section.title}',
                             details={'section_id': section.id, 'before': before})
                flash(f'Section {section.title} saved.', 'success')
                return redirect(url_for('main.edit_rule_section', section_id=section.id))
        return render_template('main/rule_section_form.html', version=current_app.version,
                               section=section, blocks=parse(section.body))

    @staticmethod
    @permission_required('edit_rules')
    def delete_section(section_id):
        section = RuleSection.get_for_group_or_404(section_id)
        title = section.title
        before = {'title': section.title, 'subtitle': section.subtitle, 'body': section.body}
        db.session.delete(section)
        db.session.commit()
        audit.record('rules.delete', f'Deleted the rules section {title}', details={'before': before})
        flash(f'Section {title} deleted.', 'success')
        return redirect(url_for('main.rules_editor'))

    @staticmethod
    @permission_required('edit_rules')
    def move_section(section_id):
        """Move a section one place up or down."""
        section = RuleSection.get_for_group_or_404(section_id)
        sections = RuleSection.ordered().all()
        index = sections.index(section)
        other = index - 1 if request.form.get('direction') == 'up' else index + 1
        if 0 <= other < len(sections):
            sections[index], sections[other] = sections[other], sections[index]
            for position, s in enumerate(sections):
                s.position = position
            db.session.commit()
            direction = 'up' if request.form.get('direction') == 'up' else 'down'
            audit.record('rules.move', f'Moved the rules section {section.title} {direction}')
        return redirect(url_for('main.rules_editor'))

    # ==================== HELPERS ====================

    @staticmethod
    def _sections(group):
        """Sections with their bodies parsed for display."""
        return [(s, parse(s.body)) for s in RuleSection.ordered(group.id)]

    @staticmethod
    def _pdf(group):
        try:
            pdf = PDFGenerator.generate_welfare_rules_pdf(brand_for(group), RuleSection.ordered(group.id).all())
        except Exception as e:
            current_app.logger.error(f'Welfare rules PDF failed: {e}', exc_info=True)
            flash('PDF generation unavailable. Use print-to-PDF instead.', 'warning')
            return redirect(url_for('group.rules', slug=group.slug))
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={group.slug}_welfare_rules.pdf'
        return response

    @staticmethod
    def _active_group(slug):
        group = Group.query.filter_by(slug=slug, is_active=True).first()
        if group is None:
            abort(404)
        return group

    @staticmethod
    def _visitor_group():
        """The group a visitor most likely means: the last one they used, or the only one."""
        slug = request.cookies.get(LAST_GROUP_COOKIE)
        if slug:
            group = Group.query.filter_by(slug=slug, is_active=True).first()
            if group:
                return group
        groups = Group.query.filter_by(is_active=True).limit(2).all()
        return groups[0] if len(groups) == 1 else None

    @staticmethod
    def _submitted():
        """The submitted section fields, or None (with messages) if they can't be used."""
        title = ' '.join(request.form.get('title', '').split())
        subtitle = ' '.join(request.form.get('subtitle', '').split()) or None
        body = request.form.get('body', '').replace('\r\n', '\n').strip()
        problems = []
        if not title or len(title) > TITLE_MAX:
            problems.append(f'A section needs a title of up to {TITLE_MAX} characters.')
        if subtitle and len(subtitle) > SUBTITLE_MAX:
            problems.append(f'The subtitle can be up to {SUBTITLE_MAX} characters.')
        if len(body) > 20000:
            problems.append('The section text is too long; split it into several sections.')
        for problem in problems:
            flash(problem, 'danger')
        return None if problems else {'title': title, 'subtitle': subtitle, 'body': body}
