# app/services/public_access.py
"""
What a group's public pages may show, and who may see it.

  Access code   one shared code per group (on by default), entered once and
                remembered in the visitor's session. It guards the paid list.
  Paid list     members whose month is paid. Members who haven't paid are
                never listed, and nothing on the page names them.
  PIN lookup    a member's own history by name and PIN. Every failure gives
                the same answer and takes about as long, so it doesn't reveal
                which names exist or have a PIN. After MAX_FAILED wrong PINs a
                name is locked; each lock lasts twice as long as the last.
"""
import hmac
from datetime import datetime, timedelta

from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.member import PAID, Contribution, Member, MemberAlias, PeriodSummary, normalise_name

MAX_FAILED = 5
FIRST_LOCK = timedelta(minutes=15)
LONGEST_LOCK = timedelta(hours=24)
_DUMMY_PIN_HASH = generate_password_hash('not-a-real-pin')


# ==================== ACCESS CODE ====================

def needs_code(group) -> bool:
    s = group.settings
    return bool(s and s.access_code_enabled and s.access_code) and not session.get(_key(group))


def try_code(group, code: str) -> bool:
    """Check a submitted code; on success the session remembers it."""
    expected = (group.settings.access_code or '').upper()
    given = ''.join((code or '').split()).upper()
    if expected and hmac.compare_digest(given.encode(), expected.encode()):
        session[_key(group)] = True
        return True
    return False


def _key(group):
    return f'group_access_{group.id}'


# ==================== PAID LIST ====================

def browsable_months(group) -> list:
    """Synced (year, month) pairs the public may browse, newest first."""
    summaries = (PeriodSummary.for_group(group.id)
                 .order_by(PeriodSummary.year.desc(), PeriodSummary.month.desc())
                 .with_entities(PeriodSummary.year, PeriodSummary.month).all())
    if not summaries:
        return []
    latest_year, latest_month = summaries[0]
    back = max(group.settings.public_months_back or 1, 1)
    oldest = (latest_year * 12 + latest_month - 1) - (back - 1)
    return [(y, m) for y, m in summaries if y * 12 + m - 1 >= oldest]


def paid_list(group, year: int, month: int) -> dict:
    """Who paid in the month (fully, by money or credit), and the month's summary."""
    rows = (Contribution.for_group(group.id).filter_by(year=year, month=month, status=PAID)
            .join(Member).order_by(Member.display_name).all())
    summary = PeriodSummary.for_group(group.id).filter_by(year=year, month=month).first()
    return {
        'members': [{'name': c.member.display_name, 'amount': c.credited} for c in rows],
        'total': summary.total_contributions if summary else 0.0,
        'synced_at': summary.synced_at if summary else None,
    }


def last_updated(group):
    latest = PeriodSummary.for_group(group.id).order_by(PeriodSummary.synced_at.desc()).first()
    return latest.synced_at if latest else None


# ==================== PIN LOOKUP ====================

def lookup(group, name: str, pin: str):
    """The member with this name and PIN, or None for any failure (see module notes)."""
    member = _member_named(group, name)
    now = datetime.utcnow()
    if member is None or not member.pin_hash or (member.pin_locked_until and member.pin_locked_until > now):
        check_password_hash(_DUMMY_PIN_HASH, pin or '')       # same work as a real check
        return None

    if check_password_hash(member.pin_hash, (pin or '').strip()):
        member.pin_failed_attempts, member.pin_lockouts, member.pin_locked_until = 0, 0, None
        db.session.commit()
        return member

    member.pin_failed_attempts += 1
    if member.pin_failed_attempts >= MAX_FAILED:
        member.pin_lockouts += 1
        member.pin_locked_until = now + min(FIRST_LOCK * 2 ** (member.pin_lockouts - 1), LONGEST_LOCK)
        member.pin_failed_attempts = 0
    db.session.commit()
    return None


def _member_named(group, name):
    key = normalise_name(name)
    if not key:
        return None
    member = Member.for_group(group.id).filter_by(normalised_name=key, is_active=True).first()
    if member is None:
        alias = MemberAlias.for_group(group.id).filter_by(normalised_name=key).first()
        member = alias.member if alias and alias.member.is_active else None
    return member
