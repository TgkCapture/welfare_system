"""
Per-group files and settings: each group's uploads and reports live in
their own folders, cleanup touches one group at a time, and the sheet URL
and retention period come from the group's own settings.
"""
import os
import time
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner

from app.extensions import db
from app.models.group import Group
from app.models.report import GeneratedReport
from app.services.file_cleanup import FileCleanupService
from app.services.group_storage import group_folder


def _upload(client, workbook):
    with open(workbook, 'rb') as fh:
        return client.post(
            '/upload',
            data={'file': (fh, 'mzugoss.xlsx'), 'year': '2026', 'month': '3'},
            content_type='multipart/form-data',
        )


def _age(path, days):
    """Backdate a file's modification time by *days*."""
    old = time.time() - days * 86400
    os.utime(path, (old, old))


def _report_file(group, name, days_old=0, report_age_days=None, user=None):
    """A report file in *group*'s folder, optionally with its DB record."""
    path = os.path.join(group_folder('reports', group), name)
    with open(path, 'wb') as fh:
        fh.write(b'%PDF-1.4 test')
    _age(path, days_old)
    if report_age_days is not None:
        db.session.add(GeneratedReport(
            group_id=group.id, month=1, year=2026, filename=name, file_path=path,
            generated_by=user.id if user else None,
            generated_at=datetime.utcnow() - timedelta(days=report_age_days),
        ))
        db.session.commit()
    return path


# ==================== STORAGE LOCATION ====================

def test_report_is_saved_in_the_groups_folder_and_upload_removed(app, client, group, make_user,
                                                                 login, mzugoss_workbook):
    make_user()
    login()

    assert _upload(client, mzugoss_workbook).status_code == 302

    report = GeneratedReport.query.one()
    reports_dir = os.path.join(app.config['REPORT_FOLDER'], 'mzugoss')
    assert os.path.dirname(report.file_path) == reports_dir
    assert os.path.isfile(report.file_path)
    # The uploaded workbook (member data) is not kept
    assert os.listdir(os.path.join(app.config['UPLOAD_FOLDER'], 'mzugoss')) == []


def test_uploaded_copy_is_removed_even_when_parsing_fails(app, client, make_user, login, tmp_path):
    make_user()
    login()
    bad = tmp_path / 'broken.xlsx'
    bad.write_bytes(b'not a workbook')

    _upload(client, bad)

    assert os.listdir(os.path.join(app.config['UPLOAD_FOLDER'], 'mzugoss')) == []


def test_group_folder_rejects_an_unsafe_slug(app, group):
    group.slug = '../escape'
    with pytest.raises(ValueError):
        group_folder('reports', group)


# ==================== CLEANUP ====================

def test_group_cleanup_leaves_other_groups_alone(app, group, make_group, make_user):
    other = make_group(name='Another Welfare', slug='another')
    mine = _report_file(group, 'old.pdf', days_old=30)
    theirs = _report_file(other, 'old.pdf', days_old=30)

    result = FileCleanupService.cleanup_group(group)

    assert result['deleted_count'] == 1
    assert not os.path.exists(mine)
    assert os.path.exists(theirs)


def test_cleanup_uses_each_groups_retention(app, group, make_group, make_user):
    other = make_group(name='Another Welfare', slug='another')
    group.settings.report_retention_days = 60
    db.session.commit()
    kept = _report_file(group, 'r.pdf', days_old=30)       # within 60 days
    expired = _report_file(other, 'r.pdf', days_old=30)    # platform default is shorter

    FileCleanupService.cleanup_all()

    assert os.path.exists(kept)
    assert not os.path.exists(expired)


def test_cleanup_archives_expired_reports_but_keeps_their_records(app, group, make_user):
    user = make_user()
    _report_file(group, 'old.pdf', days_old=30, report_age_days=30, user=user)
    _report_file(group, 'new.pdf', report_age_days=0, user=user)

    result = FileCleanupService.cleanup_group(group)

    assert result['reports_archived'] == 1
    archived = {r.filename: r.is_archived for r in GeneratedReport.query}
    assert archived == {'old.pdf': True, 'new.pdf': False}


def test_dry_run_changes_nothing(app, group, make_user):
    user = make_user()
    path = _report_file(group, 'old.pdf', days_old=30, report_age_days=30, user=user)

    result = FileCleanupService.cleanup_group(group, dry_run=True)

    assert (result['deleted_count'], result['reports_archived']) == (1, 1)
    assert os.path.exists(path)
    assert not GeneratedReport.query.one().is_archived


def test_officer_cleanup_page_cleans_only_their_group(client, group, make_group, make_user, login):
    other = make_group(name='Another Welfare', slug='another')
    make_user(email='t@example.com', role='Treasurer')
    mine = _report_file(group, 'old.pdf', days_old=30)
    theirs = _report_file(other, 'old.pdf', days_old=30)
    login('t@example.com')

    assert client.post('/admin/cleanup').status_code == 200
    assert client.post('/reports/cleanup').status_code == 302

    assert not os.path.exists(mine)
    assert os.path.exists(theirs)
    assert b'another' not in client.get('/admin/storage-status').data


def test_superadmin_storage_page_cleans_every_group(client, group, make_group, make_superadmin, login):
    other = make_group(name='Another Welfare', slug='another')
    paths = [_report_file(group, 'old.pdf', days_old=30), _report_file(other, 'old.pdf', days_old=30)]
    make_superadmin()
    login('root@example.com', slug=None)

    page = client.get('/platform/storage')
    assert b'Another Welfare' in page.data

    client.post('/platform/storage', data={'dry_run': '1'})
    assert all(os.path.exists(p) for p in paths)

    client.post('/platform/storage')
    assert not any(os.path.exists(p) for p in paths)


# ==================== SETTINGS ====================

def test_settings_are_per_group(client, group, make_group, make_user, login):
    other = make_group(name='Another Welfare', slug='another')
    make_user(email='chair@example.com')
    login('chair@example.com')

    client.post('/settings', data={
        'sheet_url': 'https://docs.google.com/spreadsheets/d/mine', 'report_retention_days': '30',
    })

    mine, theirs = db.session.get(Group, group.id).settings, db.session.get(Group, other.id).settings
    assert (mine.google_sheet_url, mine.report_retention_days) == (
        'https://docs.google.com/spreadsheets/d/mine', 30)
    assert (theirs.google_sheet_url, theirs.report_retention_days) == (None, None)
    assert b'spreadsheets/d/mine' in client.get('/upload-dashboard').data


@pytest.mark.parametrize('retention', ['0', '-5', 'abc', '99999'])
def test_invalid_retention_is_rejected(client, group, make_user, login, retention):
    make_user(email='chair@example.com')
    login('chair@example.com')

    client.post('/settings', data={'sheet_url': '', 'report_retention_days': retention})

    assert db.session.get(Group, group.id).settings.report_retention_days is None


def test_blank_values_clear_the_settings(client, group, make_user, login):
    group.settings.google_sheet_url = 'https://docs.google.com/spreadsheets/d/x'
    group.settings.report_retention_days = 14
    db.session.commit()
    make_user(email='chair@example.com')
    login('chair@example.com')

    client.post('/settings', data={'sheet_url': '', 'report_retention_days': ''})

    settings = db.session.get(Group, group.id).settings
    assert (settings.google_sheet_url, settings.report_retention_days) == (None, None)


# ==================== CLI ====================

def test_move_files_to_groups(app, group, make_user):
    user = make_user()
    legacy = os.path.join(app.config['REPORT_FOLDER'], 'legacy.pdf')
    with open(legacy, 'wb') as fh:
        fh.write(b'%PDF-1.4 legacy')
    db.session.add(GeneratedReport(group_id=group.id, month=1, year=2025, filename='legacy.pdf',
                                   file_path=legacy, generated_by=user.id))
    db.session.commit()
    runner = app.test_cli_runner()

    runner.invoke(args=['move-files-to-groups', '--dry-run'])
    assert os.path.exists(legacy)

    result = runner.invoke(args=['move-files-to-groups'])
    assert 'Moved 1 file' in result.output
    report = GeneratedReport.query.one()
    assert report.file_path == os.path.join(app.config['REPORT_FOLDER'], 'mzugoss', 'legacy.pdf')
    assert os.path.isfile(report.file_path) and not os.path.exists(legacy)

    # Re-running is harmless
    assert '1 already in place' in runner.invoke(args=['move-files-to-groups']).output


def test_cleanup_files_cli_for_one_group(app, group, make_group):
    other = make_group(name='Another Welfare', slug='another')
    mine = _report_file(group, 'old.pdf', days_old=30)
    theirs = _report_file(other, 'old.pdf', days_old=30)

    result = app.test_cli_runner().invoke(args=['cleanup-files', '--group', 'mzugoss'])

    assert 'Deleted 1 file' in result.output
    assert not os.path.exists(mine) and os.path.exists(theirs)
