# app/services/scheduler.py
import time
import threading
from datetime import datetime, timedelta
from flask import current_app
from app.services.file_cleanup import FileCleanupService
import logging

logger = logging.getLogger(__name__)

class CleanupScheduler:
    """Background scheduler for automatic file cleanup"""
    
    def __init__(self, app=None):
        self.app = app
        self.thread = None
        self.running = False
        self.last_run_date = None  # Track last run date
        self.shutdown_event = threading.Event()
        
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        
        # Get configuration
        self.enable_cleanup = app.config.get('ENABLE_AUTO_CLEANUP', True)
        self.cleanup_hour = self._parse_cleanup_time(app.config.get('CLEANUP_TIME', '02:00'))
        self.days_to_keep = app.config.get('AUTO_CLEANUP_DAYS', 3)
        
        if self.enable_cleanup:
            self.start()
    
    def _parse_cleanup_time(self, time_str):
        """Parse cleanup time from config string (HH:MM)"""
        try:
            hour, minute = map(int, time_str.split(':'))
            return (hour, minute)
        except (ValueError, AttributeError):
            logger.warning(f"Invalid CLEANUP_TIME format: {time_str}. Using default 02:00")
            return (2, 0)  # Default 2:00 AM
    
    def start(self):
        """Start the cleanup scheduler"""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        self.running = True
        self.shutdown_event.clear()
        
        self.thread = threading.Thread(
            target=self._run_scheduler,
            name="CleanupScheduler",
            daemon=True
        )
        self.thread.start()
        
        if self.app:
            logger.info(
                f"File cleanup scheduler started. Will run daily at "
                f"{self.cleanup_hour[0]:02d}:{self.cleanup_hour[1]:02d}"
            )
    
    def stop(self):
        """Stop the cleanup scheduler gracefully"""
        if not self.running:
            return
        
        logger.info("Stopping cleanup scheduler...")
        self.running = False
        self.shutdown_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=10)
            if self.thread.is_alive():
                logger.warning("Scheduler thread did not stop gracefully")
            else:
                logger.info("Scheduler stopped successfully")
    
    def _run_scheduler(self):
        """Run the scheduler in background thread"""
        logger.info("Scheduler thread started")
        
        while self.running and not self.shutdown_event.is_set():
            try:
                current_time = datetime.now()
                
                # Check if we should run cleanup today
                should_run = self._should_run_cleanup(current_time)
                
                if should_run:
                    logger.info(f"Running scheduled cleanup at {current_time}")
                    self._cleanup_task()
                    self.last_run_date = current_time.date()  # Mark as run today
                    
                    # Sleep for a while after running to avoid multiple runs
                    time.sleep(300)  # 5 minutes
                else:
                    # Calculate sleep time until next check (30 seconds)
                    time.sleep(30)
                    
            except Exception as e:
                logger.error(f"Scheduler error: {str(e)}", exc_info=True)
                
                # Exponential backoff on error
                sleep_time = min(300, 30 * (2 ** min(5, self._error_count)))  # Max 5 minutes
                time.sleep(sleep_time)
    
    def _should_run_cleanup(self, current_time):
        """Determine if cleanup should run now"""
        # Don't run if already ran today
        if self.last_run_date == current_time.date():
            return False
        
        # Check if current time is within the scheduled window
        target_hour, target_minute = self.cleanup_hour
        
        # Create a 5-minute window around the target time
        target_time = current_time.replace(
            hour=target_hour, 
            minute=target_minute, 
            second=0, 
            microsecond=0
        )
        
        time_window_start = target_time - timedelta(minutes=2)
        time_window_end = target_time + timedelta(minutes=2)
        
        return time_window_start <= current_time <= time_window_end
    
    def _cleanup_task(self):
        """Task to cleanup old files"""
        if not self.app:
            logger.error("No app context available for cleanup task")
            return
            
        try:
            # Create app context
            with self.app.app_context():
                logger.info(f"Starting automated cleanup (keeping {self.days_to_keep} days)")
                
                result = FileCleanupService.cleanup_old_files(
                    days_to_keep=self.days_to_keep
                )
                
                if result.get('success'):
                    deleted_count = result.get('deleted_count', 0)
                    logger.info(
                        f"Auto-cleanup completed: Removed {deleted_count} files, "
                        f"freed {result.get('freed_space_mb', 0):.2f} MB"
                    )
                    
                    # Log individual folders if available
                    if 'folder_stats' in result:
                        for folder, stats in result['folder_stats'].items():
                            if stats['deleted'] > 0:
                                logger.info(
                                    f"  {folder}: {stats['deleted']} files deleted "
                                    f"({stats['freed_mb']:.2f} MB freed)"
                                )
                else:
                    logger.error(
                        f"Auto-cleanup failed: {result.get('error', 'Unknown error')}"
                    )
                    
        except Exception as e:
            logger.error(f"Error in cleanup task: {str(e)}", exc_info=True)
    
    def run_cleanup_now(self):
        """Manually trigger cleanup immediately (for testing/admin)"""
        if not self.app:
            return {'success': False, 'error': 'No app context'}
        
        try:
            logger.info("Manual cleanup triggered")
            result = self._cleanup_task()
            
            # Update last run date to prevent immediate re-run
            self.last_run_date = datetime.now().date()
            
            return result
        except Exception as e:
            logger.error(f"Manual cleanup failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_status(self):
        """Get scheduler status for monitoring"""
        return {
            'running': self.running,
            'last_run': self.last_run_date.isoformat() if self.last_run_date else None,
            'next_scheduled': self._get_next_scheduled_time().isoformat() if self.running else None,
            'thread_alive': self.thread.is_alive() if self.thread else False,
            'config': {
                'enabled': self.enable_cleanup,
                'cleanup_time': f"{self.cleanup_hour[0]:02d}:{self.cleanup_hour[1]:02d}",
                'days_to_keep': self.days_to_keep
            }
        }
    
    def _get_next_scheduled_time(self):
        """Calculate next scheduled cleanup time"""
        now = datetime.now()
        today_cleanup = now.replace(
            hour=self.cleanup_hour[0],
            minute=self.cleanup_hour[1],
            second=0,
            microsecond=0
        )
        
        if now < today_cleanup:
            return today_cleanup
        else:
            # Schedule for tomorrow
            return today_cleanup + timedelta(days=1)

# Singleton instance
cleanup_scheduler = CleanupScheduler()