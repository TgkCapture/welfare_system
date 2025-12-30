# app/commands.py
import click
from flask import current_app
from app.services.scheduler import CleanupScheduler
from app.services.file_cleanup import FileCleanupService

def init_commands(app):
    """Initialize CLI commands"""
    
    @app.cli.command('cleanup-files')
    @click.option('--days', default=7, help='Days to keep files (default: 7)')
    def cleanup_files(days):
        """Clean up old files from upload and report folders"""
        with app.app_context():
            result = CleanupScheduler.run_manual_cleanup(days_to_keep=days)
            
            if result.get('success'):
                click.echo(f"✓ Cleaned up {result['deleted_count']} files")
                if result.get('deleted_files'):
                    click.echo("Deleted files:")
                    for filename in result['deleted_files']:
                        click.echo(f"  - {filename}")
            else:
                click.echo(f"✗ Cleanup failed: {result.get('error')}")
    
    @app.cli.command('storage-status')
    def storage_status():
        """Show storage usage statistics"""
        with app.app_context():
            sizes = FileCleanupService.get_folder_sizes()
            
            click.echo("=== Storage Status ===")
            click.echo(f"Upload Folder: {sizes['upload_folder_mb']} MB ({sizes['upload_folder_count']} files)")
            click.echo(f"Report Folder: {sizes['report_folder_mb']} MB ({sizes['report_folder_count']} files)")
            click.echo(f"Total: {sizes['total_mb']} MB")
            click.echo("=====================")