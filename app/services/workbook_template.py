# app/services/workbook_template.py
"""
Writes standard workbooks (see standard_workbook.py for the layout).

``write_workbook()`` turns a WorkbookSpec into a workbook: one Contributions
sheet per year, dropdowns limiting Member IDs and purposes to known values,
and a Summary that is all formulas apart from the first opening balance.

``build_template()`` makes a group's template for a year, pre-filled with
what the app already knows: its members (each given a Member ID if they
lack one), rates, payout purposes, and the opening balance carried over
from the previous year. The legacy converter fills a spec from an old
workbook instead.
"""
from dataclasses import dataclass, field
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

ROWS = 300          # extra rows given formulas and dropdowns, beyond the filled-in ones
PAYOUT_ROWS = 1000
MONTH_FORMAT = 'mmm yyyy'
MONEY_FORMAT = '#,##0'

_HEADER_FILL = PatternFill('solid', fgColor='1D4ED8')
_HEADER_FONT = Font(bold=True, color='FFFFFF')
_FORMULA_FILL = PatternFill('solid', fgColor='EEF2FF')


@dataclass
class SpecMember:
    code: str
    name: str
    phone: str = None
    joined: date = None
    left: date = None
    notes: str = None


@dataclass
class SpecPayout:
    paid_on: date
    code: str
    purpose: str
    amount: float
    approved_by: str = None
    notes: str = None


@dataclass
class WorkbookSpec:
    title: str
    years: list
    members: list                                       # [SpecMember]
    purposes: list                                      # purpose names for the dropdown
    rates: list = field(default_factory=list)           # [(effective_from, amount)]
    opening_balance: float = 0.0
    # year → Member IDs listed on that year's sheet (default: every member)
    year_members: dict = None
    # year → Member ID → month number → amount
    contributions: dict = field(default_factory=dict)
    # year → Member ID → excess paid beyond the months (carried into next year)
    excess: dict = field(default_factory=dict)
    payouts: list = field(default_factory=list)         # [SpecPayout]


# ==================== GROUP TEMPLATE ====================

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
    previous = YearSummary.for_group(group.id).filter_by(year=year - 1).first()
    spec = WorkbookSpec(
        title=group.settings.display_name if group.settings else group.name,
        years=[year],
        members=[
            SpecMember(m.code, m.display_name, m.phone, m.joined_on, m.left_on)
            for m in Member.for_group(group.id).order_by(Member.code)
        ],
        purposes=[p.name for p in PayoutPurpose.for_group(group.id).filter_by(is_active=True)
                  .order_by(PayoutPurpose.name)],
        rates=[(r.effective_from, r.amount)
               for r in Rate.for_group(group.id).order_by(Rate.effective_from)] or [(date(year, 1, 1), None)],
        opening_balance=previous.closing_balance if previous else 0,
    )
    return save(write_workbook(spec))


def save(wb) -> BytesIO:
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ==================== WORKBOOK ====================

def write_workbook(spec: WorkbookSpec) -> Workbook:
    wb = Workbook()
    _readme(wb.active, spec.title, spec.years[-1])
    _members(wb.create_sheet(MEMBERS), spec.members)
    for year in spec.years:
        codes = (spec.year_members or {}).get(year, [m.code for m in spec.members])
        _contributions(wb.create_sheet(contributions_sheet(year)), codes,
                       spec.contributions.get(year, {}), spec.excess.get(year, {}))
    _payouts(wb.create_sheet(PAYOUTS), spec.payouts)
    _rates(wb.create_sheet(RATES), spec.rates)
    _summary(wb.create_sheet(SUMMARY), spec.years, spec.purposes, spec.opening_balance)
    _lists(wb.create_sheet(LISTS), spec.purposes)
    return wb


def _readme(ws, title, year):
    ws.title = README
    lines = [
        f'{title} — contributions workbook',
        '',
        'How to use this workbook',
        '1. Members: one row per member. Give each a unique Member ID and never reuse it.',
        '   Joined / Left are months (e.g. Mar 2024). Members are not expected to pay outside them.',
        f'2. Contributions {year}: one row per member. Type only what each member paid in each month.',
        '   Leave a month blank until it is collected; the app skips months nobody has paid yet.',
        '   Excess: money a member paid beyond the months (e.g. 13,500 against 12,000 due). It is',
        '   credit: the app applies it to their first months next year, so leave those months blank.',
        '   Paying more than the rate in a month also covers their following month(s).',
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
    _headers(ws, MEMBER_HEADERS, widths=[12, 30, 16, 16, 16, 50])
    for row, m in enumerate(members, start=2):
        for col, value in enumerate((m.code, m.name, m.phone, m.joined, m.left, m.notes), start=1):
            ws.cell(row, col, value)
    for row in range(2, len(members) + ROWS):
        for col in (4, 5):
            ws.cell(row, col).number_format = MONTH_FORMAT


def _contributions(ws, codes, amounts, excess):
    _headers(ws, CONTRIBUTION_HEADERS, widths=[12, 30] + [11] * 12 + [12])
    last = len(codes) + ROWS
    for row in range(2, last + 1):
        code = codes[row - 2] if row - 2 < len(codes) else None
        ws.cell(row, 1, code)
        _formula(ws.cell(row, 2), _name_lookup(f'A{row}'))
        for month in range(1, 13):
            cell = ws.cell(row, 2 + month, amounts.get(code, {}).get(month) if code else None)
            cell.number_format = MONEY_FORMAT
        ws.cell(row, 15, excess.get(code) if code else None).number_format = MONEY_FORMAT
    _member_dropdown(ws, f'A2:A{last}')


def _payouts(ws, payouts):
    _headers(ws, PAYOUT_HEADERS, widths=[13, 12, 30, 24, 12, 24, 50])
    last = len(payouts) + PAYOUT_ROWS + 1
    for row in range(2, last + 1):
        p = payouts[row - 2] if row - 2 < len(payouts) else None
        if p:
            ws.cell(row, 1, p.paid_on)
            ws.cell(row, 2, p.code)
            ws.cell(row, 4, p.purpose)
            ws.cell(row, 5, p.amount)
            ws.cell(row, 6, p.approved_by)
            ws.cell(row, 7, p.notes)
        ws.cell(row, 1).number_format = 'yyyy-mm-dd'
        _formula(ws.cell(row, 3), _name_lookup(f'B{row}'))
        ws.cell(row, 5).number_format = MONEY_FORMAT
    _member_dropdown(ws, f'B2:B{last}')
    purpose = DataValidation(type='list', formula1=f'={LISTS}!$A$2:$A$200', allow_blank=True)
    purpose.error = 'Choose a purpose from the list. Officers add purposes in the app.'
    ws.add_data_validation(purpose)
    purpose.add(f'D2:D{last}')


def _rates(ws, rates):
    _headers(ws, RATE_HEADERS, widths=[16, 16])
    for row, (effective, amount) in enumerate(rates, start=2):
        ws.cell(row, 1, effective).number_format = MONTH_FORMAT
        ws.cell(row, 2, amount).number_format = MONEY_FORMAT


def _summary(ws, years, purposes, opening):
    headers = SUMMARY_HEADERS + purposes
    _headers(ws, headers, widths=[8, 16, 16, 16, 16] + [18] * len(purposes))
    for row, year in enumerate(years, start=2):
        ws.cell(row, 1, year)
        if row == 2:
            ws['B2'] = opening                         # the only typed figure
        else:
            _formula(ws.cell(row, 2), f'=E{row - 1}')  # carried over
        # Months and Excess: all money received in the year
        _formula(ws.cell(row, 3), f"=SUM('{contributions_sheet(year)}'!C2:O{ROWS + 2000})")
        _formula(ws.cell(row, 4), _payouts_in_year(f'A{row}'))
        _formula(ws.cell(row, 5), f'=B{row}+C{row}-D{row}')
        for offset, _ in enumerate(purposes):
            col = get_column_letter(6 + offset)
            _formula(ws[f'{col}{row}'], _payouts_in_year(f'A{row}', purpose_cell=f'{col}$1'))
        for col in range(2, len(headers) + 1):
            ws.cell(row, col).number_format = MONEY_FORMAT


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
