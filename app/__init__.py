# app/__init__.py
from flask import Flask
import os
import click
from datetime import datetime, timedelta
from app.config import Config
from app.services.file_cleanup import FileCleanupService
from app.extensions import db, login_manager

__version__ = "2.0.0"

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
    from app.extensions import init_extensions
    init_extensions(app)
    
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Initialize scheduler
    from app.services.scheduler import CleanupScheduler
    cleanup_scheduler = CleanupScheduler()
    cleanup_scheduler.init_app(app)
    
    # Register blueprints (import here to avoid circular imports)
    from app.routes.auth import auth as auth_blueprint
    from app.routes.main import main as main_blueprint
    
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    
    # Add CLI commands
    _register_cli_commands(app)
    
    # Create database tables within app context
    with app.app_context():
        db.create_all()
    
    # Error handlers
    from app.controllers.error_controller import ErrorController
    ErrorController.register_error_handlers(app)
    
    return app


def _register_cli_commands(app):
    """Register CLI commands for the application"""
    
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
    
    @app.cli.command('create-admin')
    @click.option('--email', prompt='Admin email', help='Email for the admin user')
    @click.option('--password', prompt=True, hide_input=True, 
                  confirmation_prompt=True, help='Password for the admin user')
    def create_admin_command(email, password):
        """Create an admin user"""
        from werkzeug.security import generate_password_hash
        from app.models.user import User
        
        with app.app_context():
            # Check if user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                click.echo(f"✗ User with email {email} already exists")
                return
            
            try:
                admin_user = User(
                    email=email,
                    password=generate_password_hash(password, method='scrypt'),
                    role='admin'
                )
                db.session.add(admin_user)
                db.session.commit()
                click.echo(f"✓ Admin user {email} created successfully")
            except Exception as e:
                db.session.rollback()
                click.echo(f"✗ Failed to create admin user: {str(e)}")
    
    @app.cli.command('list-users')
    def list_users_command():
        """List all users in the system"""
        from app.models.user import User
        
        with app.app_context():
            users = User.query.order_by(User.created_at).all()
            
            if not users:
                click.echo("No users found")
                return
            
            click.echo("=== Users ===")
            for user in users:
                status = "Active" if user.is_active else "Inactive"
                click.echo(f"ID: {user.id}")
                click.echo(f"Email: {user.email}")
                click.echo(f"Role: {user.role}")
                click.echo(f"Status: {status}")
                click.echo(f"Created: {user.created_at}")
                if user.last_login:
                    click.echo(f"Last Login: {user.last_login}")
                click.echo("---")
    
    @app.cli.command('version')
    def version_command():
        """Show application version"""
        click.echo(f"Welfare System v{__version__}")