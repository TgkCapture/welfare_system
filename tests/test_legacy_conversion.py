"""
Converting an old Mzugoss-layout workbook to the standard layout, using
the synthetic workbook that mirrors MGSS.xlsx.
"""
import csv
from datetime import date

import pytest
from openpyxl import Workbook, load_workbook

from app.services.legacy_conversion import UNSPECIFIED, LegacyConverter
from app.services.name_matching import short_form as _short_form
from app.services.standard_workbook import StandardWorkbook
from app.services.workbook_template import write_workbook
from tests.workbooks import MONTHS

TODAY = date(2026, 6, 15)


def _convert(path, **kw):
    return LegacyConverter(str(path), 'Test Welfare', today=TODAY, **kw).convert()


def _members(conversion):
    return {m.name: m for m in conversion.spec.members}


def _legacy_book(path, years):
    """A minimal old-layout workbook: years = {year: (carry_over, [(name, {month: amount}, [payouts])])}."""
    wb = Workbook()
    wb.remove(wb.active)
    for year, (carry_over, rows) in years.items():
        ws = wb.create_sheet(str(year))
        ws['A2'], ws['A3'], ws['A4'], ws['B4'] = 'MONEY DISPENSED', 'TOTAL BOOK BALANCE', 'Carry Over', carry_over
        ws.cell(6, 1, 'Name')
        for i, month in enumerate(MONTHS, start=2):
            ws.cell(6, i, month)
        ws.cell(6, 15, 'DISPENSED TO')
        for r, (name, paid, payouts) in enumerate(rows, start=7):
            ws.cell(r, 1, name)
            for i, month in enumerate(MONTHS, start=2):
                if month in paid:
                    ws.cell(r, i, paid[month])
            for offset, amount in enumerate(payouts):
                ws.cell(r, 15 + offset, amount)
        ws.cell(7 + len(rows) + 1, 1, 'Total')
    wb.save(path)
    return path


# ==================== CONVERSION ====================

def test_reads_year_sheets_and_ignores_the_rest(app, mzugoss_workbook):
    conversion = _convert(mzugoss_workbook)

    assert conversion.spec.years == [2025, 2026]
    assert 'Ignored sheets: Old (visible), August (hidden), Septmber (hidden), October (hidden).' in conversion.review


def test_members_get_ids_and_joined_left_guesses(app, mzugoss_workbook):
    members = _members(_convert(mzugoss_workbook))

    assert [m.code for m in members.values()][:2] == ['M001', 'M002']
    assert members['Alinafe Banda'].joined is None                 # on the first sheet
    assert members['Chisomo Mwale'].joined == date(2026, 1, 1)     # first payment
    assert members['Gift Nyirenda'].joined == date(2026, 4, 1)     # double space tidied; paid from April
    assert members['Esther Tembo'].joined == date(2026, 1, 1)      # never paid: first sheet
    assert 'Joined guessed' in members['Gift Nyirenda'].notes


def test_contributions_and_text_cells(app, mzugoss_workbook):
    conversion = _convert(mzugoss_workbook)
    code = _members(conversion)['Bright Phiri'].code

    assert conversion.spec.contributions[2026][code] == {1: 1000, 3: 500}
    assert '- 2026 row 11, March: "pending" is not a number and was left out.' in conversion.review


def test_payouts_are_dated_and_marked_unspecified(app, mzugoss_workbook):
    conversion = _convert(mzugoss_workbook)

    payouts = [(p.paid_on, p.amount, p.purpose) for p in conversion.spec.payouts]
    assert payouts == [
        (date(2025, 12, 31), 5000, UNSPECIFIED),
        (TODAY, 20000, UNSPECIFIED), (TODAY, 10000, UNSPECIFIED),   # DISPENSED TO and the column after
    ]
    assert conversion.spec.purposes == [UNSPECIFIED]   # no built-in purposes


def test_purposes_come_from_the_caller(app, mzugoss_workbook):
    conversion = _convert(mzugoss_workbook, purposes=['Funeral condolence', 'unspecified', 'Hospital bill'])
    assert conversion.spec.purposes == ['Funeral condolence', 'Hospital bill', UNSPECIFIED]


def test_a_year_missing_between_two_sheets_gets_an_empty_row(app, tmp_path):
    path = _legacy_book(tmp_path / 'old.xlsx', {
        2023: (0, [('A', {'August': 500}, []), ('B', {'August': 500}, [])]),
        2024: (0, [('A', {'January': 500}, [])]),                          # B paid nothing
        2025: (0, [('A', {'January': 1000}, []), ('B', {'January': 1000}, [])]),
    })

    conversion = _convert(path)
    b = _members(conversion)['B']

    assert b.code in conversion.spec.year_members[2024]
    assert b.code not in conversion.spec.contributions[2024]
    assert (b.joined, b.left) == (None, None)
    assert 'counted as unpaid (paid nothing that year)' in b.notes


def test_rates_follow_the_most_common_payment(app, tmp_path):
    path = _legacy_book(tmp_path / 'old.xlsx', {
        2023: (0, [('A', {'August': 500}, []), ('B', {'August': 500, 'May': 300}, [])]),
        2024: (0, [('A', {'January': 500}, []), ('B', {'January': 500}, [])]),
        2025: (0, [('A', {'January': 1000}, []), ('B', {'January': 1000, 'March': 500}, [])]),
    })
    # The first rate starts when payments started (May); later changes from January
    assert _convert(path).spec.rates == [(date(2023, 5, 1), 500), (date(2025, 1, 1), 1000)]


def test_excess_notes_become_the_excess_column(app, tmp_path):
    path = _legacy_book(tmp_path / 'old.xlsx', {
        2025: (0, [('A', {m: 1000 for m in MONTHS}, []), ('B', {'January': 1000}, [])]),
    })
    wb = load_workbook(path)
    wb['2025']['N7'] = '1,500N'        # A paid 1,500 beyond the year
    wb['2025']['N8'] = 'call him'      # any other note is just listed
    wb.save(path)

    conversion = _convert(path)

    assert conversion.spec.excess[2025] == {'M001': 1500}
    assert '- 2025 row 7: A paid 1,500 extra, carried into 2026.' in conversion.review
    assert any('has a note in column N: "call him"' in line for line in conversion.review)
    paid_in = [line for line in conversion.review if line.startswith('| 2025 |')][0]
    assert '| 14,500 |' in paid_in     # 12,000 + 1,000 + the 1,500 excess


@pytest.mark.parametrize('drop', [False, True])
def test_payouts_repeating_the_previous_year(app, tmp_path, drop):
    path = _legacy_book(tmp_path / 'old.xlsx', {
        2024: (0, [('A', {'January': 500}, [4160]), ('B', {'January': 500}, [])]),
        2025: (0, [('A', {'January': 500}, [4160]), ('B', {'January': 500}, [7000])]),
    })

    conversion = _convert(path, drop_repeated_payouts=drop)

    amounts = [(p.paid_on.year, p.amount) for p in conversion.spec.payouts]
    assert amounts == ([(2024, 4160), (2025, 7000)] if drop else [(2024, 4160), (2025, 4160), (2025, 7000)])
    heading = ("Dropped as repeats of the previous year's payout (same member and amount):" if drop else
               "Kept, but they repeat the previous year's payout")
    assert any(line.startswith(heading) for line in conversion.review)


def test_carry_overs_are_calculated_and_differences_reported(app, mzugoss_workbook):
    conversion = _convert(mzugoss_workbook)

    assert conversion.spec.opening_balance == 40000          # the first sheet's carry-over
    balances = [line for line in conversion.review if line.startswith('| 2026 |')]
    # 2025 closes at 40,000 + 1,000 − 5,000; the old 2026 sheet typed 120,000
    assert balances[0].startswith('| 2026 | 36,000 |')
    assert 'carry-over 120,000' in balances[0]


def test_confirmed_merges_join_two_spellings(app, tmp_path):
    path = _legacy_book(tmp_path / 'old.xlsx', {
        2024: (0, [('Steven Ngoma', {'January': 500}, []), ('Ann', {'January': 500}, [])]),
        2025: (0, [('Steve Ngoma', {'January': 500}, []), ('Ann', {'January': 500}, [])]),
    })

    unmerged = _convert(path)
    assert [(k, m) for k, m, *_ in unmerged.suggestions] == [('Steven Ngoma', 'Steve Ngoma')]
    assert len(unmerged.spec.members) == 3

    merged = _convert(path, merges={'Steve Ngoma': 'Steven Ngoma'})
    steven = _members(merged)['Steven Ngoma']
    assert len(merged.spec.members) == 2
    assert (steven.joined, steven.left) == (None, None)
    assert merged.spec.contributions[2025][steven.code] == {1: 500}

    # The kept spelling is used even when the other was seen first
    reverse = _convert(path, merges={'Steven Ngoma': 'Steve Ngoma'})
    assert 'Steve Ngoma' in _members(reverse) and 'Steven Ngoma' not in _members(reverse)


def test_names_on_the_same_sheet_are_never_suggested(app, tmp_path):
    path = _legacy_book(tmp_path / 'old.xlsx', {
        2025: (0, [('Steve Ngoma', {'January': 500}, []), ('Steven Ngoma', {'January': 500}, [])]),
    })
    assert _convert(path).suggestions == []


@pytest.mark.parametrize('a,b,expected', [
    ('chiso mwale', 'chisomo mwale', True),
    ('wapozga', 'wapozga munyenyembe', True),
    ('agness', 'agnes nomsa', True),
    ('banda ann', 'ann banda', True),
    ('ann banda', 'ann banda', False),
    ('fetch mkandawire', 'funny mkandawire', False),
    ('jo', 'john phiri', False),
])
def test_short_form(a, b, expected):
    assert _short_form(a, b) is expected


def test_converted_workbook_is_a_standard_workbook(app, group, mzugoss_workbook, tmp_path):
    path = tmp_path / 'standard.xlsx'
    write_workbook(_convert(mzugoss_workbook).spec).save(path)

    assert StandardWorkbook.is_standard(str(path))
    wb = load_workbook(path)
    assert wb.sheetnames == ['Read me', 'Members', 'Contributions 2025', 'Contributions 2026',
                             'Payouts', 'Rates', 'Summary', 'Lists']
    assert wb['Summary']['B2'].value == 40000
    assert wb['Summary']['B3'].value == '=E2'      # carried over, not typed


# ==================== CLI ====================

def test_cli_converts_checks_and_applies_merges(app, mzugoss_workbook, tmp_path):
    out = tmp_path / 'out'
    runner = app.test_cli_runner()

    result = runner.invoke(args=['convert-legacy-workbook', str(mzugoss_workbook), '--out-dir', str(out)])

    assert 'Check: 0 month(s) differ from the old sheet' in result.output, result.output
    review = (out / 'mzugoss_review.md').read_text(encoding='utf-8')
    assert "Every month's total paid in matches the old sheet." in review
    assert (out / 'mzugoss_standard.xlsx').exists()

    # Confirming a suggestion merges it on the next run
    with open(out / 'merges.csv', 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(['keep', 'merge', 'similarity', 'keep_years', 'merge_years', 'confirm'])
        writer.writerow(['Alinafe Banda', 'Bright Phiri', 0, '', '', 'yes'])
        writer.writerow(['Alinafe Banda', 'Chisomo Mwale', 0, '', '', ''])        # not confirmed
    result = runner.invoke(args=['convert-legacy-workbook', str(mzugoss_workbook), '--out-dir', str(out),
                                 '--merges', str(out / 'merges.csv')])
    review = (out / 'mzugoss_review.md').read_text(encoding='utf-8')
    assert 'Merged as confirmed: Bright Phiri → Alinafe Banda.' in review
    names = [load_workbook(out / 'mzugoss_standard.xlsx')['Members'].cell(r, 2).value for r in range(2, 9)]
    assert 'Bright Phiri' not in names and 'Chisomo Mwale' in names


def test_cli_uses_the_groups_purposes(app, group, mzugoss_workbook, tmp_path):
    from app.extensions import db
    from app.models.ledger import PayoutPurpose
    db.session.add(PayoutPurpose(group_id=group.id, name='Hospital bill'))
    db.session.commit()

    app.test_cli_runner().invoke(args=['convert-legacy-workbook', str(mzugoss_workbook), '--out-dir',
                                       str(tmp_path), '--group', 'mzugoss', '--purpose', 'School fees'])

    lists = load_workbook(tmp_path / 'mzugoss_standard.xlsx')['Lists']
    assert [c.value for c in lists['A'][1:]] == ['Hospital bill', 'School fees', UNSPECIFIED]
