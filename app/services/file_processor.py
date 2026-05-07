# app/services/file_processor.py
"""
File upload processing.

"""
import os
from datetime import datetime

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
GOOGLE_SHEETS_TMP_PREFIX = 'gs_tmp_'


class FileProcessor:
    """Utility class for processing file uploads."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def process_upload(request) -> str:
        """Dispatch to the correct handler based on form input method.
        """
        use_sheets = (
            request.form.get('input_method') == 'sheets'
            or request.form.get('use_google_sheets') == 'on'
        )

        if use_sheets:
            return FileProcessor._process_google_sheets(request)
        return FileProcessor._process_file_upload(request)

    @staticmethod
    def cleanup_file(filepath: str) -> None:
        """Delete *filepath* if it is a Google Sheets temp file.
        """
        if not filepath:
            return

        basename = os.path.basename(filepath)
        is_temp  = basename.startswith(GOOGLE_SHEETS_TMP_PREFIX)

        if is_temp and os.path.exists(filepath):
            try:
                os.remove(filepath)
                current_app.logger.info(f"FileProcessor: removed temp file {filepath}")
            except Exception as e:
                current_app.logger.warning(
                    f"FileProcessor: could not remove temp file {filepath}: {e}"
                )

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    @staticmethod
    def _process_file_upload(request) -> str:
        """Save an uploaded Excel / CSV file and return its path."""
        if 'file' not in request.files:
            raise ValueError("No file was included in the request.")

        file = request.files['file']
        if not file or file.filename == '':
            raise ValueError("No file was selected.")

        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Invalid file type '.{ext}'. "
                f"Please upload one of: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
            )

        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        current_app.logger.info(f"FileProcessor: saved upload to {filepath}")
        return filepath

    @staticmethod
    def _process_google_sheets(request) -> str:
        """Fetch a Google Sheet and persist it as a temp .xlsx file.
        """
        from app.services.google_sheets_service import GoogleSheetsService
        from app.models.setting import Setting

        sheet_url = request.form.get('sheet_url', '').strip()
        year      = request.form.get('year', type=int)

        if not sheet_url:
            raise ValueError("A Google Sheets URL is required.")
        if not year:
            raise ValueError("Year is required when importing from Google Sheets.")

        # Persist so the settings page stays in sync
        Setting.set_value('google_sheets_url', sheet_url)

        service = GoogleSheetsService()
        service.init_app(current_app._get_current_object())
        excel_data = service.get_sheet_as_excel(sheet_url, sheet_name=str(year))

        if excel_data is None:
            raise ValueError(
                "Could not fetch data from Google Sheets. "
                "Please check the URL and that the service account has access."
            )

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename  = f"{GOOGLE_SHEETS_TMP_PREFIX}{year}_{timestamp}.xlsx"
        filepath  = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        with open(filepath, 'wb') as fh:
            fh.write(excel_data.getvalue())

        current_app.logger.info(
            f"FileProcessor: saved Google Sheets data to {filepath}"
        )
        return filepath