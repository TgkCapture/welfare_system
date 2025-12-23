# app/services/file_cleanup.py
import os
import shutil
from datetime import datetime, timedelta
from flask import current_app
import logging

class FileCleanupService:
    """Service for cleaning up old files"""
    
    @staticmethod
    def cleanup_old_files(days_to_keep=7):
        """
        Clean up files older than specified days
        
        Args:
            days_to_keep: Number of days to keep files (default: 7)
        """
        if current_app:
            logger = current_app.logger
        else:
            logger = logging.getLogger(__name__)
            
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_files = []
        
        try:
            # Get folder paths
            upload_folder = os.path.join(os.getcwd(), 'uploads')
            report_folder = os.path.join(os.getcwd(), 'reports')
            
            # Clean up upload folder
            if os.path.exists(upload_folder):
                deleted_files.extend(
                    FileCleanupService._cleanup_folder(upload_folder, cutoff_date)
                )
            
            # Clean up report folder
            if os.path.exists(report_folder):
                deleted_files.extend(
                    FileCleanupService._cleanup_folder(report_folder, cutoff_date)
                )
            
            logger.info(f"Cleaned up {len(deleted_files)} files older than {days_to_keep} days")
            
            return {
                'success': True,
                'deleted_count': len(deleted_files),
                'deleted_files': deleted_files
            }
            
        except Exception as e:
            logger.error(f"Error during file cleanup: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def _cleanup_folder(folder_path, cutoff_date):
        """Clean up files in a specific folder"""
        deleted_files = []
        
        if not os.path.exists(folder_path):
            return deleted_files
        
        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            
            # Skip directories
            if not os.path.isfile(filepath):
                continue
            
            # Get file modification time
            try:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                
                # Delete if older than cutoff date
                if file_mtime < cutoff_date:
                    os.remove(filepath)
                    deleted_files.append(filename)
                    
            except Exception as e:
                logger = current_app.logger if current_app else logging.getLogger(__name__)
                logger.warning(f"Could not delete file {filename}: {str(e)}")
                continue
        
        return deleted_files
    
    @staticmethod
    def get_folder_sizes():
        """Get the size of upload and report folders"""
        folder_sizes = {
            'upload_folder_mb': 0,
            'report_folder_mb': 0,
            'total_mb': 0,
            'upload_folder_count': 0,
            'report_folder_count': 0
        }
        
        # Get upload folder size
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        if os.path.exists(upload_folder):
            upload_size = FileCleanupService._get_folder_size(upload_folder)
            folder_sizes['upload_folder_mb'] = round(upload_size / (1024 * 1024), 2)
            folder_sizes['upload_folder_count'] = FileCleanupService._get_file_count(upload_folder)
        
        # Get report folder size
        report_folder = os.path.join(os.getcwd(), 'reports')
        if os.path.exists(report_folder):
            report_size = FileCleanupService._get_folder_size(report_folder)
            folder_sizes['report_folder_mb'] = round(report_size / (1024 * 1024), 2)
            folder_sizes['report_folder_count'] = FileCleanupService._get_file_count(report_folder)
        
        # Get total
        folder_sizes['total_mb'] = folder_sizes['upload_folder_mb'] + folder_sizes['report_folder_mb']
        
        return folder_sizes
    
    @staticmethod
    def _get_folder_size(folder_path):
        """Calculate total size of folder in bytes"""
        if not os.path.exists(folder_path):
            return 0
        
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.isfile(filepath):
                    total_size += os.path.getsize(filepath)
        
        return total_size
    
    @staticmethod
    def _get_file_count(folder_path):
        """Count files in folder"""
        if not os.path.exists(folder_path):
            return 0
        
        count = 0
        for filename in os.listdir(folder_path):
            filepath = os.path.join(folder_path, filename)
            if os.path.isfile(filepath):
                count += 1
        
        return count