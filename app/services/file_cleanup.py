# app/services/file_cleanup.py
"""
File cleanup service.

Deletes old files and reports on storage usage, one group at a time.
Contribution history is kept forever; only files expire.

Retention periods:
  uploads  →  UPLOAD_RETENTION_DAYS (uploads are normally deleted at once)
  reports  →  the group's report_retention_days, else REPORT_RETENTION_DAYS
  logs     →  LOG_RETENTION_DAYS (platform-wide)

When a group's report files expire, their report records are archived
(not deleted), so the history and figures stay available.
"""
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from flask import current_app

from app.services.group_storage import (
    group_folder, report_retention_days, root_folder, upload_retention_days,
)

logger = logging.getLogger(__name__)


class FileCleanupService:
    """Static-method service for file lifecycle management."""

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def cleanup_group(group, dry_run: bool = False) -> dict:
        """Delete *group*'s expired files and archive its expired reports."""
        from app.extensions import db
        from app.models.report import GeneratedReport

        report_days = report_retention_days(group)
        folder_stats = {
            'uploads': FileCleanupService._clean_folder(
                group_folder('uploads', group), upload_retention_days(), dry_run=dry_run),
            'reports': FileCleanupService._clean_folder(
                group_folder('reports', group), report_days, dry_run=dry_run),
        }

        cutoff = datetime.utcnow() - timedelta(days=report_days)
        expired = GeneratedReport.for_group(group.id).filter(
            GeneratedReport.generated_at < cutoff,
            GeneratedReport.is_archived.is_(False),
        )
        archived = expired.count()
        if not dry_run and archived:
            for report in expired.all():
                report.is_archived = True
                report.archived_at = datetime.utcnow()
            db.session.commit()

        return FileCleanupService._summary(folder_stats, reports_archived=archived,
                                           retention_days=report_days, dry_run=dry_run)

    @staticmethod
    def cleanup_all(dry_run: bool = False) -> dict:
        """Clean every group, plus logs and files that belong to no group."""
        from app.models.group import Group

        groups = {
            g.slug: FileCleanupService.cleanup_group(g, dry_run=dry_run)
            for g in Group.query.order_by(Group.slug).all()
        }

        default_days = current_app.config.get('REPORT_RETENTION_DAYS', 7)
        platform = FileCleanupService._summary({
            # Only loose files at the top level; group folders were handled above
            'unassigned uploads': FileCleanupService._clean_folder(
                root_folder('uploads'), upload_retention_days(), recursive=False, dry_run=dry_run),
            'unassigned reports': FileCleanupService._clean_folder(
                root_folder('reports'), default_days, recursive=False, dry_run=dry_run),
            'logs': FileCleanupService._clean_folder(
                current_app.config['LOGS_FOLDER'],
                current_app.config.get('LOG_RETENTION_DAYS', 30), dry_run=dry_run),
        }, dry_run=dry_run)

        results = list(groups.values()) + [platform]
        return {
            'success':          True,
            'dry_run':          dry_run,
            'groups':           groups,
            'platform':         platform,
            'deleted_count':    sum(r['deleted_count'] for r in results),
            'freed_space_mb':   round(sum(r['freed_space_mb'] for r in results), 2),
            'reports_archived': sum(r['reports_archived'] for r in results),
        }

    @staticmethod
    def cleanup_scheduled() -> dict:
        """Daily job run by the scheduler."""
        result = FileCleanupService.cleanup_all()
        logger.info(
            f"Scheduled cleanup: {result['deleted_count']} files deleted, "
            f"{result['reports_archived']} reports archived."
        )
        return result

    # ------------------------------------------------------------------
    # Storage usage
    # ------------------------------------------------------------------

    @staticmethod
    def group_storage(group) -> dict:
        """Size and file counts of *group*'s folders."""
        folders = {
            kind: FileCleanupService._analyse_folder(group_folder(kind, group))
            for kind in ('uploads', 'reports')
        }
        return {
            'folders':        folders,
            'total_size_mb':  round(sum(f['size_mb'] for f in folders.values()), 2),
            'total_files':    sum(f['file_count'] for f in folders.values()),
            'retention_days': report_retention_days(group),
        }

    @staticmethod
    def platform_storage() -> dict:
        """Storage per group, plus loose files and logs."""
        from app.models.group import Group

        groups = [
            {'group': g, **FileCleanupService.group_storage(g)}
            for g in Group.query.order_by(Group.name).all()
        ]
        other = {
            'Unassigned uploads': FileCleanupService._analyse_folder(root_folder('uploads'), recursive=False),
            'Unassigned reports': FileCleanupService._analyse_folder(root_folder('reports'), recursive=False),
            'Logs': FileCleanupService._analyse_folder(current_app.config['LOGS_FOLDER']),
        }
        return {
            'groups':        groups,
            'other':         other,
            'total_size_mb': round(sum(g['total_size_mb'] for g in groups)
                                   + sum(f['size_mb'] for f in other.values()), 2),
        }

    @staticmethod
    def get_folder_sizes() -> dict:
        """Return size and file-count stats for the whole of each root folder."""
        folders = {
            'uploads': root_folder('uploads'),
            'reports': root_folder('reports'),
            'logs':    current_app.config['LOGS_FOLDER'],
        }
        stats = {key: FileCleanupService._analyse_folder(path) for key, path in folders.items()}
        return {
            'success':       True,
            'folders':       stats,
            'total_size_mb': round(sum(s['size_mb'] for s in stats.values()), 2),
            'total_files':   sum(s['file_count'] for s in stats.values()),
            'timestamp':     datetime.now().isoformat(),
        }

    @staticmethod
    def check_storage_limits() -> dict:
        """Return warnings / exceeded flags if folders approach their limits."""
        limits = {
            'uploads': current_app.config.get('MAX_UPLOAD_FOLDER_SIZE_MB', 1000),
            'reports': current_app.config.get('MAX_REPORT_FOLDER_SIZE_MB', 500),
        }

        sizes = FileCleanupService.get_folder_sizes()
        warnings = []
        exceeded = []

        for key, limit_mb in limits.items():
            current_mb = sizes['folders'].get(key, {}).get('size_mb', 0.0)
            if current_mb > limit_mb:
                exceeded.append({
                    'folder':         key,
                    'current_mb':     round(current_mb, 2),
                    'limit_mb':       limit_mb,
                    'exceeded_by_mb': round(current_mb - limit_mb, 2),
                })
            elif current_mb > limit_mb * 0.8:
                warnings.append({
                    'folder':       key,
                    'current_mb':   round(current_mb, 2),
                    'limit_mb':     limit_mb,
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summary(folder_stats: dict, reports_archived: int = 0, **extra) -> dict:
        return {
            'success':          True,
            'deleted_count':    sum(s['deleted'] for s in folder_stats.values()),
            'freed_space_mb':   round(sum(s['freed_mb'] for s in folder_stats.values()), 2),
            'reports_archived': reports_archived,
            'folder_stats':     folder_stats,
            **extra,
        }

    @staticmethod
    def _clean_folder(folder_path: str, retention_days: int,
                      recursive: bool = True, dry_run: bool = False) -> dict:
        """Delete files in *folder_path* older than *retention_days*.

        With *dry_run*, count what would be deleted without deleting it.
        """
        stats = {
            'path': folder_path, 'exists': True, 'retention_days': retention_days,
            'deleted': 0, 'failed': 0, 'skipped': 0,
            'freed_mb': 0.0, 'errors': [],
        }

        folder = Path(folder_path)
        if not folder.is_dir():
            stats['exists'] = False
            return stats

        cutoff_ts = time.time() - retention_days * 86400
        for fp in (folder.rglob('*') if recursive else folder.iterdir()):
            if not fp.is_file():
                continue
            try:
                st = fp.stat()
                if st.st_mtime >= cutoff_ts:
                    stats['skipped'] += 1
                    continue
                if not dry_run:
                    fp.unlink()
                stats['deleted']  += 1
                stats['freed_mb'] += st.st_size / (1024 * 1024)
            except PermissionError as e:
                stats['failed'] += 1
                stats['errors'].append(f"Permission denied: {fp.name}")
                logger.warning(f"Permission denied deleting {fp}: {e}")
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"Error deleting {fp.name}: {e}")
                logger.warning(f"Could not delete {fp}: {e}")

        if stats['deleted'] and not dry_run:
            logger.info(f"{folder_path}: deleted {stats['deleted']} files, "
                        f"freed {stats['freed_mb']:.2f} MB")

        stats['freed_mb'] = round(stats['freed_mb'], 2)
        return stats

    @staticmethod
    def _analyse_folder(folder_path: str, recursive: bool = True) -> dict:
        """Return size / count / age stats for a single folder."""
        result = {
            'path':        folder_path,
            'exists':      os.path.isdir(folder_path),
            'size_mb':     0.0,
            'file_count':  0,
            'oldest_date': None,
            'newest_date': None,
        }
        if not result['exists']:
            return result

        folder = Path(folder_path)
        mtimes, total_bytes = [], 0
        for fp in (folder.rglob('*') if recursive else folder.iterdir()):
            try:
                if fp.is_file():
                    st = fp.stat()
                    total_bytes += st.st_size
                    mtimes.append(st.st_mtime)
            except OSError:
                continue

        result['file_count'] = len(mtimes)
        result['size_mb'] = round(total_bytes / (1024 * 1024), 2)
        if mtimes:
            result['oldest_date'] = datetime.fromtimestamp(min(mtimes)).isoformat()
            result['newest_date'] = datetime.fromtimestamp(max(mtimes)).isoformat()
        return result
