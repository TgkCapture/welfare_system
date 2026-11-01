"""
Synthetic contribution workbooks shaped like the real Mzugoss sheet
(MGSS.xlsx), with invented names and amounts.

Year sheet layout ('2025', '2026'):

    row 2   MONEY DISPENSED     | amount
    row 3   TOTAL BOOK BALANCE  | amount
    row 4   <prev> Carry Over   | amount
    row 6   Name | January … December | (blank) | DISPENSED TO
    row 7+  one row per member, payouts in column O (repeat payouts in P)
    last    Total row

The 2018-era 'Old' sheet has a title in row 1, its header in row 7 and
only August–December. Hidden, month-named leftover sheets follow.

Values are written as plain numbers, not formulas: openpyxl does not
store calculated results, and pandas reads cached values only.
"""
import calendar

from openpyxl import Workbook

MONTHS = list(calendar.month_name)[1:]

# March 2026 per member: paid, partial (500 of 1000), blank, zero, text,
# paid (non-ASCII name), joined in April (double space in name as in real data)
MEMBERS_2026 = [
    ('Alinafe Banda',   {'January': 1000, 'February': 1000, 'March': 1000}, None),
    ('Bright Phiri',    {'January': 1000, 'March': 500},                    None),
    ('Chisomo Mwale',   {'January': 1000},                                  None),
    ('Dumisani Zulu',   {'January': 1000, 'March': 0},                      None),
    ('Esther Tembo',    {'March': 'pending'},                               (20000, 10000)),
    ('Fañny Kumwenda',  {'March': 1000},                                    None),
    ('Gift  Nyirenda',  {'April': 1000, 'May': 1000},                       None),
]

MONEY_DISPENSED_2026    = 30000
TOTAL_BOOK_BALANCE_2026 = 150000.50
CARRY_OVER_2026         = 120000

DISPENSED_COL = 15   # column O


def _write_year_sheet(ws, members, prev_year, dispensed, balance, carry_over):
    ws['A2'], ws['B2'] = 'MONEY DISPENSED', dispensed
    ws['A3'], ws['B3'] = 'TOTAL BOOK BALANCE', balance
    ws['A4'], ws['B4'] = f'{prev_year} Carry Over', carry_over

    ws.cell(6, 1, 'Name')
    for i, month in enumerate(MONTHS, start=2):
        ws.cell(6, i, month)
    ws.cell(6, DISPENSED_COL, 'DISPENSED TO')

    row = 7
    for name, paid, payouts in members:
        ws.cell(row, 1, name)
        for i, month in enumerate(MONTHS, start=2):
            if month in paid:
                ws.cell(row, i, paid[month])
        for offset, amount in enumerate(payouts or ()):
            ws.cell(row, DISPENSED_COL + offset, amount)
        row += 1

    row += 1   # the real sheet leaves blank rows before Total
    ws.cell(row, 1, 'Total')
    for i, month in enumerate(MONTHS, start=2):
        ws.cell(row, i, sum(
            p[month] for _, p, _ in members
            if isinstance(p.get(month), (int, float))
        ))


def _write_old_sheet(ws):
    ws['A1'] = 'MZUGOSS CLASS OF 2018 MONTHLY CONTRIBUTIONS'
    ws['A2'], ws['B2'] = 'MONEY DISPENSED', 1000
    ws['A3'], ws['B3'] = 'TOTAL BOOK BALANCE', 2000
    ws.append([])
    ws.append([])
    ws.append([])
    ws.append(['Name', 'August', 'September', 'October', 'November', 'December'])
    ws.append(['Alinafe Banda', 500, 500, 500])
    ws.append(['Bright Phiri', 500])


def build_mzugoss_workbook(path):
    """Write a workbook mirroring MGSS.xlsx to *path* and return it."""
    wb = Workbook()
    _write_old_sheet(wb.active)
    wb.active.title = 'Old'

    _write_year_sheet(
        wb.create_sheet('2025'),
        [('Alinafe Banda', {'March': 1000}, (5000,)), ('Bright Phiri', {}, None)],
        prev_year=2024, dispensed=5000, balance=60000, carry_over=40000,
    )
    _write_year_sheet(
        wb.create_sheet('2026'), MEMBERS_2026, prev_year=2025,
        dispensed=MONEY_DISPENSED_2026, balance=TOTAL_BOOK_BALANCE_2026,
        carry_over=CARRY_OVER_2026,
    )

    for month in ('August', 'Septmber', 'October'):
        wb.create_sheet(month).sheet_state = 'hidden'

    wb.save(path)
    return path
