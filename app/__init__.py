# app/__init__.py
from flask import Flask
import os
import click
from datetime import datetime, timedelta
from app.config import Config
from app.services.file_cleanup import FileCleanupService

__version__ = "1.3.1"

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    
    # Load instance config
    instance_config_path = os.path.join(app.instance_path, 'config.py')
    if os.path.exists(instance_config_path):
        app.config.from_pyfile('config.py')
    
    app.version = __version__
    
    # Create directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
    if 'LOGS_FOLDER' in app.config:
        os.makedirs(app.config['LOGS_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    from app.extensions import db, login_manager, init_extensions
    init_extensions(app)
    
    
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Initialize scheduler
    from app.services.scheduler import CleanupScheduler
    cleanup_scheduler = CleanupScheduler()
    cleanup_scheduler.init_app(app)
    
    # Register blueprints
    from app.routes.auth import auth as auth_blueprint
    from app.routes.main import main as main_blueprint
    
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    
    # Add CLI commands directly
    @app.cli.command('cleanup-files')
    @click.option('--days', default=7, help='Days to keep files (default: 7)')
    def cleanup_files_command(days):
        """Clean up old files from upload and report folders"""
        with app.app_context():
            result = FileCleanupService.cleanup_old_files(days_to_keep=days)
            
            if result.get('success'):
                click.echo(f"✓ Cleaned up {result['deleted_count']} files")
                if result.get('deleted_files'):
                    click.echo("Deleted files:")
                    for filename in result['deleted_files'][:10]:  # Show first 10
                        click.echo(f"  - {filename}")
                    if len(result['deleted_files']) > 10:
                        click.echo(f"  ... and {len(result['deleted_files']) - 10} more")
            else:
                click.echo(f"✗ Cleanup failed: {result.get('error')}")
    
    @app.cli.command('storage-status')
    def storage_status_command():
        """Show storage usage statistics"""
        with app.app_context():
            sizes = FileCleanupService.get_folder_sizes()
            
            click.echo("=== Storage Status ===")
            click.echo(f"Upload Folder: {sizes['upload_folder_mb']} MB ({sizes['upload_folder_count']} files)")
            click.echo(f"Report Folder: {sizes['report_folder_mb']} MB ({sizes['report_folder_count']} files)")
            click.echo(f"Total: {sizes['total_mb']} MB")
            click.echo("=====================")
    
    # Create database tables within app context
    with app.app_context():
        db.create_all()
    
    # Error handlers
    from app.routes.errors import register_error_handlers
    register_error_handlers(app)
    
    return app