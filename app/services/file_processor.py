# app/services/file_processor.py
"""
File upload processing.

Uploaded workbooks and Google Sheets exports are written to the current
group's upload folder under a unique name, and removed once the report
has been generated (they hold member data and nothing reads them later).
"""
import os
import uuid
from datetime import datetime

from flask import current_app
from werkzeug.utils import secure_filename

from app.services.group_storage import group_folder


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
        """Delete a processed upload from the group's upload folder."""
        if not filepath or not os.path.exists(filepath):
            return
        try:
            os.remove(filepath)
            current_app.logger.info(f"FileProcessor: removed processed upload {filepath}")
        except Exception as e:
            current_app.logger.warning(
                f"FileProcessor: could not remove upload {filepath}: {e}"
            )

    # ------------------------------------------------------------------
    # Private handlers
    # ------------------------------------------------------------------

    @staticmethod
    def _unique_path(name: str) -> str:
        """A path in the group's upload folder that no other upload can share."""
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(group_folder('uploads'), f"{stamp}_{uuid.uuid4().hex[:8]}_{name}")

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

        filepath = FileProcessor._unique_path(filename)
        file.save(filepath)

        current_app.logger.info(f"FileProcessor: saved upload to {filepath}")
        return filepath

    @staticmethod
    def _process_google_sheets(request) -> str:
        """Fetch a Google Sheet and persist it as a temp .xlsx file.
        """
        from app.extensions import db
        from app.models.tenancy import current_group
        from app.services.google_sheets_service import GoogleSheetsService

        sheet_url = request.form.get('sheet_url', '').strip()
        year      = request.form.get('year', type=int)

        if not sheet_url:
            raise ValueError("A Google Sheets URL is required.")
        if not year:
            raise ValueError("Year is required when importing from Google Sheets.")

        # Remember it as the group's sheet so the settings page stays in sync
        current_group().settings.google_sheet_url = sheet_url
        db.session.commit()

        service = GoogleSheetsService()
        service.init_app(current_app._get_current_object())
        excel_data = service.get_sheet_as_excel(sheet_url, sheet_name=str(year))

        if excel_data is None:
            raise ValueError(
                "Could not fetch data from Google Sheets. "
                "Please check the URL and that the service account has access."
            )

        filepath = FileProcessor._unique_path(f"{GOOGLE_SHEETS_TMP_PREFIX}{year}.xlsx")
        with open(filepath, 'wb') as fh:
            fh.write(excel_data.getvalue())

        current_app.logger.info(
            f"FileProcessor: saved Google Sheets data to {filepath}"
        )
        return filepath
