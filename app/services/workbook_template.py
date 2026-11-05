# app/services/workbook_template.py
"""
Writes standard workbooks (see standard_workbook.py for the layout).

``write_workbook()`` turns a WorkbookSpec into a workbook: one Contributions
sheet per year, dropdowns limiting Member IDs and purposes to known values,
and a Summary that is all formulas apart from the first opening balance.

``build_template()`` makes a group's whole workbook, every year from the
first one stored up to the year asked for, pre-filled with what the app
already knows: its members (each given a Member ID if they lack one), what
each paid each month, Excess, payouts, rates, payout purposes and the first
opening balance. The legacy converter fills a spec from an old workbook
instead.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.extensions import db
from app.models.ledger import Payout, PayoutPurpose, Rate, YearSummary
from app.models.member import Contribution, Member, MemberYear
from app.services.standard_workbook import (
    CONTRIBUTION_HEADERS, LISTS, MEMBER_HEADERS, MEMBERS, PAYOUT_HEADERS, PAYOUTS,
    RATE_HEADERS, RATES, README, SUMMARY, SUMMARY_HEADERS, contributions_sheet, payouts_in_year,
    summary_formula,
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
    name: str = None        # who it went to, when they aren't a member


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


def stored_years(group_id: int) -> list:
    """Every year the group has payments, payouts or balances stored for, oldest first."""
    years = set()
    for model in (Contribution, Payout, YearSummary):
        years.update(y for (y,) in model.for_group(group_id).with_entities(model.year).distinct())
    return sorted(years)


def template_years(group_id: int, year: int) -> list:
    """The years a download up to *year* holds: from the first stored year, never dropping a stored one."""
    stored = stored_years(group_id)
    return list(range(min(stored + [year]), max(stored + [year]) + 1))


def build_template(group, year: int) -> BytesIO:
    """Return the group's whole standard workbook, up to *year*, as .xlsx bytes.

    One Contributions sheet per year, from the first year the app has stored
    (or *year* alone, for a group with nothing stored yet). Stored years come
    filled in with what each member paid each month, Excess and payouts, so
    the history and its carry-overs stay in one workbook; later years start
    empty. Syncing it back unchanged stores the same figures.
    """
    gid = group.id
    assign_member_codes(gid)
    years = template_years(gid, year)
    members = Member.for_group(gid).order_by(Member.code).all()
    by_id = {m.id: m for m in members}

    contributions = defaultdict(lambda: defaultdict(dict))     # year → code → month → amount
    on_sheet = defaultdict(set)                                 # year → Member IDs with stored months
    for c in Contribution.for_group(gid):
        code = by_id[c.member_id].code
        on_sheet[c.year].add(code)
        if c.amount:
            contributions[c.year][code][c.month] = c.amount

    excess = defaultdict(dict)
    for my in MemberYear.for_group(gid).filter(MemberYear.excess_paid != 0):
        excess[my.year][by_id[my.member_id].code] = my.excess_paid
        on_sheet[my.year].add(by_id[my.member_id].code)

    year_members = {
        y: [m.code for m in members
            if m.code in on_sheet[y] or any(m.is_member_in(y, month) for month in range(1, 13))]
        for y in years
    }

    first = YearSummary.for_group(gid).filter_by(year=years[0]).first()
    spec = WorkbookSpec(
        title=group.settings.display_name if group.settings else group.name,
        years=years,
        members=[SpecMember(m.code, m.display_name, m.phone, m.joined_on, m.left_on) for m in members],
        purposes=[p.name for p in PayoutPurpose.for_group(gid).filter_by(is_active=True)
                  .order_by(PayoutPurpose.name)],
        rates=[(r.effective_from, r.amount)
               for r in Rate.for_group(gid).order_by(Rate.effective_from)] or [(date(years[0], 1, 1), None)],
        opening_balance=first.opening_balance if first else 0,
        year_members=year_members,
        contributions=contributions,
        excess=excess,
        payouts=[
            SpecPayout(p.paid_on or date(p.year, 12, 31),
                       by_id[p.member_id].code if p.member_id in by_id else None,
                       p.purpose, p.amount, p.approved_by, p.notes,
                       name=None if p.member_id in by_id else p.beneficiary)
            for p in Payout.for_group(gid).order_by(Payout.paid_on, Payout.sheet_row, Payout.id)
        ],
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
        '- Easiest: download the workbook again from the app, up to the new year. It comes with every',
        '  year so far filled in and the new year empty, ready to replace this one.',
        '- Or by hand: copy the latest Contributions sheet, rename it (e.g. Contributions 2027) and clear',
        '  the months; then add a row to Summary (copy the row above, change the year and sheet name).',
        '',
        'Blue headers are column names the app looks for: keep them as they are.',
        'Shaded cells hold formulas: don\'t type over them.',
    ]
    for row, line in enumerate(lines, start=1):
        ws.cell(row, 1, line)
    ws['A1'].font = Font(bold=True, size=14)
    for row in (3, 16):
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
        if p and p.name and not p.code:
            ws.cell(row, 3, p.name)                  # not a member: the name is typed
        else:
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
        for col, header in enumerate(SUMMARY_HEADERS[1:], start=2):
            if row == 2 and header == 'Opening balance':
                ws['B2'] = opening                     # the only typed figure
            else:
                _formula(ws.cell(row, col), summary_formula(header, row, year))
        for offset, _ in enumerate(purposes):
            col = get_column_letter(6 + offset)
            _formula(ws[f'{col}{row}'], payouts_in_year(f'A{row}', purpose_cell=f'{col}$1'))
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
