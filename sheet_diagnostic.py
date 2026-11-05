# sheet_diagnostic.py
"""
Standalone diagnostic script for Google Sheets connectivity.

Usage:
    python sheet_diagnostic.py [SHEET_URL]

If SHEET_URL is omitted the script reads it from the
DIAGNOSTIC_SHEET_URL environment variable or prompts for it.
"""
import os
import sys

# Make sure the project root is on sys.path when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask


def build_app() -> Flask:
    """Create a minimal Flask app with credentials configured."""
    app = Flask(__name__)

    # Credentials — prefer env vars so this script works in CI too
    app.config['GOOGLE_CREDENTIALS_PATH'] = os.environ.get(
        'GOOGLE_CREDENTIALS_PATH',
        os.path.join('credentials', 'service_account.json'),
    )
    app.config['GOOGLE_CREDENTIALS_JSON'] = os.environ.get(
        'GOOGLE_CREDENTIALS_JSON', ''
    )
    return app


def diagnose(sheet_url: str) -> None:
    """Run full diagnostics against *sheet_url* and print results."""
    from app.services.google_sheets_service import google_sheets_service

    app = build_app()

    with app.app_context():
        google_sheets_service.init_app(app)

        print('=' * 70)
        print('GOOGLE SHEETS DIAGNOSTIC')
        print('=' * 70)
        print(f'URL: {sheet_url}\n')

        # ── Step 1: connection test ────────────────────────────────────
        print('Step 1 — Authentication & connection')
        result = google_sheets_service.test_connection(sheet_url)

        if not result.get('success'):
            print(f"  ✗ {result.get('error', 'Unknown error')}")
            print('\nDiagnostic aborted — fix authentication before continuing.')
            return

        print(f"  ✓ Connected to: \"{result['sheet_title']}\"")
        worksheets = result.get('worksheet_names', [])
        print(f"  ✓ Worksheets ({len(worksheets)}): {worksheets}\n")

        # ── Step 2: per-worksheet inspection ──────────────────────────
        print('Step 2 — Worksheet inspection')
        for sheet_name in worksheets:
            print(f"\n  Sheet: {sheet_name!r}")
            df = google_sheets_service.get_sheet_data(sheet_url, sheet_name)

            if df is None:
                print('    ✗ Failed to fetch data')
                continue

            if df.empty:
                print('    ⚠  Sheet is empty')
                continue

            print(f'    Rows: {len(df)}, Columns: {len(df.columns)}')
            print(f'    Headers: {list(df.columns)}')

            # Warn about blank column names
            blank_cols = [c for c in df.columns if str(c).strip() == '']
            if blank_cols:
                print(f'    ⚠  {len(blank_cols)} blank column name(s) detected')

            # Show first 3 data rows
            print('    First 3 rows:')
            for _, row in df.head(3).iterrows():
                print(f'      {dict(row)}')

        print('\n' + '=' * 70)
        print('Diagnostic complete.')
        print('=' * 70)


def main() -> None:
    sheet_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get('DIAGNOSTIC_SHEET_URL', '').strip()
    )

    if not sheet_url:
        sheet_url = input('Enter the Google Sheets URL to diagnose: ').strip()

    if not sheet_url:
        print('No URL provided — exiting.')
        sys.exit(1)

    diagnose(sheet_url)


if __name__ == '__main__':
    main()