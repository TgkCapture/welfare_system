# app/services/member_service.py
"""
Officer actions on members: rename, merge two records of one person, the
personal history link and the lookup PIN, plus the history itself.

PINs are random, shown to the officer once, and stored only as a hash.
"""
import secrets
from collections import defaultdict

from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models.ledger import Payout
from app.models.member import (
    PAID, PARTIAL, UNPAID,
    Contribution, Member, MemberAlias, MemberYear, PeriodSummary, new_history_token, normalise_name,
    tidy_name,
)
from app.services.name_matching import may_be_same_person

PIN_LENGTH = 6
_STATUS_RANK = {UNPAID: 0, PARTIAL: 1, PAID: 2}


class MemberError(ValueError):
    """An action that can't be done, with a message for the officer."""


# ==================== NAMES ====================

def rename(member, name: str) -> None:
    """Change the display name; the old spelling stays as an alias for matching."""
    name = tidy_name(name)
    key = normalise_name(name)
    if not key or len(name) > 150:
        raise MemberError('A name of up to 150 characters is needed.')
    if key != member.normalised_name:
        other = Member.for_group(member.group_id).filter(
            Member.normalised_name == key, Member.id != member.id).first()
        alias = MemberAlias.for_group(member.group_id).filter_by(normalised_name=key).first()
        if other or (alias and alias.member_id != member.id):
            owner = other or alias.member
            raise MemberError(f'{owner.display_name} already uses that name. Merge the two instead.')
        if alias:
            db.session.delete(alias)          # the name becomes the main one again
            db.session.flush()
        old_key, member.normalised_name = member.normalised_name, key
        _add_alias(member, old_key)
    member.display_name = name
    db.session.commit()


def remove_alias(alias) -> None:
    db.session.delete(alias)
    db.session.commit()


def possible_duplicates(member) -> list:
    """Other members of the group whose name may be another spelling of this one's."""
    return [
        other for other in Member.for_group(member.group_id).filter(Member.id != member.id)
        .order_by(Member.display_name)
        if may_be_same_person(member.normalised_name, other.normalised_name)
    ]


# ==================== MERGE ====================

def merge(source, target) -> list:
    """Fold *source* into *target* (two records of one person) and delete *source*.

    Contributions, credit and payouts move to *target*; a month both have is
    added together. *source*'s names become aliases of *target*. Returns notes
    for the officer.
    """
    if source.id == target.id or source.group_id != target.group_id:
        raise MemberError('Choose a different member of your group to merge into.')
    group_id, notes = target.group_id, []

    touched = set()
    for c in Contribution.for_group(group_id).filter_by(member_id=source.id).all():
        same = Contribution.for_group(group_id).filter_by(
            member_id=target.id, year=c.year, month=c.month).first()
        if same:
            same.amount += c.amount
            same.credit_used = (same.credit_used or 0) + (c.credit_used or 0)
            same.status = max(same.status, c.status, key=_STATUS_RANK.get)
            db.session.delete(c)
            touched.add((c.year, c.month))
        else:
            c.member_id = target.id

    for y in MemberYear.for_group(group_id).filter_by(member_id=source.id).all():
        same = MemberYear.for_group(group_id).filter_by(member_id=target.id, year=y.year).first()
        if same:
            same.credit_in += y.credit_in
            same.excess_paid += y.excess_paid
            same.credit_out += y.credit_out
            db.session.delete(y)
        else:
            y.member_id = target.id

    Payout.for_group(group_id).filter_by(member_id=source.id).update(
        {'member_id': target.id, 'beneficiary': target.display_name})

    old_names = [source.normalised_name] + [a.normalised_name for a in source.aliases]
    for alias in list(source.aliases):
        db.session.delete(alias)
    db.session.flush()
    for key in old_names:
        _add_alias(target, key)

    # Membership covers both records: the earlier join and the later leave
    target.joined_on = None if not (source.joined_on and target.joined_on) else min(source.joined_on, target.joined_on)
    target.left_on = None if not (source.left_on and target.left_on) else max(source.left_on, target.left_on)
    target.is_active = target.is_active or source.is_active

    if source.code:
        if target.code:
            notes.append(f'{source.display_name} had Member ID {source.code} in the workbook. Delete that '
                         f'row from the Members sheet and use {target.code}, or the next sync will add '
                         'them back as a separate member.')
        else:
            code, source.code = source.code, None
            db.session.flush()
            target.code = code

    db.session.delete(source)
    db.session.flush()
    for year, month in touched:
        _recount(group_id, year, month)
    db.session.commit()
    return notes


def _recount(group_id, year, month):
    """Recount paid and unpaid members for a month after two records became one."""
    summary = PeriodSummary.for_group(group_id).filter_by(year=year, month=month).first()
    if summary is None:
        return
    statuses = [c.status for c in Contribution.for_group(group_id).filter_by(year=year, month=month)]
    summary.contributors_count = sum(s != UNPAID for s in statuses)
    summary.defaulters_count = sum(s == UNPAID for s in statuses)


def _add_alias(member, key):
    exists = MemberAlias.for_group(member.group_id).filter_by(normalised_name=key).first()
    if key and key != member.normalised_name and not exists:
        db.session.add(MemberAlias(group_id=member.group_id, member=member, normalised_name=key))


# ==================== LINK AND PIN ====================

def regenerate_link(member) -> None:
    """A new personal link; the old one stops working."""
    member.history_token = new_history_token()
    db.session.commit()


def new_pin(member) -> str:
    """Set a new random PIN and return it. Only its hash is kept."""
    pin = ''.join(str(secrets.randbelow(10)) for _ in range(PIN_LENGTH))
    member.pin_hash = generate_password_hash(pin)
    member.pin_failed_attempts = 0
    member.pin_locked_until = None
    db.session.commit()
    return pin


def clear_pin(member) -> None:
    member.pin_hash = None
    member.pin_failed_attempts = 0
    member.pin_locked_until = None
    db.session.commit()


# ==================== HISTORY ====================

def history(member) -> list:
    """The member's months by year, newest year first.

    Each year: {'year', 'months': [12 × None or {'amount', 'credit', 'status'}],
    'paid', 'credit_in', 'excess', 'credit_out'}.
    """
    years = defaultdict(lambda: {'months': [None] * 12, 'paid': 0.0,
                                 'credit_in': 0.0, 'excess': 0.0, 'credit_out': 0.0})
    for c in Contribution.for_group(member.group_id).filter_by(member_id=member.id):
        years[c.year]['months'][c.month - 1] = {'amount': c.amount, 'credit': c.credit_used or 0,
                                                'status': c.status}
        years[c.year]['paid'] += max(c.amount, 0)
    for y in MemberYear.for_group(member.group_id).filter_by(member_id=member.id):
        years[y.year].update(credit_in=y.credit_in, excess=y.excess_paid, credit_out=y.credit_out)
        years[y.year]['paid'] += y.excess_paid
    return [{'year': year, **years[year]} for year in sorted(years, reverse=True)]
