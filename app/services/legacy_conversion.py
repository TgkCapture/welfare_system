# app/services/legacy_conversion.py
"""
Converts a workbook in the old Mzugoss layout to the standard layout.

Old layout, one sheet per year named "YYYY":

    rows above the header   MONEY DISPENSED | TOTAL BOOK BALANCE | <year> Carry Over
    header row              Name | January … December | (blank) | DISPENSED TO
    member rows             payments by month; payouts in DISPENSED TO and the
                            unlabelled numeric column(s) right after it
    Total row               ends the member rows

Other sheets (the 2018-era "Old" sheet, hidden month sheets) are ignored
and listed in the review.

What the conversion decides, and lists in the review for a person to check:
  - Members: one per distinct name (case, spacing and dots ignored), plus
    any merges confirmed in the name-suggestions file. Member IDs follow
    the order names first appear.
  - Joined: blank for members on the first year's sheet; otherwise the first
    month they paid in the first year they appear (January if they never
    paid that year). Left: December of the last year they appear, unless they
    are on the latest sheet. A member missing from a sheet between two they
    are on paid nothing that year: they get an empty row there.
  - Rates: the most common amount paid each year, from January of that year
    (the first rate from the first month anyone paid).
  - Excess: a note like "1500N" beside a member's months means they paid that
    much beyond the year's months. It goes in the Excess column and becomes
    credit for the next year's first months.
  - Payouts: one row per amount, dated 31 December of the year (or today for
    the current year), purpose "Unspecified", since the old sheet records
    neither. Optionally, payouts that repeat the previous year's (same member
    and amount) are dropped.
  - Balances: only the first year's carry-over is used, as the opening
    balance. Every later carry-over is calculated, which corrects any typed
    carry-over that disagreed with the previous closing balance.
"""
import calendar
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from openpyxl import load_workbook

from app.models.member import normalise_name, tidy_name
from app.services.name_matching import may_be_same_person, similarity
from app.services.workbook_template import SpecMember, SpecPayout, WorkbookSpec

UNSPECIFIED = 'Unspecified'
_MONTHS = [m.casefold() for m in calendar.month_name[1:]]
_YEAR_SHEET = re.compile(r'^\s*(\d{4})\s*$')
_SUMMARY_ROW = re.compile(r'\btotals?\b|\bbalance\b|\bdispensed\b|\bcarry\b|\bmoney\b', re.I)
_EXCESS_NOTE = re.compile(r'^\s*([\d,]+(?:\.\d+)?)\s*N\s*$', re.I)   # e.g. 1500N


@dataclass
class YearSheet:
    year: int
    title: str
    rows: list = field(default_factory=list)       # [(row, display name, {month: amount}, [payouts])]
    carry_over: float = None
    carry_over_label: str = None
    money_dispensed: float = None
    book_balance: float = None
    excess: dict = field(default_factory=dict)     # row → excess noted beside it (e.g. 1500N)
    notes: list = field(default_factory=list)      # review lines found while reading


@dataclass
class Conversion:
    spec: WorkbookSpec
    review: list                     # Markdown lines
    suggestions: list                # [(keep, merge, similarity, keep_years, merge_years)]
    legacy_totals: dict              # (year, month) → total paid, as the old sheet has it


class LegacyConverter:

    def __init__(self, path: str, title: str, merges: dict = None, drop_repeated_payouts: bool = False,
                 today: date = None, purposes: list = None):
        self.path, self.title = path, title
        # normalised name to merge → normalised name to keep
        self.merges = {normalise_name(k): normalise_name(v) for k, v in (merges or {}).items()}
        # A merged member is shown under the name chosen to keep
        self.kept_names = {normalise_name(v): tidy_name(v) for v in (merges or {}).values()}
        self.drop_repeated_payouts = drop_repeated_payouts
        # The group's own payout purposes, for the dropdown; old payouts are "Unspecified"
        self.purposes = [p for p in (purposes or []) if p.casefold() != UNSPECIFIED.casefold()]
        self.today = today or date.today()

    def convert(self) -> Conversion:
        wb = load_workbook(self.path, data_only=True)
        sheets = []
        ignored = []
        for ws in wb.worksheets:
            match = _YEAR_SHEET.match(ws.title)
            if match and ws.sheet_state == 'visible':
                sheets.append(self._read_year(ws, int(match.group(1))))
            else:
                ignored.append(f'{ws.title} ({ws.sheet_state})')
        if not sheets:
            raise ValueError('No visible sheets named after a year (e.g. 2025) were found.')
        sheets.sort(key=lambda s: s.year)

        review = [f'# Conversion review: {self.title}', '',
                  f'Source: `{self.path}`. Year sheets read: {", ".join(str(s.year) for s in sheets)}.']
        if ignored:
            review.append(f'Ignored sheets: {", ".join(ignored)}.')
        review.append('')

        members, appearances, first_paid = self._members(sheets)
        spec = WorkbookSpec(
            title=self.title,
            years=[s.year for s in sheets],
            members=list(members.values()),
            purposes=self.purposes + [UNSPECIFIED],
        )
        self._joined_left(spec, sheets, members, appearances, first_paid, review)
        self._contributions(spec, sheets, members, appearances, review)
        self._rates(spec, sheets, review)
        self._payouts(spec, sheets, members, review)
        self._balances(spec, sheets, review)
        notes = [note for sheet in sheets for note in sheet.notes]
        if notes:
            review += ['## Other notes', ''] + notes + ['']

        legacy_totals = {
            (s.year, month): sum(amounts.get(month, 0) for _, _, amounts, _ in s.rows if amounts.get(month, 0) > 0)
            for s in sheets for month in range(1, 13)
        }
        return Conversion(spec, review, self._suggestions(members, appearances), legacy_totals)

    # ==================== READING ====================

    def _read_year(self, ws, year) -> YearSheet:
        sheet = YearSheet(year=year, title=ws.title)
        header = next((r for r in range(1, min(ws.max_row, 30) + 1)
                       if sum(str(c.value).strip().casefold() in _MONTHS for c in ws[r] if c.value) >= 3), None)
        if header is None:
            raise ValueError(f"Sheet '{ws.title}': no row with month names was found.")

        month_cols, name_col, payout_cols = {}, 1, []
        for cell in ws[header]:
            label = str(cell.value).strip().casefold() if cell.value is not None else ''
            if label in _MONTHS:
                month_cols[_MONTHS.index(label) + 1] = cell.column
            elif label == 'name':
                name_col = cell.column
            elif 'dispensed' in label:
                payout_cols.append(cell.column)

        # Values above the header: carry-over, money dispensed, book balance
        for r in range(1, header):
            label = str(ws.cell(r, 1).value or '')
            value = next((c.value for c in ws[r][1:] if isinstance(c.value, (int, float))), None)
            if 'carry' in label.casefold():
                sheet.carry_over, sheet.carry_over_label = value, label.strip()
            elif 'money dispensed' in label.casefold():
                sheet.money_dispensed = value
            elif 'book balance' in label.casefold():
                sheet.book_balance = value

        last_month_col = max(month_cols.values())
        for r in range(header + 1, ws.max_row + 1):
            raw_name = ws.cell(r, name_col).value
            if raw_name is None or not str(raw_name).strip():
                continue
            if _SUMMARY_ROW.search(str(raw_name)):
                break                                  # the Total row ends the members
            name = tidy_name(raw_name)
            amounts = {}
            for month, col in month_cols.items():
                value = ws.cell(r, col).value
                if isinstance(value, (int, float)):
                    amounts[month] = float(value)
                elif value not in (None, ''):
                    sheet.notes.append(f'- {ws.title} row {r}, {calendar.month_name[month]}: '
                                       f'"{value}" is not a number and was left out.')
            payouts = []
            # DISPENSED TO, plus repeat payouts in the unlabelled columns after it
            extra = range(max(payout_cols) + 1, max(payout_cols) + 4) if payout_cols else ()
            for col in list(payout_cols) + list(extra):
                value = ws.cell(r, col).value
                if isinstance(value, (int, float)) and value:
                    payouts.append(float(value))
            for col in range(last_month_col + 1, (min(payout_cols) if payout_cols else last_month_col + 1)):
                value = ws.cell(r, col).value
                if value in (None, ''):
                    continue
                excess = _EXCESS_NOTE.match(str(value))
                if excess:
                    sheet.excess[r] = float(excess.group(1).replace(',', ''))
                else:
                    sheet.notes.append(f'- {ws.title} row {r} ({name}) has a note in column '
                                       f'{ws.cell(r, col).column_letter}: "{value}". It was not carried over.')
            sheet.rows.append((r, name, amounts, payouts))
        return sheet

    # ==================== MEMBERS ====================

    def _members(self, sheets):
        """One member per name after merges, numbered in order of first appearance."""
        members, appearances, first_paid = {}, defaultdict(list), {}
        for sheet in sheets:
            for row, name, amounts, _ in sheet.rows:
                key = self._key(name)
                if key not in members:
                    members[key] = SpecMember(code=f'M{len(members) + 1:03d}',
                                              name=self.kept_names.get(key, name))
                appearances[key].append(sheet.year)
                paid = [m for m, a in amounts.items() if a > 0]
                if paid and key not in first_paid:
                    first_paid[key] = (sheet.year, min(paid))
        return members, appearances, first_paid

    def _key(self, name):
        key = normalise_name(name)
        return self.merges.get(key, key)

    def _joined_left(self, spec, sheets, members, appearances, first_paid, review):
        first_year, last_year = sheets[0].year, sheets[-1].year
        guesses = []
        for key, member in members.items():
            years = sorted(set(appearances[key]))
            notes = []
            if years[0] != first_year:
                paid_year, paid_month = first_paid.get(key, (None, None))
                month = paid_month if paid_year == years[0] else 1
                member.joined = date(years[0], month, 1)
                notes.append(f'Joined guessed ({"first payment" if paid_year == years[0] else "first sheet"})')
            if years[-1] != last_year:
                member.left = date(years[-1], 12, 1)
                notes.append(f'Left guessed (not on the {years[-1] + 1} sheet)')
            gaps = [y for y in range(years[0], years[-1] + 1) if y not in years]
            if gaps:
                notes.append(f'Not on the {", ".join(map(str, gaps))} sheet: given an empty row there, '
                             'so counted as unpaid (paid nothing that year)')
            if notes:
                member.notes = '; '.join(notes) + '. Please check.'
                joined = f'{member.joined:%b %Y}' if member.joined else '—'
                left = f'{member.left:%b %Y}' if member.left else '—'
                guesses.append(f'| {member.code} | {member.name} | {joined} | {left} | {"; ".join(notes)} |')
        review += ['## Joined and Left months to check', '',
                   'The old sheets have no join or leave dates, so these were worked out from which '
                   'sheets a member is on and when they first paid. A member is not counted as owing '
                   'for months outside them. They are also in the Members sheet\'s Notes column.', '']
        if guesses:
            review += ['| ID | Name | Joined | Left | Why |', '| --- | --- | --- | --- | --- |'] + guesses
        else:
            review.append('Every member is on every sheet: nothing to check.')
        review.append('')

    # ==================== CONTRIBUTIONS AND RATES ====================

    def _contributions(self, spec, sheets, members, appearances, review):
        spec.year_members = {}
        excess_lines = []
        for sheet in sheets:
            codes, amounts, excess = [], {}, {}
            for row, name, paid, _ in sheet.rows:
                code = members[self._key(name)].code
                if row in sheet.excess:
                    excess[code] = excess.get(code, 0) + sheet.excess[row]
                    excess_lines.append(f'- {sheet.title} row {row}: {members[self._key(name)].name} '
                                        f'paid {sheet.excess[row]:,.0f} extra, carried into {sheet.year + 1}.')
                if code in amounts:
                    for month, amount in paid.items():         # a merged respelling on the same sheet
                        amounts[code][month] = amounts[code].get(month, 0) + amount
                else:
                    codes.append(code)
                    amounts[code] = dict(paid)
            # A member missing between two sheets they're on paid nothing that year: still listed
            for key, member in members.items():
                years = appearances[key]
                if min(years) < sheet.year < max(years) and member.code not in amounts:
                    codes.append(member.code)
            spec.year_members[sheet.year] = codes
            spec.contributions[sheet.year] = amounts
            spec.excess[sheet.year] = excess
        if excess_lines:
            review += ['## Excess payments', '',
                       "Notes like \"1500N\" became the Excess column: money paid beyond the year's months. "
                       "The old sheets left it out of the book balance; it now counts in the year it was "
                       "paid and covers the member's first months of the next year, so don't type those "
                       "months again.", ''] + excess_lines + ['']

    def _rates(self, spec, sheets, review):
        lines, current = [], None
        for sheet in sheets:
            paid = Counter(a for _, _, amounts, _ in sheet.rows for a in amounts.values() if a > 0)
            if not paid:
                continue
            rate = paid.most_common(1)[0][0]
            if rate != current:
                # The first rate starts when payments started; later changes from January
                month = 1 if current is not None else min(
                    m for _, _, amounts, _ in sheet.rows for m, a in amounts.items() if a > 0)
                spec.rates.append((date(sheet.year, month, 1), rate))
                lines.append(f'- {rate:,.0f} from {calendar.month_name[month]} {sheet.year}')
                current = rate
        review += ['## Rates to check', '',
                   'Taken as the amount most members paid each year. If a change took effect in '
                   'another month, correct its date on the Rates sheet: payments below the rate show '
                   'as partial.', ''] + lines + ['']

    # ==================== PAYOUTS ====================

    def _payouts(self, spec, sheets, members, review):
        previous, dropped, kept_repeats = set(), [], []
        for sheet in sheets:
            paid_on = min(date(sheet.year, 12, 31), self.today)
            this_year = set()
            for row, name, _, payouts in sheet.rows:
                member = members[self._key(name)]
                for amount in payouts:
                    repeat = (member.code, amount) in previous
                    this_year.add((member.code, amount))
                    line = f'- {sheet.title} row {row}: {member.name}, {amount:,.0f}'
                    if repeat and self.drop_repeated_payouts:
                        dropped.append(line)
                        continue
                    if repeat:
                        kept_repeats.append(line)
                    spec.payouts.append(SpecPayout(
                        paid_on=paid_on, code=member.code, purpose=UNSPECIFIED, amount=amount,
                        notes=f'Imported from the {sheet.title} sheet: the date and purpose were not recorded.',
                    ))
            previous = this_year

        review += ['## Payouts', '',
                   f'{len(spec.payouts)} payout(s) imported. The old sheets record no dates or purposes, so '
                   f'each is dated 31 December of its year (today for {sheets[-1].year}) with the purpose '
                   f'"{UNSPECIFIED}". Please fill in the real date, purpose and approver on the Payouts '
                   'sheet. Until then each sync will list them as warnings, and two payouts to one '
                   'member in the same year show as a possible repeat because they share a date.', '']
        if dropped:
            review += ['Dropped as repeats of the previous year\'s payout (same member and amount):', ''] + dropped + ['']
        if kept_repeats:
            review += ['Kept, but they repeat the previous year\'s payout (same member and amount). '
                       'Delete any that were copied by mistake:', ''] + kept_repeats + ['']

    # ==================== BALANCES ====================

    def _balances(self, spec, sheets, review):
        first = sheets[0]
        spec.opening_balance = first.carry_over or 0.0
        lines = ['## Balances', '',
                 f'Opening balance for {first.year}: {spec.opening_balance:,.0f}'
                 + (f' (from "{first.carry_over_label}")' if first.carry_over is not None
                    else f' (the "{first.carry_over_label}" row is empty)' if first.carry_over_label
                    else ' (no carry-over row)') + '.',
                 'Every later opening balance is the previous closing balance, calculated by the workbook. '
                 'Where the old sheet differs, the old figure is shown:', '',
                 '| Year | Opening | Paid in | Paid out | Closing | Old sheet |',
                 '| --- | ---: | ---: | ---: | ---: | --- |']
        opening = spec.opening_balance
        for sheet in sheets:
            paid_in = (sum(a for amounts in spec.contributions[sheet.year].values() for a in amounts.values() if a > 0)
                       + sum(spec.excess.get(sheet.year, {}).values()))
            paid_out = sum(p.amount for p in spec.payouts if p.paid_on.year == sheet.year)
            closing = opening + paid_in - paid_out
            old = []
            if sheet is not first and sheet.carry_over is not None and abs(sheet.carry_over - opening) > 0.005:
                old.append(f'carry-over {sheet.carry_over:,.0f}')
            if sheet.money_dispensed is not None and abs(sheet.money_dispensed - paid_out) > 0.005:
                old.append(f'dispensed {sheet.money_dispensed:,.0f}')
            if sheet.book_balance is not None and abs(sheet.book_balance - closing) > 0.005:
                old.append(f'book balance {sheet.book_balance:,.0f}')
            lines.append(f'| {sheet.year} | {opening:,.0f} | {paid_in:,.0f} | {paid_out:,.0f} | '
                         f'{closing:,.0f} | {"; ".join(old) or "same"} |')
            opening = closing
        review += lines + ['']

    # ==================== NAME SUGGESTIONS ====================

    def _suggestions(self, members, appearances):
        """Pairs of names that may be one person, never seen on the same sheet."""
        keys = list(members)
        pairs = []
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if set(appearances[a]) & set(appearances[b]):
                    continue        # both on one sheet: two people
                if may_be_same_person(a, b):
                    # Keep the fuller name, then the one on more sheets
                    rank = lambda k: (len(k.split()), len(set(appearances[k])), len(k))
                    keep, merge = (a, b) if rank(a) >= rank(b) else (b, a)
                    pairs.append((members[keep].name, members[merge].name, similarity(a, b),
                                  sorted(set(appearances[keep])), sorted(set(appearances[merge]))))
        return sorted(pairs, key=lambda p: -p[2])
