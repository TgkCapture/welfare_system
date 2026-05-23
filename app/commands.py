# app/commands.py
"""
Flask CLI commands.

Register with the app via ``init_commands(app)`` in the app factory.

Available commands:
  flask cleanup-files   — delete old files from upload / report folders
  flask storage-status  — print current folder sizes
  flask create-admin    — create an admin user interactively
"""
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
        '--days', default=7, show_default=True,
        help='Delete files older than this many days.',
    )
    @click.option(
        '--dry-run', is_flag=True, default=False,
        help='Show what would be deleted without actually deleting.',
    )
    def cleanup_files(days, dry_run):
        """Clean up old files from upload and report folders."""
        from app.services.file_cleanup import FileCleanupService

        if dry_run:
            click.echo(f'[DRY RUN] Would clean files older than {days} day(s).')
            sizes = FileCleanupService.get_folder_sizes()
            for folder, stats in sizes.get('folders', {}).items():
                click.echo(
                    f"  {folder}: {stats.get('file_count', 0)} files, "
                    f"{stats.get('size_mb', 0):.2f} MB"
                )
            return

        result = FileCleanupService.cleanup_old_files(days_to_keep=days)

        if result.get('success'):
            click.secho(
                f"✓ Deleted {result['deleted_count']} file(s), "
                f"freed {result['freed_space_mb']:.2f} MB.",
                fg='green',
            )
            for folder, stats in result.get('folder_stats', {}).items():
                if stats.get('deleted', 0):
                    click.echo(
                        f"  {folder}: {stats['deleted']} deleted, "
                        f"{stats['freed_mb']:.2f} MB freed"
                    )
                if stats.get('errors'):
                    for err in stats['errors']:
                        click.secho(f"  warning: {err}", fg='yellow')
        else:
            click.secho(f"✗ Cleanup failed: {result.get('error')}", fg='red')

    # ------------------------------------------------------------------
    # storage-status
    # ------------------------------------------------------------------

    @app.cli.command('storage-status')
    def storage_status():
        """Show current storage usage for all monitored folders."""
        from app.services.file_cleanup import FileCleanupService

        sizes = FileCleanupService.get_folder_sizes()

        if not sizes.get('success'):
            click.secho(f"✗ Error: {sizes.get('error')}", fg='red')
            return

        click.echo('=== Storage Status ===')
        for folder, stats in sizes.get('folders', {}).items():
            exists = stats.get('exists', False)
            if exists:
                click.echo(
                    f"  {folder:10s}: {stats.get('size_mb', 0):7.2f} MB  "
                    f"({stats.get('file_count', 0)} files)"
                )
            else:
                click.secho(f"  {folder:10s}: [folder not found]", fg='yellow')

        click.echo(f"  {'TOTAL':10s}: {sizes.get('total_size_mb', 0):7.2f} MB  "
                   f"({sizes.get('total_files', 0)} files)")
        click.echo('======================')

        # Storage limit warnings
        from app.services.file_cleanup import FileCleanupService
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
    # create-admin
    # ------------------------------------------------------------------

    @app.cli.command('create-admin')
    @click.option('--email',    prompt='Admin email')
    @click.option('--password', prompt='Password', hide_input=True,
                  confirmation_prompt=True)
    def create_admin(email, password):
        """Create an admin user account."""
        from app.extensions import db
        from app.models.user import User

        if len(password) < 8:
            click.secho('✗ Password must be at least 8 characters.', fg='red')
            return

        if User.query.filter_by(email=email).first():
            click.secho(f'✗ Email {email!r} is already registered.', fg='red')
            return

        try:
            user = User(
                email=email,
                password=generate_password_hash(password, method='scrypt'),
                role='admin',
            )
            db.session.add(user)
            db.session.commit()
            click.secho(f'✓ Admin account created for {email}.', fg='green')
        except Exception as e:
            db.session.rollback()
            click.secho(f'✗ Failed: {e}', fg='red')