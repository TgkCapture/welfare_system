# app/services/workbook_template.py
"""
Builds a group's standard workbook (see standard_workbook.py for the layout).

The template comes pre-filled with what the app already knows: the group's
members (each given a Member ID if they lack one), its rates and payout
purposes, and the opening balance carried over from the previous year.
Dropdowns limit Member IDs and purposes to known values, and the Summary
sheet is all formulas apart from the first opening balance.
"""
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.extensions import db
from app.models.ledger import PayoutPurpose, Rate, YearSummary
from app.models.member import Member
from app.services.standard_workbook import (
    CONTRIBUTION_HEADERS, LISTS, MEMBER_HEADERS, MEMBERS, PAYOUT_HEADERS, PAYOUTS,
    RATE_HEADERS, RATES, README, SUMMARY, SUMMARY_HEADERS, contributions_sheet,
)

ROWS = 300          # rows given formulas and dropdowns, beyond the pre-filled ones
PAYOUT_ROWS = 1000
MONTH_FORMAT = 'mmm yyyy'
MONEY_FORMAT = '#,##0'

_HEADER_FILL = PatternFill('solid', fgColor='1D4ED8')
_HEADER_FONT = Font(bold=True, color='FFFFFF')
_FORMULA_FILL = PatternFill('solid', fgColor='EEF2FF')


def assign_member_codes(group_id: int) -> None:
    """Give every member of the group without a Member ID the next free one (M001…)."""
    members = Member.for_group(group_id).order_by(Member.id).all()
    used = {m.code for m in members if m.code}
    number = 0
    for member in members:
        if member.code:
            continue
        while True:
            number += 1
            code = f'M{number:03d}'
            if code not in used:
                break
        member.code = code
        used.add(code)
    db.session.flush()


def build_template(group, year: int) -> BytesIO:
    """Return the group's standard workbook for *year* as .xlsx bytes."""
    assign_member_codes(group.id)
    members = Member.for_group(group.id).order_by(Member.code).all()
    purposes = [p.name for p in PayoutPurpose.for_group(group.id).filter_by(is_active=True)
                .order_by(PayoutPurpose.name)]
    rates = Rate.for_group(group.id).order_by(Rate.effective_from).all()
    previous = YearSummary.for_group(group.id).filter_by(year=year - 1).first()

    wb = Workbook()
    _readme(wb.active, group, year)
    _members(wb.create_sheet(MEMBERS), members)
    _contributions(wb.create_sheet(contributions_sheet(year)), members)
    _payouts(wb.create_sheet(PAYOUTS))
    _rates(wb.create_sheet(RATES), rates, year)
    _summary(wb.create_sheet(SUMMARY), year, purposes, previous.closing_balance if previous else 0)
    _lists(wb.create_sheet(LISTS), purposes)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ==================== SHEETS ====================

def _readme(ws, group, year):
    ws.title = README
    lines = [
        f'{group.settings.display_name if group.settings else group.name} — contributions workbook',
        '',
        'How to use this workbook',
        '1. Members: one row per member. Give each a unique Member ID and never reuse it.',
        '   Joined / Left are months (e.g. Mar 2024). Members are not expected to pay outside them.',
        f'2. Contributions {year}: one row per member. Type only what each member paid in each month.',
        '   Leave a month blank until it is collected; the app skips months nobody has paid yet.',
        '3. Payouts: one row per payout, with its date, the member it concerns, a purpose from the',
        '   list, the amount and who approved it.',
        '4. Rates: the monthly amount, and the month it took effect. Add a row when it changes.',
        '5. Summary: only the first opening balance is typed. Everything else is calculated.',
        '',
        'Starting a new year',
        '- Copy the latest Contributions sheet, rename it (e.g. Contributions 2027) and clear the months.',
        '- Add a row to Summary: copy the row above and change the year and sheet name in the formulas.',
        '',
        'Blue headers are column names the app looks for: keep them as they are.',
        'Shaded cells hold formulas: don\'t type over them.',
    ]
    for row, line in enumerate(lines, start=1):
        ws.cell(row, 1, line)
    ws['A1'].font = Font(bold=True, size=14)
    for row in (3, 13):
        ws.cell(row, 1).font = Font(bold=True)
    ws.column_dimensions['A'].width = 100


def _members(ws, members):
    _headers(ws, MEMBER_HEADERS, widths=[12, 30, 16, 16, 16, 30])
    for row, m in enumerate(members, start=2):
        ws.cell(row, 1, m.code)
        ws.cell(row, 2, m.display_name)
        ws.cell(row, 3, m.phone)
        for col, value in ((4, m.joined_on), (5, m.left_on)):
            cell = ws.cell(row, col, value)
            cell.number_format = MONTH_FORMAT
    for row in range(2, len(members) + ROWS):
        for col in (4, 5):
            ws.cell(row, col).number_format = MONTH_FORMAT


def _contributions(ws, members):
    _headers(ws, CONTRIBUTION_HEADERS, widths=[12, 30] + [11] * 12)
    last = len(members) + ROWS
    for row in range(2, last + 1):
        if row - 2 < len(members):
            ws.cell(row, 1, members[row - 2].code)
        _formula(ws.cell(row, 2), _name_lookup(f'A{row}'))
        for col in range(3, 15):
            ws.cell(row, col).number_format = MONEY_FORMAT
    _member_dropdown(ws, f'A2:A{last}')


def _payouts(ws):
    _headers(ws, PAYOUT_HEADERS, widths=[13, 12, 30, 24, 12, 24, 30])
    for row in range(2, PAYOUT_ROWS + 2):
        ws.cell(row, 1).number_format = 'yyyy-mm-dd'
        _formula(ws.cell(row, 3), _name_lookup(f'B{row}'))
        ws.cell(row, 5).number_format = MONEY_FORMAT
    _member_dropdown(ws, f'B2:B{PAYOUT_ROWS + 1}')
    purpose = DataValidation(type='list', formula1=f'={LISTS}!$A$2:$A$200', allow_blank=True)
    purpose.error = 'Choose a purpose from the list. Officers add purposes in the app.'
    ws.add_data_validation(purpose)
    purpose.add(f'D2:D{PAYOUT_ROWS + 1}')


def _rates(ws, rates, year):
    _headers(ws, RATE_HEADERS, widths=[16, 16])
    rows = [(r.effective_from, r.amount) for r in rates] or [(date(year, 1, 1), None)]
    for row, (effective, amount) in enumerate(rows, start=2):
        ws.cell(row, 1, effective).number_format = MONTH_FORMAT
        ws.cell(row, 2, amount).number_format = MONEY_FORMAT


def _summary(ws, year, purposes, opening):
    headers = SUMMARY_HEADERS + purposes
    _headers(ws, headers, widths=[8, 16, 16, 16, 16] + [18] * len(purposes))
    sheet = contributions_sheet(year)
    ws['A2'] = year
    ws['B2'] = opening                         # the only typed figure
    _formula(ws['C2'], f"=SUM('{sheet}'!C2:N{ROWS + 1000})")
    _formula(ws['D2'], _payouts_in_year('A2'))
    _formula(ws['E2'], '=B2+C2-D2')
    for offset, _ in enumerate(purposes):
        col = get_column_letter(6 + offset)
        _formula(ws[f'{col}2'], _payouts_in_year('A2', purpose_cell=f'{col}$1'))
    for col in range(2, len(headers) + 1):
        ws.cell(2, col).number_format = MONEY_FORMAT


def _lists(ws, purposes):
    ws['A1'] = 'Payout purposes'
    for row, name in enumerate(purposes, start=2):
        ws.cell(row, 1, name)
    ws.sheet_state = 'hidden'


# ==================== HELPERS ====================

def _headers(ws, headers, widths):
    for col, (header, width) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(1, col, header)
        cell.fill, cell.font = _HEADER_FILL, _HEADER_FONT
        cell.alignment = Alignment(horizontal='center')
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = 'A2'


def _formula(cell, formula):
    cell.value = formula
    cell.fill = _FORMULA_FILL


def _name_lookup(id_cell):
    return f'=IF({id_cell}="","",IFERROR(VLOOKUP({id_cell},{MEMBERS}!$A:$B,2,FALSE),"Unknown ID"))'


def _member_dropdown(ws, cells):
    dv = DataValidation(type='list', formula1=f'={MEMBERS}!$A$2:$A$2000', allow_blank=True)
    dv.error = 'Use a Member ID from the Members sheet.'
    ws.add_data_validation(dv)
    dv.add(cells)


def _payouts_in_year(year_cell, purpose_cell=None):
    criteria = (f'{PAYOUTS}!$A:$A,">="&DATE({year_cell},1,1),'
                f'{PAYOUTS}!$A:$A,"<="&DATE({year_cell},12,31)')
    if purpose_cell:
        criteria += f',{PAYOUTS}!$D:$D,{purpose_cell}'
    return f'=SUMIFS({PAYOUTS}!$E:$E,{criteria})'
