# app/services/setup.py
"""
The setup checklist that walks a new group from creation to its first
shared month.

Most steps are worked out from the group's data (purposes exist, a month is
synced, …), so they tick themselves. The two that can't be (reviewing the
branding and the public page) are ticked when an officer saves or opens
those pages (``mark``). Each step names the permission needed to do it.
"""
from dataclasses import dataclass

from app.extensions import db
from app.models.ledger import PayoutPurpose, SyncRun
from app.models.member import PeriodSummary
from app.models.rules import RuleSection
from app.models.user import User


@dataclass
class Step:
    key: str
    title: str
    text: str
    icon: str
    endpoint: str
    permission: str
    done: bool


def steps(group) -> list:
    marks = set(group.settings.setup_marks or []) if group.settings else set()
    synced = PeriodSummary.for_group(group.id).first() is not None
    # A synced month means a workbook exists, however it arrived
    has_source = synced or bool(group.settings and group.settings.google_sheet_url) or \
        SyncRun.for_group(group.id).first() is not None
    return [
        Step('branding', 'Check your group\'s name and colour',
             'How your group appears on pages, reports and the members\' page.',
             'palette', 'main.settings', 'edit_settings', 'branding' in marks),
        Step('purposes', 'Add your payout purposes',
             'The reasons your group pays money out, such as a funeral condolence. They fill the '
             'workbook\'s dropdown.', 'hand-holding-heart', 'main.payout_purposes', 'edit_settings',
             PayoutPurpose.for_group(group.id).filter_by(is_active=True).first() is not None),
        Step('workbook', 'Set up your workbook',
             'Download the standard template (or set up the layout of your own sheet), and add your '
             'Google Sheet link if you use one.', 'file-excel', 'main.workbook', 'upload_data', has_source),
        Step('sync', 'Upload or sync your first month',
             'Members, contributions and balances are read from the workbook. Then check any new names.',
             'file-arrow-up', 'main.upload_dashboard', 'upload_data', synced),
        Step('rules', 'Write your welfare rules',
             'What members pay and what support they can receive, shown to members and as a PDF.',
             'book-open', 'main.rules_editor', 'edit_rules',
             RuleSection.for_group(group.id).first() is not None),
        Step('public', 'Review the members\' page',
             'Choose what it shows and note the group code to share.', 'globe', 'main.public_pages',
             'edit_settings', 'public' in marks),
        Step('officers', 'Add your other officers',
             'Give the treasurer and secretary their own accounts and roles.', 'users-gear',
             'main.admin_users', 'manage_users',
             User.for_group(group.id).filter_by(is_active=True).count() >= 2),
    ]


def progress(group) -> dict:
    items = steps(group)
    done = sum(s.done for s in items)
    return {
        'steps': items,
        'done': done,
        'total': len(items),
        'complete': done == len(items),
        'next': next((s for s in items if not s.done), None),
    }


def mark(group, key: str) -> None:
    """Tick a step that can't be worked out from the data.

    Not during a platform support session: looking at a screen for the
    group is not the group's officers having seen it.
    """
    from app.services import support

    if support.is_active():
        return
    settings = group.settings
    if settings is not None and key not in (settings.setup_marks or []):
        settings.setup_marks = list(settings.setup_marks or []) + [key]
        db.session.commit()


def show_on_dashboard(group) -> bool:
    return bool(group.settings) and not group.settings.setup_dismissed and not progress(group)['complete']
