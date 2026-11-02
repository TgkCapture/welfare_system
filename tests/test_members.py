"""
The Members screen (rename, merge, retire, personal link, PIN) and the
public personal history page.
"""
import pandas as pd
import pytest
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models.ledger import Payout, SyncRun
from app.models.member import (
    PAID, PARTIAL, UNPAID, Contribution, Member, MemberAlias, MemberYear, PeriodSummary, normalise_name,
)
from app.services import member_service
from app.services.member_service import MemberError
from app.services.period_store import PeriodStore


def _parsed(rows, month='March', year=2026):
    return {'data': pd.DataFrame(rows, columns=['Name', month]), 'name_col': 'Name',
            'month_col': month, 'year': year, 'month': month}


def _member(group, name):
    return Member.for_group(group.id).filter_by(normalised_name=normalise_name(name)).one()


@pytest.fixture
def officer(client, make_user, login):
    make_user(email='t@example.com', role='Treasurer')     # has manage_members
    login('t@example.com')


# ==================== LIST AND SEARCH ====================

def test_members_list_and_search(client, group, officer):
    PeriodStore.sync(group, _parsed([('Ann Banda', 1000), ('Ben Phiri', 0)]))
    ann = _member(group, 'Ann Banda')
    db.session.add(MemberAlias(group_id=group.id, member_id=ann.id, normalised_name='annie banda'))
    db.session.commit()

    page = client.get('/members').data
    assert b'Ann Banda' in page and b'Ben Phiri' in page
    found = client.get('/members?q=annie').data      # matches an alias
    assert b'Ann Banda' in found and b'Ben Phiri' not in found


def test_new_members_from_a_sync(client, group, officer):
    PeriodStore.sync(group, _parsed([('Ann Banda', 1000)]))
    run = SyncRun(group_id=group.id, details={'new_members': ['Ben Phiri']}, warnings=[])
    db.session.add(run)
    db.session.commit()
    PeriodStore.sync(group, _parsed([('Ann Banda', 1000), ('Ben Phiri', 1000)]))

    page = client.get(f'/members?run={run.id}').data
    assert b'Ben Phiri' in page and b'Ann Banda' not in page


def test_members_screen_needs_manage_members(client, group, make_user, login):
    make_user(email='sec@example.com', role='Secretary')
    login('sec@example.com')
    assert client.get('/members').status_code != 200


# ==================== RENAME ====================

def test_rename_keeps_the_old_spelling_for_matching(client, group, officer):
    PeriodStore.sync(group, _parsed([('Gift Nyirenda', 1000)]))
    gift = _member(group, 'Gift Nyirenda')

    client.post(f'/members/{gift.id}/rename', data={'name': 'Gift  N. Nyirenda'})

    gift = db.session.get(Member, gift.id)
    assert gift.display_name == 'Gift N. Nyirenda'
    result = PeriodStore.sync(group, _parsed([('Gift Nyirenda', 500)], month='April'))
    assert result['new_members'] == []


def test_rename_to_another_members_name_is_refused(app, group):
    PeriodStore.sync(group, _parsed([('Ann Banda', 1000), ('Ben Phiri', 0)]))
    with pytest.raises(MemberError, match='Merge the two instead'):
        member_service.rename(_member(group, 'Ben Phiri'), 'ann banda')


# ==================== MERGE ====================

def test_merge_moves_everything_and_keeps_the_names(client, group, officer):
    PeriodStore.sync(group, _parsed([('Steven Ngoma', 1000), ('Ann', 1000)], month='February'))
    PeriodStore.sync(group, _parsed([('Steve Ngoma', 1000), ('Ann', 1000)]))
    steven, steve = _member(group, 'Steven Ngoma'), _member(group, 'Steve Ngoma')
    steven_id, steve_id = steven.id, steve.id
    db.session.add(Payout(group_id=group.id, year=2026, member_id=steven_id, beneficiary='Steven Ngoma',
                          amount=5000))
    db.session.add(MemberYear(group_id=group.id, member_id=steven_id, year=2025, credit_out=500))
    db.session.commit()

    # The detail page suggests the likely match
    assert b'Possibly the same person' in client.get(f'/members/{steven_id}').data

    response = client.post(f'/members/{steven_id}/merge', data={'into': steve_id})

    assert response.headers['Location'] == f'/members/{steve_id}'
    assert Member.query.filter_by(id=steven_id).first() is None
    steve = db.session.get(Member, steve_id)
    assert {(c.month, c.amount) for c in steve.contributions} == {(2, 1000), (3, 1000)}
    assert Payout.for_group(group.id).one().beneficiary == 'Steve Ngoma'
    assert MemberYear.for_group(group.id).one().member_id == steve.id
    # Old spelling now matches the kept member
    assert PeriodStore.sync(group, _parsed([('Steven Ngoma', 1000)], month='April'))['new_members'] == []


def test_merge_adds_up_a_month_both_records_have(app, group):
    PeriodStore.sync(group, _parsed([('Ann', 500), ('Annie', 500), ('Ben', 0)]))
    ann, annie = _member(group, 'Ann'), _member(group, 'Annie')
    for c in Contribution.for_group(group.id).filter(Contribution.member_id.in_([ann.id, annie.id])):
        c.status = PARTIAL
    db.session.commit()

    member_service.merge(annie, ann)

    month = Contribution.for_group(group.id).filter_by(member_id=ann.id).one()
    assert (month.amount, month.status) == (1000, PARTIAL)
    summary = PeriodSummary.for_group(group.id).one()
    assert (summary.contributors_count, summary.defaulters_count, summary.total_contributions) == (1, 1, 1000)


def test_merge_with_two_member_ids_warns_about_the_workbook(client, group, officer):
    PeriodStore.sync(group, _parsed([('Steven Ngoma', 1000), ('Steve Ngoma', 1000)]))
    steven, steve = _member(group, 'Steven Ngoma'), _member(group, 'Steve Ngoma')
    steven.code, steve.code = 'M030', 'M048'
    db.session.commit()

    client.post(f'/members/{steven.id}/merge', data={'into': steve.id})

    page = client.get(f'/members/{steve.id}').data
    assert b'Member ID M030 in the workbook' in page


def test_merge_takes_the_id_when_the_kept_member_has_none(app, group):
    PeriodStore.sync(group, _parsed([('Steven Ngoma', 1000), ('Steve Ngoma', 1000)]))
    steven, steve = _member(group, 'Steven Ngoma'), _member(group, 'Steve Ngoma')
    steven.code = 'M030'
    db.session.commit()

    assert member_service.merge(steven, steve) == []
    assert db.session.get(Member, steve.id).code == 'M030'


def test_cannot_merge_into_itself_or_another_group(client, group, make_group, officer):
    other = make_group(name='Another Welfare', slug='another')
    PeriodStore.sync(group, _parsed([('Ann', 1000)]))
    PeriodStore.sync(other, _parsed([('Ann', 1000)]))
    ann, theirs = _member(group, 'Ann'), _member(other, 'Ann')

    client.post(f'/members/{ann.id}/merge', data={'into': ann.id})
    client.post(f'/members/{ann.id}/merge', data={'into': theirs.id})

    assert db.session.get(Member, ann.id) is not None
    assert db.session.get(Member, theirs.id).contributions.count() == 1


# ==================== LINK AND PIN ====================

def test_pin_is_shown_once_and_stored_hashed(client, group, officer):
    PeriodStore.sync(group, _parsed([('Ann', 1000)]))
    ann = _member(group, 'Ann')

    response = client.post(f'/members/{ann.id}/pin')

    pin = response.data.decode().split('letter-spacing:.3em;">')[1][:6]
    assert pin.isdigit() and response.headers['Cache-Control'] == 'no-store'
    ann = db.session.get(Member, ann.id)
    assert ann.pin_hash != pin and check_password_hash(ann.pin_hash, pin)
    assert pin.encode() not in client.get(f'/members/{ann.id}').data

    client.post(f'/members/{ann.id}/pin/clear')
    assert db.session.get(Member, ann.id).pin_hash is None


def test_new_pin_unlocks_a_locked_member(app, group):
    PeriodStore.sync(group, _parsed([('Ann', 1000)]))
    ann = _member(group, 'Ann')
    ann.pin_failed_attempts = 5
    db.session.commit()

    member_service.new_pin(ann)

    assert (ann.pin_failed_attempts, ann.pin_locked_until) == (0, None)


def test_personal_link_shows_the_members_history(client, group, officer):
    PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 0)]))
    ann = _member(group, 'Ann')

    detail = client.get(f'/members/{ann.id}').data.decode()
    assert f'/g/mzugoss/m/{ann.history_token}' in detail

    client.get('/auth/logout')
    page = client.get(f'/g/mzugoss/m/{ann.history_token}')
    assert page.status_code == 200
    assert b'Ann' in page.data and b'Ben' not in page.data
    assert page.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert page.headers['Referrer-Policy'] == 'no-referrer'


def test_regenerated_link_replaces_the_old_one(client, group, officer):
    PeriodStore.sync(group, _parsed([('Ann', 1000)]))
    ann = _member(group, 'Ann')
    old = ann.history_token

    client.post(f'/members/{ann.id}/link')

    assert client.get(f'/g/mzugoss/m/{old}').status_code == 404
    assert client.get(f'/g/mzugoss/m/{db.session.get(Member, ann.id).history_token}').status_code == 200


@pytest.mark.parametrize('case', ['wrong token', 'other group', 'retired', 'suspended group'])
def test_personal_link_is_not_found_when_it_should_not_open(client, group, make_group, case):
    other = make_group(name='Another Welfare', slug='another')
    PeriodStore.sync(group, _parsed([('Ann', 1000)]))
    ann = _member(group, 'Ann')
    slug, token = 'mzugoss', ann.history_token
    if case == 'wrong token':
        token = 'x' * 32
    elif case == 'other group':
        slug = 'another'
    elif case == 'retired':
        ann.is_active = False
    else:
        group.is_active = False
    db.session.commit()

    assert client.get(f'/g/{slug}/m/{token}').status_code == 404


def test_history_shows_credit_and_unpaid_months(app, group):
    PeriodStore.sync(group, _parsed([('Ann', 1000), ('Ben', 0)]))
    ann, ben = _member(group, 'Ann'), _member(group, 'Ben')
    db.session.add(MemberYear(group_id=group.id, member_id=ann.id, year=2026, excess_paid=1500, credit_out=1500))
    db.session.commit()

    years = member_service.history(ann)
    assert years[0]['year'] == 2026
    assert years[0]['months'][2] == {'amount': 1000, 'credit': 0, 'status': PAID}
    assert (years[0]['paid'], years[0]['credit_out']) == (2500, 1500)
    assert member_service.history(ben)[0]['months'][2]['status'] == UNPAID
