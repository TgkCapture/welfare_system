# app/services/file_cleanup.py
"""
File cleanup service.

Responsible for deleting old files from upload / report / log folders
and reporting on current storage usage.

Per-folder retention periods:
  uploads  →  3 days   (temp files; short life)
  reports  →  config   (REPORT_RETENTION_DAYS, default 7)
  logs     →  30 days  (keep longer for auditing)
"""
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from flask import current_app

logger = logging.getLogger(__name__)

# Per-folder retention in days — (folder_key, config_key, fallback_days)
_FOLDER_RETENTION = [
    ('uploads', 'UPLOAD_RETENTION_DAYS',  3),
    ('reports', 'REPORT_RETENTION_DAYS',  7),
    ('logs',    'LOG_RETENTION_DAYS',     30),
]


def _resolve_folders() -> dict:
    """Return {folder_key: absolute_path} from app config or cwd fallbacks."""
    base = os.getcwd()
    return {
        'uploads': current_app.config.get('UPLOAD_FOLDER',  os.path.join(base, 'uploads')),
        'reports': current_app.config.get('REPORT_FOLDER',  os.path.join(base, 'reports')),
        'logs':    current_app.config.get('LOGS_FOLDER',    os.path.join(base, 'logs')),
    }


class FileCleanupService:
    """Static-method service for file lifecycle management."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def cleanup_old_files(days_to_keep: int = None) -> dict:
        """Delete files older than their per-folder retention period.

        Args:
            days_to_keep: Override for the *reports* folder only.
                          Other folders still use their own defaults.

        Returns:
            Result dict with success flag, counts, freed space and
            per-folder breakdown.
        """
        start = time.monotonic()
        folders = _resolve_folders()

        # Build (key, path, retention_days) triples
        retention_map = {
            key: current_app.config.get(cfg_key, default)
            for key, cfg_key, default in _FOLDER_RETENTION
        }
        if days_to_keep is not None:
            retention_map['reports'] = days_to_keep

        total_deleted   = 0
        total_freed_mb  = 0.0
        folder_stats    = {}

        for key, path in folders.items():
            retention = retention_map[key]
            cutoff    = time.time() - retention * 86400

            if not os.path.exists(path):
                folder_stats[key] = {
                    'exists': False, 'deleted': 0, 'freed_mb': 0.0,
                    'retention_days': retention, 'error': 'Folder does not exist',
                }
                continue

            stats = FileCleanupService._clean_folder(path, cutoff, key)
            stats['retention_days'] = retention
            folder_stats[key]        = stats
            total_deleted           += stats['deleted']
            total_freed_mb          += stats['freed_mb']

        elapsed = round(time.monotonic() - start, 2)
        logger.info(
            f"Cleanup: {total_deleted} files deleted, "
            f"{total_freed_mb:.2f} MB freed in {elapsed}s"
        )

        return {
            'success':       True,
            'deleted_count': total_deleted,
            'freed_space_mb': round(total_freed_mb, 2),
            'folder_stats':  folder_stats,
            'execution_time': elapsed,
        }

    @staticmethod
    def cleanup_scheduled() -> dict:
        """Run cleanup and auto-archive old DB report records.
        """
        from datetime import timedelta
        from app.extensions import db
        from app.models.report import GeneratedReport

        days = current_app.config.get('REPORT_RETENTION_DAYS', 7)
        file_result = FileCleanupService.cleanup_old_files(days)

        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            old = GeneratedReport.query.filter(
                GeneratedReport.generated_at < cutoff,
                GeneratedReport.is_archived == False,
            ).all()

            for r in old:
                r.is_archived = True
                r.archived_at = datetime.utcnow()

            db.session.commit()

            logger.info(
                f"Scheduled cleanup: {file_result.get('deleted_count', 0)} files "
                f"deleted, {len(old)} reports archived."
            )
            return {
                'file_cleanup':      file_result,
                'reports_archived':  len(old),
                'cutoff_date':       cutoff.isoformat(),
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"DB archiving failed during scheduled cleanup: {e}")
            return {'file_cleanup': file_result, 'error': str(e)}

    @staticmethod
    def get_folder_sizes() -> dict:
        """Return size and file-count stats for all monitored folders."""
        folders = _resolve_folders()
        stats   = {}
        total_size_mb = 0.0
        total_files   = 0

        for key, path in folders.items():
            s = FileCleanupService._analyse_folder(path)
            stats[key]     = s
            total_size_mb += s.get('size_mb', 0.0)
            total_files   += s.get('file_count', 0)

        return {
            'success':        True,
            'folders':        stats,
            'total_size_mb':  round(total_size_mb, 2),
            'total_files':    total_files,
            'timestamp':      datetime.now().isoformat(),
        }

    @staticmethod
    def check_storage_limits() -> dict:
        """Return warnings / exceeded flags if folders approach their limits."""
        limits = {
            'uploads': current_app.config.get('MAX_UPLOAD_FOLDER_SIZE_MB', 1000),
            'reports': current_app.config.get('MAX_REPORT_FOLDER_SIZE_MB', 500),
        }

        sizes  = FileCleanupService.get_folder_sizes()
        if not sizes.get('success'):
            return sizes

        warnings = []
        exceeded = []

        for key, limit_mb in limits.items():
            current_mb = sizes['folders'].get(key, {}).get('size_mb', 0.0)
            if current_mb > limit_mb:
                exceeded.append({
                    'folder':        key,
                    'current_mb':    round(current_mb, 2),
                    'limit_mb':      limit_mb,
                    'exceeded_by_mb': round(current_mb - limit_mb, 2),
                })
            elif current_mb > limit_mb * 0.8:
                warnings.append({
                    'folder':      key,
                    'current_mb':  round(current_mb, 2),
                    'limit_mb':    limit_mb,
                    'percent_full': round(current_mb / limit_mb * 100, 1),
                })

        return {
            'success':       True,
            'warnings':      warnings,
            'exceeded':      exceeded,
            'needs_cleanup': bool(exceeded),
            'total_size_mb': sizes['total_size_mb'],
            'timestamp':     datetime.now().isoformat(),
        }

    @staticmethod
    def emergency_cleanup(keep_days: int = 1) -> dict:
        """Keep only the last *keep_days* day(s) of files — use with care."""
        logger.warning(
            f"Emergency cleanup triggered — retaining only {keep_days} day(s)"
        )
        result = FileCleanupService.cleanup_old_files(days_to_keep=keep_days)
        if result.get('success'):
            logger.warning(
                f"Emergency cleanup done: {result['deleted_count']} files, "
                f"{result['freed_space_mb']:.2f} MB freed"
            )
        else:
            logger.error(f"Emergency cleanup failed: {result.get('error')}")
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_folder(folder_path: str, cutoff_ts: float, label: str = '') -> dict:
        """Delete files in *folder_path* older than *cutoff_ts* (epoch seconds).

        Returns a stats dict.
        """
        stats = {
            'path': folder_path, 'exists': True,
            'deleted': 0, 'failed': 0, 'skipped': 0,
            'freed_mb': 0.0, 'errors': [],
        }

        folder = Path(folder_path)
        if not folder.is_dir():
            stats['exists'] = False
            stats['errors'].append(f"Not a directory: {folder_path}")
            return stats

        for fp in folder.rglob('*'):
            if not fp.is_file():
                continue
            try:
                mtime = fp.stat().st_mtime
                if mtime < cutoff_ts:
                    size = fp.stat().st_size
                    fp.unlink()
                    stats['deleted']  += 1
                    stats['freed_mb'] += size / (1024 * 1024)
                    logger.debug(f"Deleted {label}/{fp.name} ({size} bytes)")
                else:
                    stats['skipped'] += 1
            except PermissionError as e:
                stats['failed'] += 1
                stats['errors'].append(f"Permission denied: {fp.name}")
                logger.warning(f"Permission denied deleting {fp}: {e}")
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"Error deleting {fp.name}: {e}")
                logger.warning(f"Could not delete {fp}: {e}")

        if stats['deleted']:
            logger.info(
                f"{label}: deleted {stats['deleted']} files, "
                f"freed {stats['freed_mb']:.2f} MB"
            )

        stats['freed_mb'] = round(stats['freed_mb'], 2)
        return stats

    @staticmethod
    def _analyse_folder(folder_path: str) -> dict:
        """Return size / count / age stats for a single folder."""
        result = {
            'path':        folder_path,
            'exists':      os.path.exists(folder_path),
            'size_mb':     0.0,
            'file_count':  0,
            'oldest_file': None,
            'newest_file': None,
            'oldest_date': None,
            'newest_date': None,
        }

        if not result['exists']:
            return result

        oldest_ts = float('inf')
        newest_ts = 0.0
        total_bytes = 0

        try:
            for fp in Path(folder_path).rglob('*'):
                if not fp.is_file():
                    continue
                try:
                    st = fp.stat()
                    total_bytes += st.st_size
                    result['file_count'] += 1

                    if st.st_mtime < oldest_ts:
                        oldest_ts = st.st_mtime
                        result['oldest_file'] = fp.name
                        result['oldest_date'] = datetime.fromtimestamp(st.st_mtime).isoformat()

                    if st.st_mtime > newest_ts:
                        newest_ts = st.st_mtime
                        result['newest_file'] = fp.name
                        result['newest_date'] = datetime.fromtimestamp(st.st_mtime).isoformat()

                except (OSError, PermissionError):
                    continue

            result['size_mb'] = round(total_bytes / (1024 * 1024), 2)

        except Exception as e:
            logger.error(f"Error analysing folder {folder_path}: {e}")
            result['error'] = str(e)

        return result