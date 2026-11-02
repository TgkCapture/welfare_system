# app/services/period_store.py
"""
Stores each sync's results and reads them back for reports.

A sync replaces the group's stored contributions and summary for the
synced month: the spreadsheet is the source of truth, the DB a mirror of
its latest state. Members are matched by normalised name, then by alias.
Names that match nobody become new members and are reported back, so an
officer can merge them into an existing member if they are a respelling.
"""
import calendar
from datetime import datetime

import pandas as pd

from app.extensions import db
from app.models.member import (
    PAID, PARTIAL, UNPAID,
    Contribution, Member, MemberAlias, PeriodSummary, normalise_name, tidy_name,
)

NAME_COL = 'Name'


def status_for(amount: float, rate: float = None) -> str:
    """Payment status of *amount* against the monthly *rate*.

    Without a known rate, any amount above zero counts as paid.
    """
    if amount is None or amount <= 0:
        return UNPAID
    if rate and amount < rate:
        return PARTIAL
    return PAID


def month_number(month) -> int:
    """1–12 from a month number or an English month name."""
    if isinstance(month, int):
        return month
    return list(calendar.month_name).index(str(month).strip().capitalize())


class PeriodStore:

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    @staticmethod
    def sync(group, parsed: dict, user=None, source: str = 'upload', rate: float = None) -> dict:
        """Store one month of parsed contributions for *group*.

        *parsed* is ExcelParser output: a DataFrame plus its name and
        month columns, the year and month, and the sheet's financial rows.
        """
        year, month = int(parsed['year']), month_number(parsed['month'])
        df, name_col, month_col = parsed['data'], parsed['name_col'], parsed['month_col']

        lookup = PeriodStore._member_lookup(group.id)
        amounts, order, new_members, repeated = {}, [], [], []

        for _, row in df.iterrows():
            display = tidy_name(row[name_col])
            key = normalise_name(display)
            if not key:
                continue

            member = lookup.get(key)
            if member is None:
                member = Member(group_id=group.id, display_name=display, normalised_name=key)
                db.session.add(member)
                lookup[key] = member
                new_members.append(display)

            amount = row[month_col]
            amount = 0.0 if pd.isna(amount) else float(amount)
            if member in amounts:
                # The same person twice in one month: add the rows up
                repeated.append(display)
                amounts[member] += amount
            else:
                amounts[member] = amount
                order.append(member)

        db.session.flush()   # new members get their ids

        now = datetime.utcnow()
        Contribution.for_group(group.id).filter_by(year=year, month=month).delete()
        db.session.add_all(
            Contribution(group_id=group.id, member_id=m.id, year=year, month=month,
                         amount=amounts[m], status=status_for(amounts[m], rate), synced_at=now)
            for m in order
        )

        paid = [a for a in amounts.values() if a > 0]
        summary = PeriodSummary.for_group(group.id).filter_by(year=year, month=month).first()
        if summary is None:
            summary = PeriodSummary(group_id=group.id, year=year, month=month)
            db.session.add(summary)
        summary.total_contributions = float(sum(paid))
        summary.contributors_count = len(paid)
        summary.defaulters_count = len(amounts) - len(paid)
        summary.money_dispensed = parsed.get('money_dispensed')
        summary.book_balance = parsed.get('total_book_balance')
        summary.source = source
        summary.synced_by = user.id if user else None
        summary.synced_at = now

        db.session.commit()
        return {
            'year': year,
            'month': month,
            'summary': summary,
            'new_members': new_members,
            'repeated_names': repeated,
        }

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def report_data(group_id: int, year: int, month: int):
        """The stored month in the shape the PDF and image generators expect.

        Returns None if the month has never been synced.
        """
        summary = PeriodSummary.for_group(group_id).filter_by(year=year, month=month).first()
        if summary is None:
            return None

        rows = PeriodStore._rows(group_id, year, month)
        month_name = calendar.month_name[month]
        return {
            'data': pd.DataFrame(
                [(c.member.display_name, c.amount) for c in rows],
                columns=[NAME_COL, month_name],
            ),
            'name_col':            NAME_COL,
            'month_col':           month_name,
            'month':               month_name,
            'year':                year,
            'total_contributions': summary.total_contributions,
            'num_contributors':    summary.contributors_count,
            'num_missing':         summary.defaulters_count,
            'defaulters':          [c.member.display_name for c in rows if c.status == UNPAID],
            'money_dispensed':     summary.money_dispensed,
            'total_book_balance':  summary.book_balance,
            'synced_at':           summary.synced_at,
        }

    @staticmethod
    def paid_members(group_id: int, year: int, month: int) -> list:
        """Members who paid something in the month, in sheet order."""
        return [
            {'name': c.member.display_name, 'amount': c.amount,
             'status': 'Partial' if c.status == PARTIAL else 'Paid'}
            for c in PeriodStore._rows(group_id, year, month)
            if c.status != UNPAID
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rows(group_id, year, month):
        return (
            Contribution.for_group(group_id)
            .filter_by(year=year, month=month)
            .order_by(Contribution.id)   # inserted in sheet order
            .all()
        )

    @staticmethod
    def _member_lookup(group_id) -> dict:
        """normalised name → Member, from names and aliases."""
        lookup = {m.normalised_name: m for m in Member.for_group(group_id)}
        for alias in MemberAlias.for_group(group_id):
            lookup.setdefault(alias.normalised_name, alias.member)
        return lookup
