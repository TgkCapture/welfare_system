# app/services/scheduler.py
import time
import threading
from datetime import datetime
from flask import current_app
from app.services.file_cleanup import FileCleanupService

class CleanupScheduler:
    """Background scheduler for automatic file cleanup"""
    
    def __init__(self, app=None):
        self.app = app
        self.thread = None
        self.running = False
    
    def init_app(self, app):
        self.app = app
        if app.config.get('ENABLE_AUTO_CLEANUP', True):
            self.start()
    
    def start(self):
        """Start the cleanup scheduler"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        
        if self.app:
            self.app.logger.info("File cleanup scheduler started")
    
    def stop(self):
        """Stop the cleanup scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _run_scheduler(self):
        """Run the scheduler in background thread"""
        while self.running:
            try:
                # Check if it's 2:00 AM
                current_time = datetime.now()
                if current_time.hour == 2 and current_time.minute == 0:
                    self._cleanup_task()
                
                # Sleep for 1 minute
                time.sleep(60)
                
            except Exception as e:
                if self.app:
                    self.app.logger.error(f"Scheduler error: {str(e)}")
                time.sleep(60)
    
    def _cleanup_task(self):
        """Task to cleanup old files"""
        if not self.app:
            return
            
        with self.app.app_context():
            try:
                # Keep files for 3 days by default
                result = FileCleanupService.cleanup_old_files(days_to_keep=3)
                
                if result.get('success'):
                    self.app.logger.info(
                        f"Auto-cleanup: Removed {result['deleted_count']} files"
                    )
                else:
                    self.app.logger.error(
                        f"Auto-cleanup failed: {result.get('error')}"
                    )
                    
            except Exception as e:
                self.app.logger.error(f"Auto-cleanup error: {str(e)}")