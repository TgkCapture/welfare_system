# app/services/standard_workbook.py
"""
The standard contribution workbook: its layout, and a reader for it.

Sheets (header in row 1, one record per row):

  Members              Member ID | Name | Phone | Joined (month) | Left (month) | Notes
  Contributions YYYY   Member ID | Name | January … December   (payments only)
  Payouts              Date | Member ID | Name | Purpose | Amount | Approved by | Notes
  Rates                Effective from | Monthly amount
  Summary              Year | Opening balance | Contributions | Payouts | Closing balance | <purposes…>

Columns are found by their header, so their order doesn't matter. Only the
first year's opening balance is typed; every other Summary figure is a
formula, and the app recalculates them all to check the sheet.

The reader never guesses: anything it can't use becomes a warning that
names the sheet, row and column, and the rest of the workbook still loads.
A missing sheet or header is an error.
"""
import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from openpyxl import load_workbook

MONTHS = list(calendar.month_name)[1:]

MEMBERS = 'Members'
PAYOUTS = 'Payouts'
RATES = 'Rates'
SUMMARY = 'Summary'
LISTS = 'Lists'
README = 'Read me'
CONTRIBUTIONS_PREFIX = 'Contributions '
CONTRIBUTIONS_RE = re.compile(r'^\s*contributions\s+(\d{4})\s*$', re.I)

MEMBER_HEADERS = ['Member ID', 'Name', 'Phone', 'Joined (month)', 'Left (month)', 'Notes']
CONTRIBUTION_HEADERS = ['Member ID', 'Name'] + MONTHS
PAYOUT_HEADERS = ['Date', 'Member ID', 'Name', 'Purpose', 'Amount', 'Approved by', 'Notes']
RATE_HEADERS = ['Effective from', 'Monthly amount']
SUMMARY_HEADERS = ['Year', 'Opening balance', 'Contributions', 'Payouts', 'Closing balance']

_MONTH_FORMATS = ('%b %Y', '%B %Y', '%Y-%m', '%m/%Y', '%Y-%m-%d', '%d/%m/%Y')
_DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d %b %Y', '%d %B %Y')


def contributions_sheet(year: int) -> str:
    return f'{CONTRIBUTIONS_PREFIX}{year}'


# ==================== READ RESULT ====================

@dataclass
class SheetMember:
    row: int
    code: str
    name: str
    phone: str = None
    joined: date = None
    left: date = None


@dataclass
class ContributionRow:
    row: int
    code: str
    name: str
    amounts: dict          # month number → float, only for cells with a value


@dataclass
class PayoutRow:
    row: int
    paid_on: date
    code: str
    name: str
    purpose: str
    amount: float
    approved_by: str = None
    notes: str = None


@dataclass
class WorkbookData:
    members: list = field(default_factory=list)
    contributions: dict = field(default_factory=dict)   # year → [ContributionRow]
    payouts: list = field(default_factory=list)
    rates: list = field(default_factory=list)           # [(effective_from, amount)]
    summary: dict = field(default_factory=dict)         # year → {opening, contributions, payouts, closing}
    warnings: list = field(default_factory=list)        # [{'where': ..., 'message': ...}]

    def warn(self, where: str, message: str) -> None:
        self.warnings.append({'where': where, 'message': message})


# ==================== READER ====================

class StandardWorkbook:

    @staticmethod
    def is_standard(path: str) -> bool:
        """True if the file has a Members sheet and at least one Contributions YYYY sheet."""
        try:
            wb = load_workbook(path, read_only=True)
        except Exception:
            return False
        try:
            names = wb.sheetnames
            return MEMBERS in names and any(CONTRIBUTIONS_RE.match(n) for n in names)
        finally:
            wb.close()

    @staticmethod
    def read(path: str) -> WorkbookData:
        # data_only: read the values Excel last calculated, not the formulas
        wb = load_workbook(path, data_only=True)
        data = WorkbookData()

        StandardWorkbook._read_members(wb, data)
        for name in wb.sheetnames:
            match = CONTRIBUTIONS_RE.match(name)
            if match:
                StandardWorkbook._read_contributions(wb[name], int(match.group(1)), data)
        if PAYOUTS in wb.sheetnames:
            StandardWorkbook._read_payouts(wb[PAYOUTS], data)
        if RATES in wb.sheetnames:
            StandardWorkbook._read_rates(wb[RATES], data)
        if SUMMARY in wb.sheetnames:
            StandardWorkbook._read_summary(wb[SUMMARY], data)
        return data

    # ------------------------------------------------------------------
    # Sheets
    # ------------------------------------------------------------------

    @staticmethod
    def _read_members(wb, data):
        ws = wb[MEMBERS]
        cols = _columns(ws, ['Member ID', 'Name'], MEMBER_HEADERS)
        for row, get in _rows(ws, cols):
            code, name = _text(get('Member ID')), _name(get('Name'))
            if not code and not name:
                continue
            where = f'{MEMBERS} row {row}'
            if not name:
                data.warn(where, f'Member ID {code} has no name, so the row was skipped.')
                continue
            if not code:
                data.warn(where, f'{name} has no Member ID. Give every member a unique ID.')
            data.members.append(SheetMember(
                row=row, code=code, name=name, phone=_text(get('Phone')) if 'Phone' in cols else None,
                joined=_month(get('Joined (month)'), data, where, 'Joined (month)') if 'Joined (month)' in cols else None,
                left=_month(get('Left (month)'), data, where, 'Left (month)') if 'Left (month)' in cols else None,
            ))

    @staticmethod
    def _read_contributions(ws, year, data):
        cols = _columns(ws, ['Member ID'] + MONTHS, CONTRIBUTION_HEADERS)
        rows = []
        for row, get in _rows(ws, cols):
            code, name = _text(get('Member ID')), _name(get('Name'))
            amounts = {}
            for number, month in enumerate(MONTHS, start=1):
                value = _amount(get(month), data, f'{ws.title} row {row}, {month}')
                if value is not None:
                    amounts[number] = value
            if not code and not name:
                if amounts:
                    data.warn(f'{ws.title} row {row}', 'Has payments but no Member ID, so it was skipped.')
                continue
            rows.append(ContributionRow(row=row, code=code, name=name, amounts=amounts))
        data.contributions[year] = rows

    @staticmethod
    def _read_payouts(ws, data):
        cols = _columns(ws, ['Date', 'Amount'], PAYOUT_HEADERS)
        for row, get in _rows(ws, cols):
            where = f'{PAYOUTS} row {row}'
            amount = _amount(get('Amount'), data, f'{where}, Amount')
            values = [get(h) for h in PAYOUT_HEADERS]
            if amount is None:
                if any(v not in (None, '') for v in values):
                    data.warn(where, 'Has no amount, so it was skipped.')
                continue
            paid_on = _date(get('Date'))
            if paid_on is None:
                data.warn(where, 'Has no valid date, so it is not counted in any year.')
                continue
            data.payouts.append(PayoutRow(
                row=row, paid_on=paid_on, code=_text(get('Member ID')), name=_name(get('Name')),
                purpose=_text(get('Purpose')), amount=amount,
                approved_by=_text(get('Approved by')), notes=_text(get('Notes')),
            ))

    @staticmethod
    def _read_rates(ws, data):
        cols = _columns(ws, RATE_HEADERS, RATE_HEADERS)
        for row, get in _rows(ws, cols):
            where = f'{RATES} row {row}'
            raw_from, raw_amount = get('Effective from'), get('Monthly amount')
            if raw_from in (None, '') and raw_amount in (None, ''):
                continue
            effective = _month(raw_from, data, where, 'Effective from')
            amount = _amount(raw_amount, data, f'{where}, Monthly amount')
            if effective is None or amount is None:
                data.warn(where, 'Needs both a month and an amount, so it was skipped.')
                continue
            data.rates.append((effective, amount))
        data.rates.sort()

    @staticmethod
    def _read_summary(ws, data):
        cols = _columns(ws, ['Year', 'Opening balance'], SUMMARY_HEADERS)
        keys = dict(zip(SUMMARY_HEADERS[1:], ('opening', 'contributions', 'payouts', 'closing')))
        for row, get in _rows(ws, cols):
            year = get('Year')
            if year in (None, ''):
                continue
            try:
                year = int(float(year))
            except (TypeError, ValueError):
                data.warn(f'{SUMMARY} row {row}', f'Year {year!r} is not a year, so the row was skipped.')
                continue
            # Formula cells have no value until the file has been opened and saved in a spreadsheet app
            data.summary[year] = {
                key: _amount(get(header), data, f'{SUMMARY} row {row}, {header}')
                for header, key in keys.items()
            }


# ==================== CELL HELPERS ====================

def _columns(ws, required, known):
    """Map header → column number from row 1; error if a required header is missing."""
    found = {}
    for cell in ws[1]:
        label = _text(cell.value)
        for header in known:
            if label and label.casefold() == header.casefold():
                found.setdefault(header, cell.column)
    missing = [h for h in required if h not in found]
    if missing:
        raise ValueError(f"Sheet '{ws.title}' is missing the column(s): {', '.join(missing)} (row 1).")
    return found


def _rows(ws, cols):
    """Yield (row number, getter by header) for every row below the header."""
    for row_number, cells in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        def get(header, _cells=cells):
            col = cols.get(header)
            return _cells[col - 1] if col and col <= len(_cells) else None
        yield row_number, get


def _text(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    return text or None


def _name(value):
    text = _text(value)
    return re.sub(r'\s+', ' ', text) if text else None


def _amount(value, data, where):
    """A number from a cell, None if blank; text that isn't a number is warned about."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        data.warn(where, f'{value!r} is not an amount, so it was ignored.')
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(',', '').strip())
    except ValueError:
        data.warn(where, f'{value!r} is not an amount, so it was ignored.')
        return None


def _month(value, data, where, column):
    """The 1st of the month a cell refers to (a date, or text like 'Mar 2024')."""
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date().replace(day=1)
    if isinstance(value, date):
        return value.replace(day=1)
    text = str(value).strip()
    for fmt in _MONTH_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().replace(day=1)
        except ValueError:
            continue
    data.warn(where, f'{column} {text!r} is not a month (use e.g. Mar 2024), so it was ignored.')
    return None


def _date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value in (None, ''):
        return None
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
