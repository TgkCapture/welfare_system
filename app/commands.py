# app/commands.py
"""
Flask CLI commands.

Register with the app via ``init_commands(app)`` in the app factory.

Available commands:
  flask cleanup-files       — delete expired files (each group's retention period)
  flask storage-status      — print storage per group
  flask move-files-to-groups — move existing report files into group folders
  flask create-group        — create a welfare group with preset roles
  flask create-admin        — create a group's first officer (Chairperson)
  flask create-superadmin   — create a platform superadmin
"""
import calendar
import os

import click
from flask import current_app
from werkzeug.security import generate_password_hash


def init_commands(app) -> None:
    """Register all CLI commands with *app*."""

    # ------------------------------------------------------------------
    # cleanup-files
    # ------------------------------------------------------------------

    @app.cli.command('cleanup-files')
    @click.option(
        '--group', 'slug', default=None,
        help='Only clean this group (default: every group, plus logs).',
    )
    @click.option(
        '--dry-run', is_flag=True, default=False,
        help='Show what would be deleted without actually deleting.',
    )
    def cleanup_files(slug, dry_run):
        """Delete expired files, using each group's retention period."""
        from app.models.group import Group
        from app.services.file_cleanup import FileCleanupService

        if slug:
            group = Group.query.filter_by(slug=slug.strip().lower()).first()
            if not group:
                click.secho(f'✗ No group with slug {slug!r}.', fg='red')
                return
            sections = {group.slug: FileCleanupService.cleanup_group(group, dry_run=dry_run)}
        else:
            result = FileCleanupService.cleanup_all(dry_run=dry_run)
            sections = {**result['groups'], '(platform)': result['platform']}

        prefix = '[DRY RUN] Would delete' if dry_run else '✓ Deleted'
        for name, result in sections.items():
            click.secho(
                f"{prefix} {result['deleted_count']} file(s), "
                f"{result['freed_space_mb']:.2f} MB, "
                f"{result['reports_archived']} report(s) archived — {name}",
                fg='yellow' if dry_run else 'green',
            )
            for folder, stats in result['folder_stats'].items():
                for err in stats.get('errors', []):
                    click.secho(f"  warning ({folder}): {err}", fg='yellow')

    # ------------------------------------------------------------------
    # storage-status
    # ------------------------------------------------------------------

    @app.cli.command('storage-status')
    def storage_status():
        """Show storage usage per group and for the whole platform."""
        from app.services.file_cleanup import FileCleanupService

        storage = FileCleanupService.platform_storage()

        click.echo('=== Storage Status ===')
        for row in storage['groups']:
            click.echo(
                f"  {row['group'].slug:20s}: {row['total_size_mb']:7.2f} MB  "
                f"({row['total_files']} files, reports kept {row['retention_days']} days)"
            )
        for name, stats in storage['other'].items():
            click.echo(f"  {name:20s}: {stats['size_mb']:7.2f} MB  ({stats['file_count']} files)")
        click.echo(f"  {'TOTAL':20s}: {storage['total_size_mb']:7.2f} MB")
        click.echo('======================')

        # Storage limit warnings
        limits = FileCleanupService.check_storage_limits()
        for item in limits.get('exceeded', []):
            click.secho(
                f"  ⚠  {item['folder']} EXCEEDED limit "
                f"({item['current_mb']:.1f} / {item['limit_mb']} MB)",
                fg='red',
            )
        for item in limits.get('warnings', []):
            click.secho(
                f"  ⚠  {item['folder']} at {item['percent_full']}% of limit",
                fg='yellow',
            )

    # ------------------------------------------------------------------
    # move-files-to-groups
    # ------------------------------------------------------------------

    @app.cli.command('move-files-to-groups')
    @click.option(
        '--dry-run', is_flag=True, default=False,
        help='Show what would be moved without moving anything.',
    )
    def move_files_to_groups(dry_run):
        """Move report files into their group's folder (one-off, safe to re-run)."""
        import os
        import shutil

        from app.extensions import db
        from app.models.group import Group
        from app.models.report import GeneratedReport
        from app.services.group_storage import group_folder

        groups = {g.id: g for g in Group.query}
        moved = missing = in_place = 0
        for report in GeneratedReport.query.order_by(GeneratedReport.id).all():  # platform-wide
            target_dir = group_folder('reports', groups[report.group_id])
            if not os.path.isfile(report.file_path):
                missing += 1
                continue
            if os.path.dirname(os.path.abspath(report.file_path)) == os.path.abspath(target_dir):
                in_place += 1
                continue

            target = os.path.join(target_dir, os.path.basename(report.file_path))
            if os.path.exists(target):
                target = os.path.join(target_dir, f'{report.id}_{os.path.basename(report.file_path)}')
            click.echo(f'  {report.file_path} → {target}')
            if not dry_run:
                shutil.move(report.file_path, target)
                report.file_path = target
                db.session.commit()   # per file, so the DB never points at a moved file
            moved += 1

        verb = 'Would move' if dry_run else '✓ Moved'
        click.secho(
            f'{verb} {moved} file(s); {in_place} already in place; '
            f'{missing} missing on disk (their reports keep their figures).',
            fg='yellow' if dry_run else 'green',
        )

    # ------------------------------------------------------------------
    # convert-legacy-workbook
    # ------------------------------------------------------------------

    @app.cli.command('convert-legacy-workbook')
    @click.argument('source', type=click.Path(exists=True, dir_okay=False))
    @click.option('--title', default='Mzugoss Class of 2018', show_default=True,
                  help='Group name shown in the workbook.')
    @click.option('--out-dir', default='conversion', show_default=True,
                  help='Folder for the workbook, review and name suggestions (git-ignored).')
    @click.option('--merges', 'merges_file', type=click.Path(exists=True, dir_okay=False),
                  help='A name-suggestions CSV with "yes" in the confirm column for pairs to merge.')
    @click.option('--drop-repeated-payouts', is_flag=True, default=False,
                  help="Drop payouts that repeat the previous year's (same member and amount).")
    def convert_legacy_workbook(source, title, out_dir, merges_file, drop_repeated_payouts):
        """Convert an old-layout workbook to the standard layout, with a review report."""
        import csv

        from app.services.legacy_conversion import LegacyConverter
        from app.services.workbook_template import write_workbook

        merges = {}
        if merges_file:
            with open(merges_file, newline='', encoding='utf-8') as fh:
                for row in csv.DictReader(fh):
                    if (row.get('confirm') or '').strip().lower() in ('yes', 'y', 'x', '1'):
                        merges[row['merge']] = row['keep']

        conversion = LegacyConverter(source, title, merges=merges,
                                     drop_repeated_payouts=drop_repeated_payouts).convert()

        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(source))[0]
        workbook_path = os.path.join(out_dir, f'{stem}_standard.xlsx')
        write_workbook(conversion.spec).save(workbook_path)

        warnings, mismatches = _verify_conversion(workbook_path, conversion.legacy_totals)
        review = conversion.review + _verification_section(merges, warnings, mismatches)
        review_path = os.path.join(out_dir, f'{stem}_review.md')
        with open(review_path, 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(review) + '\n')

        suggestions_path = os.path.join(out_dir, f'{stem}_name_suggestions.csv')
        with open(suggestions_path, 'w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(['keep', 'merge', 'similarity', 'keep_years', 'merge_years', 'confirm'])
            for keep, merge, score, keep_years, merge_years in conversion.suggestions:
                writer.writerow([keep, merge, score, ' '.join(map(str, keep_years)),
                                 ' '.join(map(str, merge_years)), ''])

        click.secho(f'✓ Workbook:         {workbook_path}', fg='green')
        click.echo(f'  Review:           {review_path}')
        click.echo(f'  Name suggestions: {suggestions_path} ({len(conversion.suggestions)} pair(s))')
        colour = 'green' if not mismatches else 'red'
        click.secho(f'  Check: {len(mismatches)} month(s) differ from the old sheet; '
                    f'{len(warnings)} sync warning(s).', fg=colour)

    # ------------------------------------------------------------------
    # create-group
    # ------------------------------------------------------------------

    @app.cli.command('create-group')
    @click.option('--name', prompt='Group name')
    @click.option('--slug', prompt='URL slug (e.g. mzugoss)')
    def create_group(name, slug):
        """Create a welfare group with default settings and preset roles."""
        from app.extensions import db
        from app.models.group import Group, GroupSettings
        from app.models.ledger import PayoutPurpose
        from app.models.role import Role

        slug = slug.strip().lower()
        if not Group.is_valid_slug(slug):
            click.secho('✗ Slug must be lowercase letters, digits and single hyphens.', fg='red')
            return
        if Group.query.filter_by(slug=slug).first():
            click.secho(f'✗ A group with slug {slug!r} already exists.', fg='red')
            return

        try:
            group = Group(name=name, slug=slug)
            group.settings = GroupSettings(display_name=name)
            db.session.add(group)
            Role.seed_presets(group)
            PayoutPurpose.seed_defaults(group)
            db.session.commit()
            click.secho(f'✓ Group {name!r} created at /g/{slug}.', fg='green')
        except Exception as e:
            db.session.rollback()
            click.secho(f'✗ Failed: {e}', fg='red')

    # ------------------------------------------------------------------
    # create-admin
    # ------------------------------------------------------------------

    @app.cli.command('create-admin')
    @click.option('--group', 'slug', prompt='Group slug')
    @click.option('--email',    prompt='Admin email')
    @click.option('--password', prompt='Password', hide_input=True,
                  confirmation_prompt=True)
    def create_admin(slug, email, password):
        """Create a group's first officer with the Chairperson role."""
        from app.models.group import Group
        from app.models.role import Role

        group = Group.query.filter_by(slug=slug.strip().lower()).first()
        if not group:
            click.secho(f'✗ No group with slug {slug!r}. Run `flask create-group` first.', fg='red')
            return

        _create_account(
            email, password, label=f'{group.name} admin',
            group_id=group.id,
            role=Role.query.filter_by(group_id=group.id, name='Chairperson').first(),
        )

    # ------------------------------------------------------------------
    # create-superadmin
    # ------------------------------------------------------------------

    @app.cli.command('create-superadmin')
    @click.option('--email',    prompt='Superadmin email')
    @click.option('--password', prompt='Password', hide_input=True,
                  confirmation_prompt=True)
    def create_superadmin(email, password):
        """Create a platform superadmin (belongs to no group)."""
        _create_account(
            email, password, label='Superadmin', group_id=None, is_superadmin=True,
        )


def _verify_conversion(workbook_path, legacy_totals):
    """Sync the converted workbook into a throwaway database and compare month totals.

    Returns (sync warnings, [(year, month, old total, converted total)]).
    """
    import tempfile

    from app import create_app
    from app.extensions import db
    from app.models.group import Group, GroupSettings
    from app.models.ledger import PayoutPurpose
    from app.models.member import PeriodSummary
    from app.services.standard_sync import StandardSync

    scratch = tempfile.mkdtemp()
    check_app = create_app('testing', {
        'SQLALCHEMY_DATABASE_URI': 'sqlite://',
        'UPLOAD_FOLDER': os.path.join(scratch, 'uploads'),
        'REPORT_FOLDER': os.path.join(scratch, 'reports'),
        'LOGS_FOLDER': os.path.join(scratch, 'logs'),
    })
    with check_app.app_context():
        db.create_all()
        group = Group(name='Check', slug='check', settings=GroupSettings(display_name='Check'))
        db.session.add(group)
        PayoutPurpose.seed_defaults(group)
        db.session.commit()
        run = StandardSync.sync(group, workbook_path)
        stored = {(s.year, s.month): s.total_contributions for s in PeriodSummary.for_group(group.id)}
        mismatches = [
            (year, month, old, stored.get((year, month), 0.0))
            for (year, month), old in sorted(legacy_totals.items())
            if abs(old - stored.get((year, month), 0.0)) > 0.005
        ]
        warnings = list(run.warnings)
        db.session.remove()
    return warnings, mismatches


def _verification_section(merges, warnings, mismatches):
    lines = ['## Check', '']
    if merges:
        lines += [f'Merged as confirmed: ' + '; '.join(f'{m} → {k}' for m, k in merges.items()) + '.', '']
    if mismatches:
        lines += ['**Months whose total differs from the old sheet:**', '',
                  '| Month | Old sheet | Converted |', '| --- | ---: | ---: |']
        lines += [f'| {calendar.month_name[m]} {y} | {old:,.0f} | {new:,.0f} |' for y, m, old, new in mismatches]
    else:
        lines.append('Every month\'s total paid in matches the old sheet.')
    lines += ['', f'Syncing the converted workbook gives {len(warnings)} warning(s) '
                  '(the treasurer sees these after each sync until they are fixed):', '']
    lines += [f"- {w['where']}: {w['message']}" for w in warnings] or ['- none']
    return lines + ['']


def _create_account(email, password, label, **fields) -> None:
    """Validate and create a User, reporting the outcome on the console."""
    from app.extensions import db
    from app.models.user import User

    email = email.strip()
    if len(password) < 8:
        click.secho('✗ Password must be at least 8 characters.', fg='red')
        return

    # Emails are unique per group (superadmins form their own "group")
    if User.email_taken(email, fields.get('group_id')):
        click.secho(f'✗ Email {email!r} is already registered.', fg='red')
        return

    try:
        user = User(
            email=email,
            password=generate_password_hash(password, method='scrypt'),
            **fields,
        )
        db.session.add(user)
        db.session.commit()
        click.secho(f'✓ {label} account created for {email}.', fg='green')
    except Exception as e:
        db.session.rollback()
        click.secho(f'✗ Failed: {e}', fg='red')
