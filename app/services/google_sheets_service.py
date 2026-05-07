# app/services/google_sheets_service.py
"""
Google Sheets integration service.

Authenticates via a service-account JSON (env var or file path),
fetches sheet data into a pandas DataFrame, and can export it as
an in-memory Excel file for consumption by ExcelParser.

Thread-safety note: the in-process cache is protected by a lock so
the service is safe to use from the scheduler thread and request
threads simultaneously.
"""
import json
import logging
import re
import threading
import time
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import gspread
import pandas as pd
from flask import current_app
from google.api_core.exceptions import NotFound, PermissionDenied
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

_SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
]
_SHEET_URL_RE = re.compile(
    r'^https://docs\.google\.com/spreadsheets/d/[a-zA-Z0-9\-_]+'
)


class GoogleSheetsService:
    """Singleton service for Google Sheets access with caching."""

    _instance      = None
    _instance_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    def __new__(cls):
        with cls._instance_lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._cache         = {}
                inst._cache_lock    = threading.Lock()
                inst._cache_ttl     = 300          # seconds
                inst._sheet_hashes  = {}
                inst._creds_path    = None
                inst._initialized   = False
                cls._instance       = inst
        return cls._instance

    def init_app(self, app) -> None:
        """Bind service to a Flask app — call once from the app factory."""
        self._creds_path  = app.config.get('GOOGLE_CREDENTIALS_PATH')
        self._creds_json  = app.config.get('GOOGLE_CREDENTIALS_JSON')
        self._cache_ttl   = app.config.get('SHEETS_CACHE_TTL', 300)
        self._initialized = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_sheet_data(
        self,
        sheet_url: str,
        sheet_name: Optional[str] = None,
        force_refresh: bool = False,
    ) -> Optional[pd.DataFrame]:
        """Fetch a worksheet as a DataFrame.

        Returns None on any error so callers can raise ValueError with
        a user-friendly message.
        """
        if not self._validate_url(sheet_url):
            logger.error(f"Invalid Google Sheets URL: {sheet_url}")
            return None

        cache_key = f"{sheet_url}:{sheet_name}"

        if not force_refresh:
            cached = self._get_cached(cache_key)
            if cached is not None:
                return cached

        client = self._get_client()
        if client is None:
            return None

        try:
            spreadsheet = client.open_by_url(sheet_url)
            worksheet   = self._resolve_worksheet(spreadsheet, sheet_name)
            if worksheet is None:
                return None

            raw = worksheet.get_all_values()
            if not raw or len(raw) < 2:
                logger.warning(f"Worksheet '{worksheet.title}' is empty or header-only")
                return pd.DataFrame()

            headers = [str(h).strip() for h in raw[0]]
            df      = pd.DataFrame(raw[1:], columns=headers)
            df      = self._clean_dataframe(df)

            self._set_cached(cache_key, df)
            logger.info(
                f"Fetched {len(df)} rows from "
                f"'{worksheet.title}' in '{spreadsheet.title}'"
            )
            return df

        except PermissionDenied:
            logger.error(f"Permission denied accessing sheet: {sheet_url}")
        except NotFound:
            logger.error(f"Spreadsheet not found: {sheet_url}")
        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching sheet: {e}", exc_info=True)

        return None

    def get_sheet_as_excel(
        self,
        sheet_url: str,
        sheet_name: Optional[str] = None,
    ) -> Optional[BytesIO]:
        """Return the sheet data as an in-memory Excel (.xlsx) file."""
        df = self.get_sheet_data(sheet_url, sheet_name)
        if df is None:
            return None

        if df.empty:
            df = pd.DataFrame({'Message': ['No data found in Google Sheet']})

        output     = BytesIO()
        safe_title = (sheet_name or 'Sheet1')[:31]   # Excel tab name limit

        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name=safe_title)

            wb  = writer.book
            ws  = writer.sheets[safe_title]

            header_fmt = wb.add_format({
                'bold': True, 'text_wrap': True,
                'fg_color': '#D7E4BC', 'border': 1,
            })
            for col_idx, col_name in enumerate(df.columns):
                ws.write(0, col_idx, col_name, header_fmt)
                col_width = max(
                    df[col_name].astype(str).str.len().max() if not df.empty else 0,
                    len(str(col_name)),
                )
                ws.set_column(col_idx, col_idx, min(col_width + 2, 50))

            # Metadata sheet
            meta = pd.DataFrame({
                'Property': ['Source URL', 'Export Time', 'Rows', 'Columns', 'Sheet'],
                'Value':    [
                    sheet_url,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    len(df), len(df.columns),
                    sheet_name or 'Default',
                ],
            })
            meta.to_excel(writer, sheet_name='Metadata', index=False)

        output.seek(0)
        logger.info(f"Exported sheet to Excel: {len(df)} rows")
        return output

    def test_connection(self, sheet_url: Optional[str] = None) -> Dict[str, Any]:
        """Verify credentials and optionally access a specific sheet."""
        client = self._get_client()
        if client is None:
            return {'success': False, 'error': 'Authentication failed.'}

        if not sheet_url:
            return {'success': True, 'message': 'Authenticated successfully.'}

        if not self._validate_url(sheet_url):
            return {'success': False, 'error': 'Invalid Google Sheets URL.'}

        try:
            ss  = client.open_by_url(sheet_url)
            wss = ss.worksheets()
            return {
                'success':          True,
                'sheet_title':      ss.title,
                'worksheet_count':  len(wss),
                'worksheet_names':  [w.title for w in wss],
                'message':          f'Connected to "{ss.title}".',
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def clear_cache(
        self,
        sheet_url: Optional[str] = None,
        sheet_name: Optional[str] = None,
    ) -> None:
        """Invalidate cache entries — all, by URL, or by URL+sheet."""
        with self._cache_lock:
            if sheet_url and sheet_name:
                key = f"{sheet_url}:{sheet_name}"
                self._cache.pop(key, None)
                self._sheet_hashes.pop(key, None)
            elif sheet_url:
                for k in list(self._cache):
                    if k.startswith(sheet_url):
                        del self._cache[k]
                        self._sheet_hashes.pop(k, None)
            else:
                self._cache.clear()
                self._sheet_hashes.clear()
            logger.info("Google Sheets cache cleared")

    # ------------------------------------------------------------------
    # Private — auth
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(gspread.exceptions.APIError),
        reraise=False,
    )
    def _get_client(self) -> Optional[gspread.Client]:
        """Return an authenticated gspread client, or None on failure."""
        try:
            creds = None

            # 1. Try JSON blob from environment variable
            json_blob = getattr(self, '_creds_json', None) or \
                        current_app.config.get('GOOGLE_CREDENTIALS_JSON')
            if json_blob:
                try:
                    creds = Credentials.from_service_account_info(
                        json.loads(json_blob), scopes=_SCOPES
                    )
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"Invalid GOOGLE_CREDENTIALS_JSON: {e}")

            # 2. Fall back to credentials file
            if not creds:
                path = self._creds_path or \
                       current_app.config.get('GOOGLE_CREDENTIALS_PATH')
                if path and __import__('os').path.exists(path):
                    creds = Credentials.from_service_account_file(
                        path, scopes=_SCOPES
                    )

            if not creds:
                logger.error("No Google credentials configured.")
                return None

            return gspread.authorize(creds)

        except GoogleAuthError as e:
            logger.error(f"Google auth error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected auth error: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Private — worksheet resolution
    # ------------------------------------------------------------------

    def _resolve_worksheet(
        self,
        spreadsheet: gspread.Spreadsheet,
        sheet_name: Optional[str],
    ) -> Optional[gspread.Worksheet]:
        """Return the best matching worksheet, or None."""
        worksheets = spreadsheet.worksheets()

        if sheet_name:
            # Exact match
            for ws in worksheets:
                if ws.title == sheet_name:
                    return ws
            # Case-insensitive partial match
            for ws in worksheets:
                if sheet_name.lower() in ws.title.lower():
                    logger.info(
                        f"Using worksheet '{ws.title}' "
                        f"(fuzzy match for '{sheet_name}')"
                    )
                    return ws

        # Fall back to first sheet
        if worksheets:
            logger.info(f"Using first worksheet: '{worksheets[0].title}'")
            return worksheets[0]

        logger.error("No worksheets found in spreadsheet.")
        return None

    # ------------------------------------------------------------------
    # Private — data cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Strip empty rows/cols and coerce numeric columns."""
        df = df.dropna(how='all').reset_index(drop=True)
        if df.empty:
            return df

        # Drop fully-unnamed columns (artefacts of merged cells)
        df = df.loc[:, ~df.columns.str.fullmatch(r'Unnamed.*', na=False)]

        for col in df.columns:
            if df[col].isna().all():
                continue
            # Only coerce if the column looks numeric (>50% convertible)
            converted = pd.to_numeric(df[col], errors='coerce')
            if converted.notna().mean() > 0.5:
                df[col] = converted

        return df

    # ------------------------------------------------------------------
    # Private — cache (thread-safe)
    # ------------------------------------------------------------------

    def _get_cached(self, key: str) -> Optional[pd.DataFrame]:
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry and (time.monotonic() - entry['ts']) < self._cache_ttl:
                return entry['df']
        return None

    def _set_cached(self, key: str, df: pd.DataFrame) -> None:
        with self._cache_lock:
            self._cache[key] = {'df': df, 'ts': time.monotonic()}

    # ------------------------------------------------------------------
    # Private — URL validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_url(url: str) -> bool:
        return bool(_SHEET_URL_RE.match(url or ''))


# Module-level singleton
google_sheets_service = GoogleSheetsService()