# app/__init__.py
from flask import Flask, g, request
import os
import click
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

from app.config import Config
from app.services.file_cleanup import FileCleanupService
from app.extensions import db, login_manager #migrate, mail, csrf
from app.utils.logging_utils import setup_logging

__version__ = "2.0.0"

def create_app(config_class=Config):
    """Application factory function"""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    
    # Load instance config if exists
    instance_config_path = os.path.join(app.instance_path, 'config.py')
    if os.path.exists(instance_config_path):
        app.config.from_pyfile('config.py')
    
    app.version = __version__
    
    # Create necessary directories
    create_app_directories(app)
    
    # Setup logging
    setup_app_logging(app)
    
    # Initialize extensions
    from app.extensions import init_extensions
    init_extensions(app)
    
    # Register models
    from app.models.user import User
    from app.models.report import GeneratedReport, ReportAccessLog
    # from app.models.audit_log import AuditLog
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login"""
        return User.query.get(int(user_id))
    
    @login_manager.unauthorized_handler
    def unauthorized():
        """Handle unauthorized access attempts"""
        from flask import flash, redirect, url_for
        flash('Please log in to access this page.', 'warning')
        return redirect(url_for('auth.login'))
    
    # Initialize scheduler
    from app.services.scheduler import CleanupScheduler
    app.cleanup_scheduler = CleanupScheduler()
    app.cleanup_scheduler.init_app(app)
    
    # Register blueprints (avoid circular imports)
    register_blueprints(app)
    
    # Add CLI commands
    _register_cli_commands(app)
    
    # Create database tables within app context
    with app.app_context():
        db.create_all()
        
        # Check and create default admin if needed
        create_default_admin_if_needed(app)
    
    # Error handlers
    from app.controllers.error_controller import ErrorController
    ErrorController.register_error_handlers(app)
    
    # Context processors
    _register_context_processors(app)
    
    # Request handlers
    _register_request_handlers(app)
    
    # Template filters
    _register_template_filters(app)
    
    return app


def create_app_directories(app):
    """Create necessary application directories"""
    directories = [
        app.config['UPLOAD_FOLDER'],
        app.config['REPORT_FOLDER'],
        app.config['TEMP_FOLDER'],
        app.config['BACKUP_FOLDER'],
    ]
    
    if 'LOGS_FOLDER' in app.config:
        directories.append(app.config['LOGS_FOLDER'])
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        app.logger.debug(f"Created/verified directory: {directory}")


def setup_app_logging(app):
    """Setup application logging"""
    if not app.debug and not app.testing:
        # Ensure logs directory exists
        logs_dir = app.config.get('LOGS_FOLDER', 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        # Main application log
        file_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'app.log'),
            maxBytes=app.config.get('LOG_FILE_MAX_SIZE', 10485760),  # 10MB
            backupCount=app.config.get('LOG_BACKUP_COUNT', 10)
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application startup')
        
        # Error log
        error_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'error.log'),
            maxBytes=app.config.get('LOG_FILE_MAX_SIZE', 10485760),
            backupCount=app.config.get('LOG_BACKUP_COUNT', 10)
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        app.logger.addHandler(error_handler)
        
        # SQL log
        sql_logger = logging.getLogger('sqlalchemy.engine')
        sql_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'sql.log'),
            maxBytes=app.config.get('LOG_FILE_MAX_SIZE', 10485760),
            backupCount=app.config.get('LOG_BACKUP_COUNT', 5)
        )
        sql_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        ))
        sql_logger.addHandler(sql_handler)
        sql_logger.setLevel(logging.WARNING)


def register_blueprints(app):
    """Register all application blueprints"""
    from app.routes.auth import auth as auth_blueprint
    from app.routes.main import main as main_blueprint
    # from app.routes.admin import admin as admin_blueprint
    from app.routes.report import report as report_blueprint
    # from app.routes.api import api as api_blueprint
    
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(main_blueprint)
    # app.register_blueprint(admin_blueprint, url_prefix='/admin')
    app.register_blueprint(report_blueprint, url_prefix='/reports')
    # app.register_blueprint(api_blueprint, url_prefix='/api/v1')


def create_default_admin_if_needed(app):
    """Create default admin user if no users exist"""
    from app.models.user import User
    from werkzeug.security import generate_password_hash
    
    if User.query.count() == 0:
        default_admin_email = app.config.get('DEFAULT_ADMIN_EMAIL', 'admin@welfare.org')
        default_admin_password = app.config.get('DEFAULT_ADMIN_PASSWORD', 'admin123')
        
        try:
            admin_user = User(
                email=default_admin_email,
                password=generate_password_hash(default_admin_password, method='scrypt'),
                role='admin',
                is_active=True
            )
            db.session.add(admin_user)
            db.session.commit()
            app.logger.info(f"Default admin user created: {default_admin_email}")
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Failed to create default admin: {str(e)}")


def _register_cli_commands(app):
    """Register CLI commands for the application"""
    
    @app.cli.command('cleanup-files')
    @click.option('--days', default=None, type=int, 
                  help='Days to keep files (default: from config)')
    @click.option('--dry-run', is_flag=True, 
                  help='Show what would be deleted without actually deleting')
    @click.option('--force', is_flag=True, 
                  help='Force cleanup without confirmation')
    def cleanup_files_command(days, dry_run, force):
        """Clean up old files from upload and report folders"""
        with app.app_context():
            if days is None:
                days = app.config.get('REPORT_RETENTION_DAYS', 7)
            
            if not force:
                click.confirm(f'Cleanup files older than {days} days?', abort=True)
            
            if dry_run:
                click.echo(f"=== DRY RUN - No files will be deleted ===")
                click.echo(f"Looking for files older than {days} days")
            
            result = FileCleanupService.cleanup_old_files(
                days_to_keep=days, 
                dry_run=dry_run
            )
            
            if result.get('success'):
                deleted_count = result.get('deleted_count', 0)
                freed_mb = result.get('freed_space_mb', 0)
                
                if dry_run:
                    click.echo(f"Would delete {deleted_count} files")
                    click.echo(f"Would free {freed_mb:.2f} MB")
                else:
                    click.echo(f"✓ Cleaned up {deleted_count} files")
                    click.echo(f"✓ Freed {freed_mb:.2f} MB")
                
                # Show folder-wise stats
                if 'folder_stats' in result:
                    click.echo("\n=== Folder Statistics ===")
                    for folder_name, stats in result['folder_stats'].items():
                        if stats.get('exists'):
                            deleted = stats.get('deleted', 0)
                            freed = stats.get('freed_mb', 0)
                            click.echo(f"{folder_name}: {deleted} files, {freed:.2f} MB")
            else:
                click.echo(f"✗ Cleanup failed: {result.get('error', 'Unknown error')}")
    
    @app.cli.command('storage-status')
    @click.option('--detailed', '-d', is_flag=True, help='Show detailed information')
    def storage_status_command(detailed):
        """Show storage usage statistics"""
        with app.app_context():
            result = FileCleanupService.get_folder_sizes()
            
            if result.get('success'):
                click.echo("=== Storage Status ===")
                click.echo(f"Generated: {result['timestamp']}")
                click.echo(f"Total: {result['total_size_mb']:.2f} MB")
                click.echo(f"Total Files: {result['total_files']}")
                click.echo()
                
                for folder_name, stats in result.get('folders', {}).items():
                    if stats.get('exists'):
                        size_mb = stats.get('size_mb', 0)
                        file_count = stats.get('file_count', 0)
                        click.echo(f"{folder_name}:")
                        click.echo(f"  Size: {size_mb:.2f} MB")
                        click.echo(f"  Files: {file_count}")
                        
                        if detailed:
                            if stats.get('oldest_date'):
                                click.echo(f"  Oldest: {stats['oldest_file']} ({stats['oldest_date']})")
                            if stats.get('newest_date'):
                                click.echo(f"  Newest: {stats['newest_file']} ({stats['newest_date']})")
                        click.echo()
            else:
                click.echo(f"✗ Failed to get storage status: {result.get('error')}")
    
    @app.cli.command('create-user')
    @click.option('--email', prompt=True, help='Email for the user')
    @click.option('--password', prompt=True, hide_input=True, 
                  confirmation_prompt=True, help='Password for the user')
    @click.option('--role', type=click.Choice(['admin', 'clerk', 'viewer']), 
                  default='viewer', help='User role')
    @click.option('--active/--inactive', default=True, help='User status')
    def create_user_command(email, password, role, active):
        """Create a new user"""
        from werkzeug.security import generate_password_hash
        from app.models.user import User
        
        with app.app_context():
            # Validate email
            import re
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                click.echo(f"✗ Invalid email format: {email}")
                return
            
            # Check if user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                click.echo(f"✗ User with email {email} already exists")
                return
            
            try:
                new_user = User(
                    email=email,
                    password=generate_password_hash(password, method='scrypt'),
                    role=role,
                    is_active=active
                )
                db.session.add(new_user)
                db.session.commit()
                click.echo(f"✓ User created successfully:")
                click.echo(f"  Email: {email}")
                click.echo(f"  Role: {role}")
                click.echo(f"  Status: {'Active' if active else 'Inactive'}")
            except Exception as e:
                db.session.rollback()
                click.echo(f"✗ Failed to create user: {str(e)}")
    
    @app.cli.command('list-users')
    @click.option('--role', help='Filter by role')
    @click.option('--active-only', is_flag=True, help='Show only active users')
    @click.option('--format', type=click.Choice(['table', 'csv', 'json']), 
                  default='table', help='Output format')
    def list_users_command(role, active_only, format):
        """List all users in the system"""
        from app.models.user import User
        import json
        
        with app.app_context():
            query = User.query
            
            if role:
                query = query.filter_by(role=role)
            if active_only:
                query = query.filter_by(is_active=True)
            
            users = query.order_by(User.created_at).all()
            
            if not users:
                click.echo("No users found")
                return
            
            if format == 'json':
                users_data = [{
                    'id': user.id,
                    'email': user.email,
                    'role': user.role,
                    'status': 'active' if user.is_active else 'inactive',
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'last_login': user.last_login.isoformat() if user.last_login else None
                } for user in users]
                click.echo(json.dumps(users_data, indent=2, default=str))
                return
            
            if format == 'csv':
                click.echo('id,email,role,status,created_at,last_login')
                for user in users:
                    status = 'active' if user.is_active else 'inactive'
                    created = user.created_at.isoformat() if user.created_at else ''
                    last_login = user.last_login.isoformat() if user.last_login else ''
                    click.echo(f'{user.id},{user.email},{user.role},{status},{created},{last_login}')
                return
            
            # Table format (default)
            click.echo("=== Users ===")
            for user in users:
                status = "✓ Active" if user.is_active else "✗ Inactive"
                click.echo(f"ID: {user.id}")
                click.echo(f"Email: {user.email}")
                click.echo(f"Role: {user.role}")
                click.echo(f"Status: {status}")
                click.echo(f"Created: {user.created_at}")
                if user.last_login:
                    click.echo(f"Last Login: {user.last_login}")
                click.echo("---")
            click.echo(f"Total: {len(users)} users")
    
    @app.cli.command('backup-database')
    @click.option('--output', '-o', help='Output file path')
    @click.option('--compress', '-c', is_flag=True, help='Compress backup')
    def backup_database_command(output, compress):
        """Create a database backup"""
        import sqlite3
        import gzip
        from datetime import datetime
        
        with app.app_context():
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            
            if not os.path.exists(db_path):
                click.echo(f"✗ Database file not found: {db_path}")
                return
            
            if not output:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output = f"backup_{timestamp}.db"
                if compress:
                    output += '.gz'
            
            try:
                # Connect to source database
                source = sqlite3.connect(db_path)
                
                if compress:
                    # Backup with compression
                    with gzip.open(output, 'wb') as f:
                        for line in source.iterdump():
                            f.write((line + '\n').encode('utf-8'))
                else:
                    # Backup without compression
                    dest = sqlite3.connect(output)
                    source.backup(dest)
                    dest.close()
                
                source.close()
                
                file_size = os.path.getsize(output)
                click.echo(f"✓ Backup created: {output}")
                click.echo(f"✓ Size: {file_size / 1024:.2f} KB")
                
            except Exception as e:
                click.echo(f"✗ Backup failed: {str(e)}")
    
    @app.cli.command('version')
    def version_command():
        """Show application version"""
        click.echo(f"Mzugoss Welfare System v{__version__}")
        click.echo(f"Environment: {app.config.get('ENV', 'production')}")
        click.echo(f"Debug mode: {app.debug}")
    
    @app.cli.command('reset-password')
    @click.option('--email', prompt=True, help='User email')
    @click.option('--password', prompt=True, hide_input=True, 
                  confirmation_prompt=True, help='New password')
    def reset_password_command(email, password):
        """Reset a user's password"""
        from werkzeug.security import generate_password_hash
        from app.models.user import User
        
        with app.app_context():
            user = User.query.filter_by(email=email).first()
            
            if not user:
                click.echo(f"✗ User not found: {email}")
                return
            
            try:
                user.password = generate_password_hash(password, method='scrypt')
                db.session.commit()
                click.echo(f"✓ Password reset for {email}")
            except Exception as e:
                db.session.rollback()
                click.echo(f"✗ Failed to reset password: {str(e)}")
    
    @app.cli.command('system-health')
    def system_health_command():
        """Check system health and status"""
        with app.app_context():
            from app.models.user import User
            from app.models.report import GeneratedReport
            
            click.echo("=== System Health Check ===")
            
            # Database connection
            try:
                db.session.execute('SELECT 1')
                click.echo("✓ Database: Connected")
            except Exception as e:
                click.echo(f"✗ Database: Error - {str(e)}")
            
            # User count
            user_count = User.query.count()
            active_users = User.query.filter_by(is_active=True).count()
            click.echo(f"✓ Users: {user_count} total, {active_users} active")
            
            # Report count
            report_count = GeneratedReport.query.count()
            active_reports = GeneratedReport.query.filter_by(is_archived=False).count()
            click.echo(f"✓ Reports: {report_count} total, {active_reports} active")
            
            # Directory permissions
            directories = [
                ('Upload', app.config['UPLOAD_FOLDER']),
                ('Report', app.config['REPORT_FOLDER']),
                ('Temp', app.config['TEMP_FOLDER']),
            ]
            
            for name, path in directories:
                if os.path.exists(path):
                    if os.access(path, os.W_OK):
                        click.echo(f"✓ {name} folder: Writable")
                    else:
                        click.echo(f"✗ {name} folder: Not writable")
                else:
                    click.echo(f"✗ {name} folder: Does not exist")
            
            # Storage check
            storage_check = FileCleanupService.check_storage_limits()
            if storage_check.get('success'):
                total_size = storage_check.get('total_size_mb', 0)
                warnings = len(storage_check.get('warnings', []))
                exceeded = len(storage_check.get('exceeded', []))
                
                if exceeded > 0:
                    click.echo(f"✗ Storage: {total_size:.2f} MB (Exceeds limits)")
                elif warnings > 0:
                    click.echo(f"⚠ Storage: {total_size:.2f} MB (Approaching limits)")
                else:
                    click.echo(f"✓ Storage: {total_size:.2f} MB (OK)")
            else:
                click.echo(f"✗ Storage check failed: {storage_check.get('error')}")
            
            click.echo("=========================")


def _register_context_processors(app):
    """Register context processors for templates"""
    
    @app.context_processor
    def inject_version():
        """Inject version into all templates"""
        return dict(app_version=__version__)
    
    @app.context_processor
    def inject_current_year():
        """Inject current year into templates"""
        return dict(current_year=datetime.now().year)
    
    @app.context_processor
    def inject_config():
        """Inject config values into templates"""
        return dict(
            app_name=app.config.get('APP_NAME', 'Mzugoss Welfare'),
            retention_days=app.config.get('REPORT_RETENTION_DAYS', 7),
            max_upload_size=app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024) // (1024 * 1024)
        )
    
    @app.context_processor
    def inject_user_info():
        """Inject user information into templates"""
        from flask_login import current_user
        
        if current_user.is_authenticated:
            return dict(
                current_user_role=current_user.role,
                current_user_email=current_user.email
            )
        return dict(current_user_role=None, current_user_email=None)


def _register_request_handlers(app):
    """Register request handlers"""
    
    @app.before_request
    def before_request():
        """Execute before each request"""
        g.start_time = datetime.now()
        g.request_id = os.urandom(8).hex()
        
        # Log request for non-static files
        if not request.endpoint or request.endpoint != 'static':
            app.logger.debug(
                f"Request [{g.request_id}]: {request.method} {request.path} "
                f"from {request.remote_addr}"
            )
    
    @app.after_request
    def after_request(response):
        """Execute after each request"""
        if hasattr(g, 'start_time'):
            duration = (datetime.now() - g.start_time).total_seconds()
            
            # Log slow requests
            if duration > 1.0:  # More than 1 second
                app.logger.warning(
                    f"Slow request [{g.request_id}]: {request.method} {request.path} "
                    f"took {duration:.2f}s"
                )
            
            # Add timing header
            response.headers['X-Response-Time'] = f'{duration:.3f}s'
        
        # Security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        return response


def _register_template_filters(app):
    """Register custom template filters"""
    
    @app.template_filter('format_currency')
    def format_currency(value):
        """Format number as currency"""
        try:
            return f"MWK {float(value):,.2f}"
        except (ValueError, TypeError):
            return f"MWK 0.00"
    
    @app.template_filter('format_date')
    def format_date(value, format='%B %d, %Y'):
        """Format datetime object"""
        if value is None:
            return ''
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except ValueError:
                return value
        return value.strftime(format)
    
    @app.template_filter('format_filesize')
    def format_filesize(value):
        """Format file size in bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if abs(value) < 1024.0:
                return f"{value:3.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} TB"
    
    @app.template_filter('truncate')
    def truncate(value, length=100, ellipsis='...'):
        """Truncate string to specified length"""
        if len(value) <= length:
            return value
        return value[:length - len(ellipsis)] + ellipsis