# app/services/standard_sync.py
"""
Syncs a standard workbook into the stored read-model, and checks it.

One sync stores everything the workbook holds: members, every month that
has at least one payment in every year, all payouts, the rates, and the
calculated monthly and yearly balances. A month nobody has paid yet is
left alone, so blank future months don't turn everyone into a defaulter.

Payment status uses the rate in force that month (paid / partial / unpaid).
Months before a member joined or after they left are not counted against
them. Carry-overs are calculated: each year opens with the previous year's
calculated closing balance. Only the first year's opening balance is read
from the sheet.

Checks raise warnings, never errors, so a sync always stores what it can:
  - the Summary sheet's figures against the app's calculation
    (including each opening balance against the previous closing)
  - payouts with an unknown purpose or member, a future date, or a duplicate
  - payments outside a member's Joined / Left months
  - unknown or duplicate Member IDs, and members missing from a year's sheet
"""
import calendar
from collections import defaultdict
from datetime import date, datetime

from app.extensions import db
from app.models.ledger import Payout, PayoutPurpose, Rate, SyncRun, YearSummary
from app.models.member import (
    Contribution, Member, MemberAlias, PeriodSummary, normalise_name,
)
from app.services.period_store import status_for
from app.services.standard_workbook import MEMBERS, PAYOUTS, SUMMARY, StandardWorkbook

_TOLERANCE = 0.005


def _money(value) -> str:
    return f'{value:,.2f}'.rstrip('0').rstrip('.')


class StandardSync:

    @staticmethod
    def sync(group, path: str, user=None, source: str = 'upload') -> SyncRun:
        """Read the workbook at *path*, store it for *group* and record the sync."""
        data = StandardWorkbook.read(path)
        now = datetime.utcnow()
        sync = StandardSync(group, data, now)

        sync.store_members()
        sync.store_rates()
        months = sync.store_contributions()
        sync.store_payouts()
        sync.store_balances(months)

        run = SyncRun(
            group_id=group.id, synced_by=user.id if user else None, synced_at=now,
            source=source, layout='standard', warnings=data.warnings,
            details={
                'years': sorted(data.contributions),
                'months': [list(m) for m in sorted(months)],
                'new_members': sync.new_members,
            },
        )
        db.session.add(run)
        db.session.commit()
        return run

    def __init__(self, group, data, now):
        self.group, self.data, self.now = group, data, now
        self.new_members = []
        self.by_code = {}          # Member ID → Member, for this workbook

    # ==================== MEMBERS ====================

    def store_members(self):
        existing = Member.for_group(self.group.id).all()
        codes = {m.code: m for m in existing if m.code}
        names = {m.normalised_name: m for m in existing}
        for alias in MemberAlias.for_group(self.group.id):
            names.setdefault(alias.normalised_name, alias.member)

        seen_codes = {}
        for row in self.data.members:
            where = f'{MEMBERS} row {row.row}'
            if row.code and row.code in seen_codes:
                self.data.warn(where, f'Member ID {row.code} is also used on row {seen_codes[row.code]}; '
                                      'this row was skipped.')
                continue
            key = normalise_name(row.name)
            member = codes.get(row.code) if row.code else None
            member = member or names.get(key)

            if member is None:
                member = Member(group_id=self.group.id, display_name=row.name, normalised_name=key)
                db.session.add(member)
                self.new_members.append(row.name)
            elif member.normalised_name != key:
                self._rename(member, row.name, key, names, where)

            if row.code:
                # Not held by another member: that member would have been found by code above
                if member.code and member.code != row.code and codes.get(member.code) is member:
                    del codes[member.code]     # the old ID is free for another row to claim
                member.code = row.code
                codes[row.code] = member
                seen_codes[row.code] = row.row
                self.by_code[row.code] = member
            names[key] = member
            member.phone = row.phone
            member.joined_on, member.left_on = row.joined, row.left
            member.is_active = row.left is None or row.left >= date.today().replace(day=1)
        db.session.flush()

    def _rename(self, member, name, key, names, where):
        """The sheet spells an existing member differently: keep the old spelling as an alias."""
        if names.get(key) not in (None, member):
            self.data.warn(where, f'{name} is already the name of another member; the name was not changed.')
            return
        if not MemberAlias.for_group(self.group.id).filter_by(normalised_name=member.normalised_name).first():
            db.session.add(MemberAlias(group_id=self.group.id, member=member,
                                       normalised_name=member.normalised_name))
        member.display_name, member.normalised_name = name, key

    def _member_for_row(self, code, name, where):
        """The member a Contributions or Payouts row refers to, by ID then by name."""
        if code and code in self.by_code:
            return self.by_code[code]
        if code:
            self.data.warn(where, f'Member ID {code} is not on the Members sheet.')
        if name:
            key = normalise_name(name)
            for member in self.by_code.values():
                if member.normalised_name == key:
                    return member
            return Member.for_group(self.group.id).filter_by(normalised_name=key).first()
        return None

    # ==================== RATES ====================

    def store_rates(self):
        Rate.for_group(self.group.id).delete()
        db.session.add_all(Rate(group_id=self.group.id, effective_from=effective, amount=amount)
                           for effective, amount in self.data.rates)
        self.rates = self.data.rates

    def rate_for(self, year, month):
        first = date(year, month, 1)
        current = None
        for effective, amount in self.rates:
            if effective <= first:
                current = amount
        return current

    # ==================== CONTRIBUTIONS ====================

    def store_contributions(self) -> set:
        """Store every month with at least one payment; return those (year, month) pairs."""
        synced = set()
        self.year_totals = defaultdict(float)
        self.month_totals = {}
        for year, rows in sorted(self.data.contributions.items()):
            sheet = f'Contributions {year}'
            members = {}           # Member → (row number, {month: amount})
            for row in rows:
                where = f'{sheet} row {row.row}'
                member = self._member_for_row(row.code, row.name, where)
                if member is None:
                    if row.amounts:
                        self.data.warn(where, 'Could not tell which member this is, so it was skipped.')
                    continue
                if member in members:
                    self.data.warn(where, f'{member.display_name} is also on row {members[member][0]}; '
                                          'the amounts were added together.')
                    for month, amount in row.amounts.items():
                        members[member][1][month] = members[member][1].get(month, 0) + amount
                else:
                    members[member] = (row.row, dict(row.amounts))

            missing = [m for m in self.by_code.values() if m not in members
                       and any(m.is_member_in(year, mo) for mo in range(1, 13))]
            for member in missing:
                self.data.warn(sheet, f'{member.code} {member.display_name} is a member in {year} '
                                      'but has no row; they are counted as unpaid.')
                members[member] = (None, {})

            for month in range(1, 13):
                if not any(month in amounts for _, amounts in members.values()):
                    continue      # not collected yet
                self._store_month(year, month, members, sheet)
                synced.add((year, month))
        return synced

    def _store_month(self, year, month, members, sheet):
        rate = self.rate_for(year, month)
        month_name = calendar.month_name[month]
        Contribution.for_group(self.group.id).filter_by(year=year, month=month).delete()

        total = paid = unpaid = 0
        for member, (row, amounts) in members.items():
            amount = amounts.get(month)
            if not member.is_member_in(year, month):
                if amount:
                    self.data.warn(f'{sheet} row {row}, {month_name}',
                                   f'{member.display_name} paid {_money(amount)} outside their '
                                   'Joined / Left months.')
                else:
                    continue    # not a member yet (or any more): not a defaulter
            amount = amount or 0.0
            status = status_for(amount, rate)
            db.session.add(Contribution(group_id=self.group.id, member_id=member.id, year=year,
                                        month=month, amount=amount, status=status, synced_at=self.now))
            if amount > 0:
                total += amount
                paid += 1
            else:
                unpaid += 1

        self.year_totals[year] += total
        self.month_totals[(year, month)] = (total, paid, unpaid)

    # ==================== PAYOUTS ====================

    def store_payouts(self):
        purposes = {p.name.casefold(): p.name for p in PayoutPurpose.for_group(self.group.id)}
        Payout.for_group(self.group.id).delete()
        seen = {}
        self.payouts = []
        for row in self.data.payouts:
            where = f'{PAYOUTS} row {row.row}'
            member = self._member_for_row(row.code, row.name, where) if (row.code or row.name) else None
            purpose = purposes.get((row.purpose or '').casefold())
            if purpose is None:
                self.data.warn(where, f'Purpose {row.purpose!r} is not one of the group\'s payout purposes.'
                               if row.purpose else 'Has no purpose.')
            if row.paid_on > date.today():
                self.data.warn(where, f'The date {row.paid_on:%d %b %Y} is in the future.')
            key = (member.id if member else (row.name or '').casefold(), row.amount, row.paid_on)
            if key in seen:
                self.data.warn(where, f'Looks like a repeat of row {seen[key]} '
                                      '(same member, amount and date).')
            seen[key] = row.row

            payout = Payout(
                group_id=self.group.id, year=row.paid_on.year, paid_on=row.paid_on,
                member_id=member.id if member else None,
                beneficiary=member.display_name if member else row.name,
                purpose=purpose or row.purpose, amount=row.amount, approved_by=row.approved_by,
                notes=row.notes, sheet_row=row.row, synced_at=self.now,
            )
            db.session.add(payout)
            self.payouts.append(payout)

    # ==================== BALANCES ====================

    def store_balances(self, synced_months):
        """Yearly balances from the first year's opening, and each synced month's summary."""
        payouts_by_year = defaultdict(float)
        for p in self.payouts:
            payouts_by_year[p.year] += p.amount

        years = sorted(set(self.data.contributions) | set(payouts_by_year))
        if not years:
            return
        YearSummary.for_group(self.group.id).filter(YearSummary.year.notin_(years)).delete()

        sheet = self.data.summary
        first = sheet.get(years[0], {}).get('opening')
        if first is None:
            self.data.warn(SUMMARY, f'No opening balance for {years[0]}; 0 was used.')
        opening = first or 0.0
        openings = {}

        for year in years:
            contributions, payouts = self.year_totals.get(year, 0.0), payouts_by_year[year]
            closing = opening + contributions - payouts
            openings[year] = opening
            figures = sheet.get(year, {})
            self._check_summary(year, figures, opening, contributions, payouts, closing, first_year=years[0])

            summary = YearSummary.for_group(self.group.id).filter_by(year=year).first()
            if summary is None:
                summary = YearSummary(group_id=self.group.id, year=year)
                db.session.add(summary)
            summary.opening_balance, summary.total_contributions = opening, contributions
            summary.total_payouts, summary.closing_balance = payouts, closing
            summary.sheet_opening, summary.sheet_closing = figures.get('opening'), figures.get('closing')
            summary.synced_at = self.now
            opening = closing

        for year, month in synced_months:
            total, paid, unpaid = self.month_totals[(year, month)]
            month_end = date(year, month, calendar.monthrange(year, month)[1])
            dispensed = sum(p.amount for p in self.payouts if (p.paid_on.year, p.paid_on.month) == (year, month))
            balance = (
                openings[year]
                + sum(t for (y, m), (t, _, _) in self.month_totals.items() if y == year and m <= month)
                - sum(p.amount for p in self.payouts if p.year == year and p.paid_on <= month_end)
            )
            summary = PeriodSummary.for_group(self.group.id).filter_by(year=year, month=month).first()
            if summary is None:
                summary = PeriodSummary(group_id=self.group.id, year=year, month=month)
                db.session.add(summary)
            summary.total_contributions, summary.contributors_count = total, paid
            summary.defaulters_count, summary.money_dispensed = unpaid, dispensed
            summary.book_balance, summary.source = balance, 'standard'
            summary.synced_at = self.now

    def _check_summary(self, year, figures, opening, contributions, payouts, closing, first_year):
        """Warn where the Summary sheet disagrees with the calculation."""
        if not figures:
            return
        checks = [('contributions', contributions, 'contributions'), ('payouts', payouts, 'payouts'),
                  ('closing', closing, 'closing balance')]
        if year != first_year:
            sheet_opening = figures.get('opening')
            if sheet_opening is not None and abs(sheet_opening - opening) > _TOLERANCE:
                self.data.warn(f'{SUMMARY} {year}', f'Opening balance is {_money(sheet_opening)}, but '
                                                    f'{year - 1} closed at {_money(opening)}.')
        for key, calculated, label in checks:
            value = figures.get(key)
            if value is not None and abs(value - calculated) > _TOLERANCE:
                self.data.warn(f'{SUMMARY} {year}', f'The sheet shows {label} of {_money(value)}, '
                                                    f'but the app calculates {_money(calculated)}.')
