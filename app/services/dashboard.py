# app/services/dashboard.py
"""
What the dashboard shows an officer: the latest month, the trend, the
year's balance, what needs attention and recent reports.

Each part is only worked out if the officer may see it, so the dashboard
is one page for every role.
"""
import calendar
from dataclasses import dataclass, field
from datetime import date

from app.models.ledger import PayoutPurpose, SyncRun, YearSummary
from app.models.member import Member, PeriodSummary
from app.models.report import GeneratedReport

TREND_MONTHS = 6


@dataclass
class Attention:
    """Something an officer should look at, with where to do it."""
    icon: str
    text: str
    endpoint: str
    args: dict = field(default_factory=dict)
    tone: str = 'warning'


def overview(group, user) -> dict:
    can = user.has_permission
    summaries = (PeriodSummary.for_group(group.id)
                 .order_by(PeriodSummary.year.desc(), PeriodSummary.month.desc())
                 .limit(TREND_MONTHS).all())
    latest = summaries[0] if summaries else None
    last_run = SyncRun.for_group(group.id).order_by(SyncRun.synced_at.desc()).first()

    return {
        'latest': latest,
        'latest_label': f'{calendar.month_name[latest.month]} {latest.year}' if latest else None,
        'trend': [_trend_row(s) for s in reversed(summaries)],
        # Not a year that hasn't started: the workbook may already have next year's empty sheet
        'year': (YearSummary.for_group(group.id).filter(YearSummary.year <= date.today().year)
                 .order_by(YearSummary.year.desc()).first()
                 if can('view_reports') or can('upload_data') else None),
        'members': Member.for_group(group.id).filter_by(is_active=True).count(),
        'last_run': last_run if user.can_sync else None,
        'attention': _attention(group, user, last_run),
        'reports': (GeneratedReport.for_group(group.id).filter(GeneratedReport.is_archived.is_(False))
                    .order_by(GeneratedReport.generated_at.desc()).limit(5).all()
                    if can('view_reports') else []),
    }


def _trend_row(summary):
    counted = summary.contributors_count + summary.defaulters_count
    return {
        'label': f'{calendar.month_abbr[summary.month]} {summary.year % 100:02d}',
        'paid': summary.contributors_count,
        'unpaid': summary.defaulters_count,
        'total': summary.total_contributions,
        'percent': round(100 * summary.contributors_count / counted) if counted else 0,
    }


def _attention(group, user, last_run) -> list:
    can = user.has_permission
    items = []
    if user.can_sync and last_run and last_run.warnings:
        items.append(Attention('triangle-exclamation', f'The last sync raised {len(last_run.warnings)} warning(s).',
                               'main.sync_run', {'run_id': last_run.id}))
    new_names = (last_run.details or {}).get('new_members', []) if last_run else []
    if can('manage_members') and new_names:
        items.append(Attention('user-plus', f'{len(new_names)} new name(s) from the last sync: check for '
                               'different spellings of existing members.', 'main.members', {'run': last_run.id},
                               tone='primary'))
    if can('manage_members'):
        no_pin = Member.for_group(group.id).filter_by(is_active=True, pin_hash=None).count()
        if no_pin:
            items.append(Attention('key', f'{no_pin} member(s) have no PIN, so they can only use their personal '
                                   'link to see their contributions.', 'main.members', tone='neutral'))
    if can('edit_settings'):
        if not PayoutPurpose.for_group(group.id).filter_by(is_active=True).count():
            items.append(Attention('hand-holding-heart', 'No payout purposes yet: add the reasons your group '
                                   'pays money out.', 'main.payout_purposes'))
        if group.settings and group.settings.access_code_enabled is False and group.settings.public_paid_enabled:
            items.append(Attention('lock-open', 'The group code is off: anyone with the link can see who has paid.',
                                   'main.public_pages', tone='neutral'))
    return items
