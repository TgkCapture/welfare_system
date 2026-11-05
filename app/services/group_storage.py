# app/services/group_storage.py
"""
Per-group file storage.

Each group's files live in folders named after its slug, which never
changes once the group exists:

  <UPLOAD_FOLDER>/<slug>/   uploaded workbooks (deleted once processed)
  <REPORT_FOLDER>/<slug>/   generated reports

Files directly inside UPLOAD_FOLDER / REPORT_FOLDER predate per-group
storage; ``flask move-files-to-groups`` moves the reports among them.
"""
import os

from flask import current_app

from app.models.group import Group
from app.models.tenancy import current_group

_CONFIG_KEYS = {'uploads': 'UPLOAD_FOLDER', 'reports': 'REPORT_FOLDER'}


def root_folder(kind: str) -> str:
    """The platform-wide folder for *kind* ('uploads' or 'reports')."""
    return current_app.config[_CONFIG_KEYS[kind]]


def group_folder(kind: str, group=None) -> str:
    """Return (and create) *group*'s folder for *kind*; default: the current group."""
    group = group or current_group()
    if group is None:
        raise ValueError('No group: files can only be stored for a group.')
    # Slugs are validated on creation; re-check so a bad one can't escape the root
    if not Group.is_valid_slug(group.slug):
        raise ValueError(f'Invalid group slug {group.slug!r}.')

    path = os.path.join(root_folder(kind), group.slug)
    os.makedirs(path, exist_ok=True)
    return path


def report_retention_days(group) -> int:
    """How long *group*'s report files are kept: its own setting or the platform default."""
    days = group.settings.report_retention_days if group.settings else None
    return days or current_app.config.get('REPORT_RETENTION_DAYS', 7)


def upload_retention_days() -> int:
    """Uploads are deleted after processing; this catches any left behind."""
    return current_app.config.get('UPLOAD_RETENTION_DAYS', 3)
