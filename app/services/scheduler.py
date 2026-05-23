# app/services/scheduler.py
"""
Background cleanup scheduler.

Runs a daemon thread that fires FileCleanupService.cleanup_scheduled()
once per day at the configured time (default 02:00).

Usage in your app factory:

    from app.services.scheduler import cleanup_scheduler
    cleanup_scheduler.init_app(app)
"""
import logging
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class CleanupScheduler:
    """Daemon-thread scheduler for daily file and DB cleanup."""

    def __init__(self, app=None):
        self.app             = app
        self._thread         = None
        self._running        = False
        self._shutdown       = threading.Event()
        self._last_run_date  = None
        self._error_count    = 0       

        # Config — set properly in init_app
        self.enabled         = True
        self.cleanup_hour    = (2, 0)     # (hour, minute)
        self.days_to_keep    = 3

        if app is not None:
            self.init_app(app)

    # ------------------------------------------------------------------
    # Flask app factory integration
    # ------------------------------------------------------------------

    def init_app(self, app) -> None:
        """Bind to a Flask app and start the thread if enabled."""
        self.app          = app
        self.enabled      = app.config.get('ENABLE_AUTO_CLEANUP', True)
        self.cleanup_hour = self._parse_time(app.config.get('CLEANUP_TIME', '02:00'))
        self.days_to_keep = app.config.get('AUTO_CLEANUP_DAYS', 3)

        if self.enabled:
            self.start()

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler thread."""
        if self._running:
            logger.warning("CleanupScheduler: already running, ignoring start()")
            return

        self._running  = True
        self._shutdown.clear()
        self._thread   = threading.Thread(
            target=self._loop,
            name='CleanupScheduler',
            daemon=True,          # dies with the main process automatically
        )
        self._thread.start()
        h, m = self.cleanup_hour
        logger.info(f"CleanupScheduler started — daily at {h:02d}:{m:02d}")

    def stop(self, timeout: int = 10) -> None:
        """Signal the scheduler to stop and wait for the thread to exit."""
        if not self._running:
            return
        logger.info("CleanupScheduler: stopping…")
        self._running = False
        self._shutdown.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("CleanupScheduler: thread did not exit within timeout")
            else:
                logger.info("CleanupScheduler: stopped cleanly")

    # ------------------------------------------------------------------
    # Admin / testing helpers
    # ------------------------------------------------------------------

    def run_now(self) -> dict:
        """Trigger an immediate cleanup and return the result dict."""
        if not self.app:
            return {'success': False, 'error': 'No app context'}
        logger.info("CleanupScheduler: manual run triggered")
        result = self._run_cleanup()
        self._last_run_date = datetime.now().date()
        return result or {}

    def get_status(self) -> dict:
        """Return current scheduler state for monitoring / admin UI."""
        h, m = self.cleanup_hour
        return {
            'running':      self._running,
            'thread_alive': self._thread.is_alive() if self._thread else False,
            'last_run':     self._last_run_date.isoformat() if self._last_run_date else None,
            'next_run':     self._next_run_time().isoformat() if self._running else None,
            'config': {
                'enabled':      self.enabled,
                'cleanup_time': f"{h:02d}:{m:02d}",
                'days_to_keep': self.days_to_keep,
            },
        }

    # ------------------------------------------------------------------
    # Private — scheduler loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        """Main loop: sleep 30 s, check if cleanup is due, run if so."""
        logger.debug("CleanupScheduler: loop entered")
        while self._running and not self._shutdown.is_set():
            try:
                if self._is_due():
                    logger.info(f"CleanupScheduler: running at {datetime.now()}")
                    self._run_cleanup()
                    self._last_run_date = datetime.now().date()
                    self._error_count   = 0
                    # Sleep 5 min after running to avoid double-trigger
                    self._shutdown.wait(timeout=300)
                else:
                    self._shutdown.wait(timeout=30)

            except Exception as e:
                self._error_count += 1
                logger.error(f"CleanupScheduler loop error: {e}", exc_info=True)
                # Exponential back-off, max 5 min
                backoff = min(300, 30 * (2 ** min(self._error_count, 5)))
                self._shutdown.wait(timeout=backoff)

        logger.debug("CleanupScheduler: loop exited")

    def _is_due(self) -> bool:
        """Return True if cleanup should fire right now."""
        now = datetime.now()

        # Already ran today
        if self._last_run_date == now.date():
            return False

        h, m = self.cleanup_hour
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)

        # Fire within a ±2 minute window around the target time
        return (target - timedelta(minutes=2)) <= now <= (target + timedelta(minutes=2))

    def _run_cleanup(self) -> dict | None:
        """Execute cleanup inside an app context. Returns result or None."""
        if not self.app:
            logger.error("CleanupScheduler: no app set, cannot run cleanup")
            return None

        try:
            from app.services.file_cleanup import FileCleanupService
            with self.app.app_context():
                result = FileCleanupService.cleanup_scheduled()
                deleted = result.get('file_cleanup', {}).get('deleted_count', 0)
                archived = result.get('reports_archived', 0)
                logger.info(
                    f"CleanupScheduler: done — "
                    f"{deleted} files deleted, {archived} reports archived"
                )
                return result
        except Exception as e:
            logger.error(f"CleanupScheduler: cleanup task failed: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Private — helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_time(time_str: str) -> tuple:
        """Parse 'HH:MM' → (hour, minute). Falls back to (2, 0) on error."""
        try:
            h, m = map(int, time_str.split(':'))
            if 0 <= h < 24 and 0 <= m < 60:
                return (h, m)
        except (ValueError, AttributeError):
            pass
        logger.warning(
            f"CleanupScheduler: invalid CLEANUP_TIME '{time_str}', using 02:00"
        )
        return (2, 0)

    def _next_run_time(self) -> datetime:
        """Calculate the next scheduled run time."""
        now = datetime.now()
        h, m = self.cleanup_hour
        today_run = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now < today_run:
            return today_run
        return today_run + timedelta(days=1)


# Singleton — import and call init_app(app) in your app factory
cleanup_scheduler = CleanupScheduler()