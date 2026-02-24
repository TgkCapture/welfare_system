# app/services/file_cleanup.py
import os
import time
from datetime import datetime, timedelta
from flask import current_app
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class FileCleanupService:
    """Service for cleaning up old files with improved error handling and logging"""
    
    @staticmethod
    def cleanup_old_files(days_to_keep=None):
        """
        Clean up files older than specified days
        
        Args:
            days_to_keep: Number of days to keep files (default: from config)
            
        Returns:
            dict: Results with success status, counts, and freed space
        """
        try:
            if days_to_keep is None:
                days_to_keep = current_app.config.get('REPORT_RETENTION_DAYS', 7)
            
            if current_app:
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 
                    os.path.join(os.getcwd(), 'uploads'))
                report_folder = current_app.config.get('REPORT_FOLDER',
                    os.path.join(os.getcwd(), 'reports'))
                logs_folder = current_app.config.get('LOGS_FOLDER',
                    os.path.join(os.getcwd(), 'logs'))
            else:
                upload_folder = os.path.join(os.getcwd(), 'uploads')
                report_folder = os.path.join(os.getcwd(), 'reports')
                logs_folder = os.path.join(os.getcwd(), 'logs')
            
            cutoff_timestamp = time.time() - (days_to_keep * 24 * 3600)
            
            # Different retention for different folders
            folders_to_clean = [
                ('uploads', upload_folder, 3),  # Keep uploads for 3 days
                ('reports', report_folder, days_to_keep),  # Use configured retention
                ('logs', logs_folder, 30)  # Keep logs for 30 days
            ]
            
            total_stats = {
                'success': True,
                'deleted_count': 0,
                'freed_space_mb': 0.0,
                'folder_stats': {},
                'cutoff_date': datetime.fromtimestamp(cutoff_timestamp).isoformat(),
                'retention_days': days_to_keep,
                'execution_time': None
            }
            
            start_time = time.time()
            
            for folder_name, folder_path, retention_days in folders_to_clean:
                if not os.path.exists(folder_path):
                    logger.debug(f"Folder {folder_name} does not exist: {folder_path}")
                    total_stats['folder_stats'][folder_name] = {
                        'exists': False,
                        'deleted': 0,
                        'freed_mb': 0.0,
                        'retention_days': retention_days,
                        'error': 'Folder does not exist'
                    }
                    continue
                
                folder_cutoff = time.time() - (retention_days * 24 * 3600)
                folder_result = FileCleanupService._cleanup_single_folder(
                    folder_path, folder_cutoff, folder_name
                )
                folder_result['retention_days'] = retention_days
                
                total_stats['folder_stats'][folder_name] = folder_result
                total_stats['deleted_count'] += folder_result.get('deleted', 0)
                total_stats['freed_space_mb'] += folder_result.get('freed_mb', 0.0)
            
            execution_time = time.time() - start_time
            total_stats['execution_time'] = round(execution_time, 2)
            
            # Log summary
            logger.info(
                f"Cleanup completed: {total_stats['deleted_count']} files deleted, "
                f"{total_stats['freed_space_mb']:.2f} MB freed in {execution_time:.2f}s. "
                f"Retention: {days_to_keep} days, Cutoff: {total_stats['cutoff_date']}"
            )
            
            return total_stats
            
        except Exception as e:
            logger.error(f"Error during file cleanup: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'deleted_count': 0,
                'freed_space_mb': 0.0,
                'folder_stats': {}
            }
    
    @staticmethod
    def cleanup_scheduled():
        """Scheduled cleanup with database archiving"""
        from app import db
        from app.models.report import GeneratedReport
        from datetime import datetime
        
        try:
            # Get retention days from config
            days_to_keep = current_app.config.get('REPORT_RETENTION_DAYS', 7)
            
            # Run file cleanup
            cleanup_result = FileCleanupService.cleanup_old_files(days_to_keep)
            
            # Archive old reports in database
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            old_reports = GeneratedReport.query.filter(
                GeneratedReport.generated_at < cutoff_date,
                GeneratedReport.is_archived == False
            ).all()
            
            for report in old_reports:
                report.is_archived = True
                report.archived_at = datetime.utcnow()
            
            db.session.commit()
            
            logger.info(
                f"Scheduled cleanup completed. "
                f"Files: {cleanup_result.get('deleted_count', 0)} deleted, "
                f"Reports: {len(old_reports)} archived."
            )
            
            return {
                'file_cleanup': cleanup_result,
                'reports_archived': len(old_reports),
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in scheduled cleanup: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _cleanup_single_folder(folder_path, cutoff_timestamp, folder_name=""):
        """Clean up files in a specific folder"""
        stats = {
            'path': folder_path,
            'exists': True,
            'deleted': 0,
            'failed': 0,
            'freed_bytes': 0,
            'freed_mb': 0.0,
            'skipped': 0,
            'errors': []
        }
        
        try:
            folder_path_obj = Path(folder_path)
            
            # Ensure it's a directory
            if not folder_path_obj.is_dir():
                stats['exists'] = False
                stats['errors'].append(f"Not a directory: {folder_path}")
                return stats
            
            file_count = 0
            deleted_count = 0
            failed_count = 0
            freed_bytes = 0
            
            # Walk through all files in the folder
            for file_path in folder_path_obj.rglob('*'):
                if not file_path.is_file():
                    continue
                
                file_count += 1
                
                try:
                    # Get file modification time
                    file_mtime = file_path.stat().st_mtime
                    
                    # Check if file is older than cutoff
                    if file_mtime < cutoff_timestamp:
                        file_size = file_path.stat().st_size
                        
                        # Delete the file
                        file_path.unlink()
                        
                        deleted_count += 1
                        freed_bytes += file_size
                        
                        logger.debug(
                            f"Deleted {folder_name}/{file_path.name} "
                            f"({file_size/1024/1024:.2f} MB, "
                            f"modified: {datetime.fromtimestamp(file_mtime)})"
                        )
                    else:
                        stats['skipped'] += 1
                        
                except PermissionError as e:
                    failed_count += 1
                    stats['errors'].append(f"Permission error: {file_path.name} - {str(e)}")
                    logger.warning(f"Permission denied deleting {file_path.name}: {str(e)}")
                except Exception as e:
                    failed_count += 1
                    stats['errors'].append(f"Error deleting {file_path.name}: {str(e)}")
                    logger.warning(f"Error deleting {file_path.name}: {str(e)}")
            
            stats['deleted'] = deleted_count
            stats['failed'] = failed_count
            stats['freed_bytes'] = freed_bytes
            stats['freed_mb'] = freed_bytes / (1024 * 1024)
            stats['total_files'] = file_count
            
            if deleted_count > 0:
                logger.info(
                    f"{folder_name}: Deleted {deleted_count}/{file_count} files, "
                    f"freed {stats['freed_mb']:.2f} MB"
                )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error cleaning folder {folder_path}: {str(e)}", exc_info=True)
            stats['errors'].append(f"Folder processing error: {str(e)}")
            return stats
    
    @staticmethod
    def get_folder_sizes():
        """Get detailed size information for all monitored folders"""
        try:
            if current_app:
                folders = {
                    'uploads': current_app.config.get('UPLOAD_FOLDER', 
                        os.path.join(os.getcwd(), 'uploads')),
                    'reports': current_app.config.get('REPORT_FOLDER',
                        os.path.join(os.getcwd(), 'reports')),
                    'logs': current_app.config.get('LOGS_FOLDER',
                        os.path.join(os.getcwd(), 'logs'))
                }
            else:
                folders = {
                    'uploads': os.path.join(os.getcwd(), 'uploads'),
                    'reports': os.path.join(os.getcwd(), 'reports'),
                    'logs': os.path.join(os.getcwd(), 'logs')
                }
            
            folder_stats = {}
            total_size_mb = 0
            total_files = 0
            
            for folder_name, folder_path in folders.items():
                stats = FileCleanupService._analyze_folder(folder_path, folder_name)
                folder_stats[folder_name] = stats
                total_size_mb += stats.get('size_mb', 0)
                total_files += stats.get('file_count', 0)
            
            return {
                'success': True,
                'folders': folder_stats,
                'total_size_mb': round(total_size_mb, 2),
                'total_files': total_files,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting folder sizes: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'folders': {},
                'total_size_mb': 0,
                'total_files': 0
            }
    
    @staticmethod
    def _analyze_folder(folder_path, folder_name=""):
        """Analyze a single folder for size and file count"""
        stats = {
            'path': folder_path,
            'exists': os.path.exists(folder_path),
            'size_bytes': 0,
            'size_mb': 0,
            'file_count': 0,
            'oldest_file': None,
            'newest_file': None,
            'oldest_date': None,
            'newest_date': None
        }
        
        if not stats['exists']:
            return stats
        
        try:
            folder_path_obj = Path(folder_path)
            oldest_time = float('inf')
            newest_time = 0
            
            # Walk through all files
            for file_path in folder_path_obj.rglob('*'):
                if file_path.is_file():
                    try:
                        file_size = file_path.stat().st_size
                        file_mtime = file_path.stat().st_mtime
                        
                        stats['size_bytes'] += file_size
                        stats['file_count'] += 1
                        
                        # Track oldest and newest files
                        if file_mtime < oldest_time:
                            oldest_time = file_mtime
                            stats['oldest_file'] = file_path.name
                            stats['oldest_date'] = datetime.fromtimestamp(file_mtime).isoformat()
                        
                        if file_mtime > newest_time:
                            newest_time = file_mtime
                            stats['newest_file'] = file_path.name
                            stats['newest_date'] = datetime.fromtimestamp(file_mtime).isoformat()
                            
                    except (OSError, PermissionError) as e:
                        logger.debug(f"Could not stat file {file_path}: {str(e)}")
                        continue
            
            # Convert bytes to MB
            stats['size_mb'] = stats['size_bytes'] / (1024 * 1024)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error analyzing folder {folder_path}: {str(e)}")
            stats['error'] = str(e)
            return stats
    
    @staticmethod
    def check_storage_limits():
        """Check if storage is approaching configured limits"""
        if not current_app:
            return {'success': False, 'error': 'No app context'}
        
        try:
            limits = {
                'uploads': current_app.config.get('MAX_UPLOAD_FOLDER_SIZE_MB', 1000),
                'reports': current_app.config.get('MAX_REPORT_FOLDER_SIZE_MB', 500)
            }
            
            folder_sizes = FileCleanupService.get_folder_sizes()
            
            if not folder_sizes.get('success'):
                return folder_sizes
            
            warnings = []
            exceeded = []
            
            for folder_name, limit_mb in limits.items():
                if folder_name in folder_sizes['folders']:
                    folder_size_mb = folder_sizes['folders'][folder_name].get('size_mb', 0)
                    
                    # Check if exceeded limit
                    if folder_size_mb > limit_mb:
                        exceeded.append({
                            'folder': folder_name,
                            'current_mb': round(folder_size_mb, 2),
                            'limit_mb': limit_mb,
                            'exceeded_by_mb': round(folder_size_mb - limit_mb, 2)
                        })
                    # Check if approaching limit (80% full)
                    elif folder_size_mb > (limit_mb * 0.8):
                        warnings.append({
                            'folder': folder_name,
                            'current_mb': round(folder_size_mb, 2),
                            'limit_mb': limit_mb,
                            'percent_full': round((folder_size_mb / limit_mb) * 100, 1)
                        })
            
            return {
                'success': True,
                'limits': limits,
                'current_sizes': folder_sizes['folders'],
                'total_size_mb': folder_sizes['total_size_mb'],
                'warnings': warnings,
                'exceeded': exceeded,
                'needs_cleanup': len(exceeded) > 0,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking storage limits: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def emergency_cleanup(keep_days=1):
        """Emergency cleanup - keep only last day's files"""
        logger.warning(f"Performing emergency cleanup - keeping only {keep_days} day(s) of files")
        
        result = FileCleanupService.cleanup_old_files(days_to_keep=keep_days)
        
        if result.get('success'):
            logger.warning(
                f"Emergency cleanup completed: {result['deleted_count']} files deleted, "
                f"{result['freed_space_mb']:.2f} MB freed"
            )
        else:
            logger.error(f"Emergency cleanup failed: {result.get('error', 'Unknown error')}")
        
        return result