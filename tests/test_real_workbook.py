"""
Optional check against a real group workbook, which is never committed.

Runs only when MZUGOSS_WORKBOOK points at a local copy of MGSS.xlsx:

    MZUGOSS_WORKBOOK=MGSS.xlsx pytest tests/test_real_workbook.py

For every year sheet and month, the parser's total must equal the sheet's
own Total row.
"""
import calendar
import os

import openpyxl
import pytest

from app.services.excel_parser import ExcelParser

WORKBOOK = os.environ.get('MZUGOSS_WORKBOOK')

pytestmark = pytest.mark.skipif(
    not WORKBOOK or not os.path.exists(WORKBOOK),
    reason='MZUGOSS_WORKBOOK not set to an existing file',
)


def _year_sheet_totals(path):
    """Yield (year, month_number, sheet_total) from each year sheet's Total row."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    for ws in wb.worksheets:
        if not (ws.title.isdigit() and len(ws.title) == 4):
            continue
        rows = list(ws.iter_rows(values_only=True))
        header = next(r for r in rows if r and r[0] == 'Name')
        total = next(r for r in rows if r and r[0] == 'Total')
        for month in range(1, 13):
            column = header.index(calendar.month_name[month])
            yield int(ws.title), month, total[column] or 0


def test_parser_matches_sheet_total_row(app):
    checked = 0
    for year, month, sheet_total in _year_sheet_totals(WORKBOOK):
        data = ExcelParser.parse_excel(WORKBOOK, year=year, month=month)
        assert data['total_contributions'] == pytest.approx(sheet_total), (year, month)
        checked += 1
    assert checked > 0
