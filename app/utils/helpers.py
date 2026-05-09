# app/utils/helpers.py
"""
Utility helpers used across the application.

  FileProcessor         — Google Sheets + direct-upload handling
  ReportDataSerializer  — session-safe serialisation of ExcelParser output
  GoogleSheetsManager   — high-level helpers for the settings / test UI
"""
import base64
import hashlib
import io
import logging
import os
from datetime import datetime

import pandas as pd
from flask import current_app
from werkzeug.utils import secure_filename

from app.models.setting import Setting
from app.services.google_sheets_service import google_sheets_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FileProcessor
# ---------------------------------------------------------------------------

class FileProcessor:
    """Process incoming file uploads — direct or via Google Sheets."""

    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
    GS_PREFIX          = 'gs_tmp_'

    @staticmethod
    def process_upload(request, use_cache: bool = True) -> str:
        """Dispatch to the correct handler and return the saved filepath."""
        use_sheets = (
            request.form.get('input_method') == 'sheets'
            or request.form.get('use_google_sheets') == 'on'
        )
        if use_sheets:
            return FileProcessor._process_google_sheets(request, use_cache)
        return FileProcessor._process_file_upload(request)

    # ------------------------------------------------------------------
    # Google Sheets path
    # ------------------------------------------------------------------

    @staticmethod
    def _process_google_sheets(request, use_cache: bool = True) -> str:
        sheet_url     = request.form.get('sheet_url', '').strip()
        year          = request.form.get('year', type=int)
        month         = request.form.get('month', '')
        sheet_name    = request.form.get('sheet_name', '').strip()
        force_refresh = request.form.get('force_refresh', 'off') == 'on'

        if not sheet_url:
            raise ValueError('Google Sheets URL is required.')
        if not google_sheets_service._validate_url(sheet_url):
            raise ValueError('Invalid Google Sheets URL format.')

        Setting.set_value('google_sheets_url', sheet_url)

        target = sheet_name or (str(year) if year else None)
        df = None

        if target and not force_refresh:
            df = google_sheets_service.get_sheet_data(
                sheet_url, target, force_refresh=False
            )

        if df is None or df.empty:
            logger.info(f"Falling back to sheet search for {sheet_url}")
            df = FileProcessor._search_all_sheets(sheet_url, year, month)

        if df is None or df.empty:
            raise ValueError(
                'No valid data found in the Google Sheet. '
                'Check the URL and that the sheet name matches the year.'
            )

        data_hash = hashlib.md5(
            pd.util.hash_pandas_object(df).values.tobytes()
        ).hexdigest()[:8]
        filename  = (
            f"{FileProcessor.GS_PREFIX}"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{data_hash}.xlsx"
        )
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        FileProcessor._save_df_to_excel(df, filepath, source_url=sheet_url)
        logger.info(f"Saved Google Sheets data to {filepath} ({len(df)} rows)")
        return filepath

    @staticmethod
    def _search_all_sheets(sheet_url: str, year=None, month=None):
        """Try every worksheet heuristically to find one with data."""
        client = google_sheets_service._get_client()
        if not client:
            return None

        try:
            ss         = client.open_by_url(sheet_url)
            worksheets = ss.worksheets()

            patterns = []
            if year and month:
                try:
                    month_int = int(month)
                    patterns += [
                        f"{year}_{month_int:02d}", f"{month_int}_{year}",
                        f"{year}-{month_int:02d}", f"{month_int} {year}",
                    ]
                except (ValueError, TypeError):
                    pass
            if year:
                patterns.append(str(year))
            patterns += ['Data', 'Contributions', 'Members', 'Sheet1']

            for pattern in patterns:
                for ws in worksheets:
                    if pattern.lower() in ws.title.lower():
                        logger.info(f"Matched sheet '{ws.title}' on pattern '{pattern}'")
                        return google_sheets_service.get_sheet_data(sheet_url, ws.title)

            for ws in worksheets:
                try:
                    if len(ws.get_all_values()) > 1:
                        logger.info(f"Using first non-empty sheet: '{ws.title}'")
                        return google_sheets_service.get_sheet_data(sheet_url, ws.title)
                except Exception:
                    continue

        except Exception as e:
            logger.error(f"Error searching all sheets: {e}", exc_info=True)

        return None

    @staticmethod
    def _save_df_to_excel(df: pd.DataFrame, filepath: str, source_url: str = '') -> None:
        """Write df to filepath as .xlsx with a Metadata sheet."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='Data', index=False)

            ws = writer.sheets['Data']
            for i, col in enumerate(df.columns):
                width = max(
                    df[col].astype(str).str.len().max() if not df.empty else 0,
                    len(str(col)),
                )
                ws.set_column(i, i, min(width + 2, 50))

            meta = pd.DataFrame({
                'Property': ['Export Time', 'Rows', 'Columns', 'Source'],
                'Value': [
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    len(df), len(df.columns),
                    source_url or 'Google Sheets',
                ],
            })
            meta.to_excel(writer, sheet_name='Metadata', index=False)

    # ------------------------------------------------------------------
    # Direct upload path
    # ------------------------------------------------------------------

    @staticmethod
    def _process_file_upload(request) -> str:
        if 'file' not in request.files:
            raise ValueError('No file included in the request.')

        file = request.files['file']
        if not file or file.filename == '':
            raise ValueError('No file was selected.')

        filename = secure_filename(file.filename)
        ext      = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        allowed  = current_app.config.get('ALLOWED_EXTENSIONS', FileProcessor.ALLOWED_EXTENSIONS)

        if ext not in allowed:
            raise ValueError(
                f"File type '.{ext}' is not allowed. "
                f"Accepted: {', '.join(sorted(allowed))}."
            )

        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
        if size > max_size:
            raise ValueError(
                f"File is too large ({size / 1_048_576:.1f} MB). "
                f"Maximum: {max_size / 1_048_576:.1f} MB."
            )

        timestamp       = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath        = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        file.save(filepath)

        logger.info(f"Uploaded: {unique_filename} ({size} bytes)")
        return filepath

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    @staticmethod
    def cleanup_file(filepath: str) -> None:
        """Delete filepath only if it is a Google Sheets temp file."""
        if not filepath or not os.path.exists(filepath):
            return
        try:
            if os.path.basename(filepath).startswith(FileProcessor.GS_PREFIX):
                os.remove(filepath)
                logger.info(f"Removed temp file: {filepath}")
        except Exception as e:
            logger.warning(f"Could not remove {filepath}: {e}")


# ---------------------------------------------------------------------------
# ReportDataSerializer
# ---------------------------------------------------------------------------

class ReportDataSerializer:
    """Serialise / deserialise ExcelParser output for Flask session storage."""

    @staticmethod
    def serialize(
        data: dict,
        report_path: str,
        include_raw_data: bool = False,
    ) -> dict:
        """Return a session-safe dict from ExcelParser output."""
        df      = data.get('data')
        records = ReportDataSerializer._df_to_records(df)

        total         = float(data.get('total_contributions', 0))
        paid          = int(data.get('num_contributors', 0))
        missed        = int(data.get('num_missing', 0))
        total_members = paid + missed

        serialized: dict = {
            'report_data': {
                'data':      records,
                'month_col': data.get('month_col'),
                'name_col':  data.get('name_col'),
                'month':     data.get('month'),
                'year':      int(data['year']) if data.get('year') else None,

                'total_contributions': total,
                'num_contributors':    paid,
                'num_missing':         missed,
                'avg_contribution':    round(total / paid, 2) if paid else 0,
                'completion_rate':     round(paid / total_members * 100, 2) if total_members else 0,

                'money_dispensed':    ReportDataSerializer._safe_float(data.get('money_dispensed')),
                'total_book_balance': ReportDataSerializer._safe_float(data.get('total_book_balance')),

                'report_filename': (
                    f"contributions_report"
                    f"_{data.get('year', '')}_{data.get('month', '')}"
                    f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                ),
                'generated_at': datetime.now().isoformat(),
                'data_source':  data.get('data_source', 'upload'),
                'columns':      list(df.columns) if df is not None else [],
                'column_stats': ReportDataSerializer._column_stats(df),
            },
            'report_path': report_path,
            'metadata': {
                'serialized_at': datetime.now().isoformat(),
                'row_count':     len(records),
                'data_hash': (
                    hashlib.md5(str(records).encode()).hexdigest()[:16]
                    if records else None
                ),
            },
        }

        if include_raw_data and df is not None and not df.empty:
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            serialized['raw_data_encoded'] = base64.b64encode(
                buf.getvalue().encode()
            ).decode()

        return serialized

    @staticmethod
    def deserialize(serialized_data: dict):
        """Reconstruct the data dict from a serialised session payload."""
        if not serialized_data:
            return None

        try:
            rd = serialized_data.get('report_data', {})

            if 'raw_data_encoded' in serialized_data:
                csv_str = base64.b64decode(
                    serialized_data['raw_data_encoded']
                ).decode()
                df = pd.read_csv(io.StringIO(csv_str))
            else:
                records = rd.get('data', [])
                df = pd.DataFrame(records) if records else pd.DataFrame()

            return {
                'data':               df,
                'month_col':          rd.get('month_col'),
                'name_col':           rd.get('name_col'),
                'month':              rd.get('month'),
                'year':               rd.get('year'),
                'total_contributions':rd.get('total_contributions', 0),
                'num_contributors':   rd.get('num_contributors', 0),
                'num_missing':        rd.get('num_missing', 0),
                'money_dispensed':    rd.get('money_dispensed'),
                'total_book_balance': rd.get('total_book_balance'),
                'data_source':        rd.get('data_source', 'session'),
                'generated_at':       rd.get('generated_at'),
            }

        except Exception as e:
            logger.error(f"Deserialization error: {e}", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _df_to_records(df) -> list:
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            return []
        clean = df.where(pd.notnull(df), None)
        return [
            {k: (v.item() if hasattr(v, 'item') else v) for k, v in row.items()}
            for row in clean.to_dict('records')
        ]

    @staticmethod
    def _safe_float(value):
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _column_stats(df) -> dict:
        if df is None or df.empty:
            return {}
        stats = {}
        for col in df.columns:
            numeric = pd.to_numeric(df[col], errors='coerce')
            valid   = numeric.dropna()
            if not valid.empty:
                stats[col] = {
                    'min':        float(valid.min()),
                    'max':        float(valid.max()),
                    'mean':       round(float(valid.mean()), 2),
                    'median':     round(float(valid.median()), 2),
                    'std':        round(float(valid.std()), 2),
                    'count':      int(valid.count()),
                    'null_count': int(numeric.isna().sum()),
                }
        return stats


# ---------------------------------------------------------------------------
# GoogleSheetsManager
# ---------------------------------------------------------------------------

class GoogleSheetsManager:
    """High-level helpers for the settings page and diagnostic UI."""

    @staticmethod
    def test_connection(sheet_url: str = None) -> dict:
        """Verify credentials and optionally open a specific sheet."""
        if not sheet_url:
            sheet_url = Setting.get_value('google_sheets_url', '')

        if not sheet_url:
            return {'status': 'error', 'message': 'No Google Sheets URL configured.'}

        result = google_sheets_service.test_connection(sheet_url)

        if result.get('success'):
            return {
                'status':          'success',
                'message':         result.get('message', 'Connected successfully.'),
                'sheet_title':     result.get('sheet_title'),
                'worksheet_count': result.get('worksheet_count'),
                'worksheet_names': result.get('worksheet_names', []),
            }
        return {'status': 'error', 'message': result.get('error', 'Unknown error.')}

    @staticmethod
    def get_sheet_info(sheet_url: str) -> dict:
        """Return worksheet-level metadata for a spreadsheet."""
        client = google_sheets_service._get_client()
        if not client:
            return None

        try:
            ss   = client.open_by_url(sheet_url)
            info = {
                'title':      ss.title,
                'url':        sheet_url,
                'id':         ss.id,
                'worksheets': [],
            }

            for ws in ss.worksheets():
                try:
                    values    = ws.get_all_values()
                    data_rows = max(0, len(values) - 1)
                    info['worksheets'].append({
                        'title':          ws.title,
                        'index':          ws.index,
                        'row_count':      ws.row_count,
                        'col_count':      ws.col_count,
                        'data_rows':      data_rows,
                        'has_data':       data_rows > 0,
                        'sample_headers': values[0] if values else [],
                    })
                except Exception as e:
                    logger.warning(f"Could not inspect worksheet '{ws.title}': {e}")
                    info['worksheets'].append({'title': ws.title, 'error': str(e)})

            return info

        except Exception as e:
            logger.error(f"Error fetching sheet info: {e}", exc_info=True)
            return None