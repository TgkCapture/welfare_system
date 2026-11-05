"""
Reading workbooks in other layouts: the per-group SheetMapping, the parser
following it, the layout settings page, and reports rebuilt from stored data.
"""
import json

import pytest
from openpyxl import Workbook

from app.extensions import db
from app.models.group import Group
from app.models.ledger import SyncRun
from app.models.report import GeneratedReport
from app.services.excel_parser import ExcelParser
from app.services.sheet_mapping import SheetMapping, column_index, column_letter
from app.services.period_store import PeriodStore

SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _other_layout(path, year=2026, numbered_months=False):
    """Not the Mzugoss layout: a numbered list, names in column B headed 'Member',
    short month headers from column C, header on row 3, totals in E1/F1."""
    wb = Workbook()
    wb.active.title = 'Notes'
    ws = wb.create_sheet(f'Contrib {year}')
    ws['A1'], ws['E1'], ws['F1'] = 'Lilongwe Old Boys', 4000, 90000
    headers = ['No.', 'Member'] + ([str(i) for i in range(1, 13)] if numbered_months else SHORT_MONTHS)
    for col, header in enumerate(headers, start=1):
        ws.cell(3, col, header)
    rows = [(1, 'Ann Banda', {1: 1000, 3: 1000}), (2, 'Ben Phiri', {3: 'owing'}), (3, 'Cara Mwale', {3: 500})]
    for r, (number, name, paid) in enumerate(rows, start=4):
        ws.cell(r, 1, number)
        ws.cell(r, 2, name)
        for month, amount in paid.items():
            ws.cell(r, 2 + month, amount)
    ws.cell(8, 2, 'Total')
    wb.save(path)
    return path


MAPPING = SheetMapping(sheet_pattern='Contrib {year}', header_row=3, name_column='B',
                       financials='cells', money_dispensed_cell='E1', book_balance_cell='F1')


# ==================== SETTINGS ====================

@pytest.mark.parametrize('mapping,problem', [
    (SheetMapping(sheet_pattern='Contributions'), '{year}'),
    (SheetMapping(sheet_mode='named'), 'name of the sheet'),
    (SheetMapping(header_row=0), 'row number'),
    (SheetMapping(name_column='B2'), 'column letter'),
    (SheetMapping(january_column='C'), 'also give the header row'),
    (SheetMapping(financials='cells', money_dispensed_cell='row two'), 'look like B2'),
])
def test_invalid_settings_are_explained(mapping, problem):
    assert any(problem in p for p in mapping.errors())


def test_blank_form_is_automatic():
    assert SheetMapping.from_form({}).is_automatic()
    assert SheetMapping.from_form({'name_column': ' b ', 'header_row': '3'}) == SheetMapping(
        name_column='B', header_row=3)


@pytest.mark.parametrize('letter,index', [('A', 0), ('C', 2), ('Z', 25), ('AA', 26), ('AZ', 51)])
def test_column_letters(letter, index):
    assert column_index(letter) == index and column_letter(index) == letter


# ==================== PARSING ====================

def test_automatic_reading_gets_this_layout_wrong(app, tmp_path):
    """Why the mapping exists: the automatic rules don't find the names here."""
    with pytest.raises(ValueError):
        parsed = ExcelParser.parse_excel(str(_other_layout(tmp_path / 'o.xlsx')), year=2026, month=3)
        assert parsed['data'][parsed['name_col']].tolist() == ['Ann Banda', 'Ben Phiri', 'Cara Mwale']


def test_mapping_reads_another_layout(app, tmp_path):
    parsed = ExcelParser.parse_excel(str(_other_layout(tmp_path / 'o.xlsx')), year=2026, month=3, mapping=MAPPING)

    assert (parsed['sheet'], parsed['name_col'], parsed['month_col']) == ('Contrib 2026', 'Member', 'Mar')
    assert parsed['data']['Member'].tolist() == ['Ann Banda', 'Ben Phiri', 'Cara Mwale']
    assert (parsed['total_contributions'], parsed['num_contributors']) == (1500, 2)
    assert (parsed['money_dispensed'], parsed['total_book_balance']) == (4000, 90000)
    assert parsed['warnings'] == [{'where': "Sheet 'Contrib 2026' cell E5",
                                   'message': "Ben Phiri: 'owing' is not an amount, so it counts as unpaid."}]


def test_january_column_for_untitled_months(app, tmp_path):
    path = _other_layout(tmp_path / 'o.xlsx', numbered_months=True)
    mapping = SheetMapping(sheet_mode='named', sheet_name='contrib 2026', header_row=3,
                           name_column='B', january_column='C', financials='none')

    parsed = ExcelParser.parse_excel(str(path), year=2026, month=1, mapping=mapping)

    assert parsed['data'].iloc[:, 1].tolist()[:1] == [1000]
    assert parsed['money_dispensed'] is None


@pytest.mark.parametrize('mapping,message', [
    (SheetMapping(sheet_pattern='Contrib {year}'), "No sheet named 'Contrib 2025'"),
    (SheetMapping(sheet_mode='named', sheet_name='Ledger'), "No sheet named 'Ledger'"),
    (SheetMapping(sheet_pattern='Contrib {year}', header_row=40), 'has no row 40'),
    (SheetMapping(sheet_pattern='Contrib {year}', header_row=3, name_column='Z'), 'Column Z'),
])
def test_errors_name_what_is_wrong(app, tmp_path, mapping, message):
    year = 2025 if 'Contrib 2025' in message else 2026
    with pytest.raises(ValueError, match=message):
        ExcelParser.parse_excel(str(_other_layout(tmp_path / 'o.xlsx')), year=year, month=3, mapping=mapping)


def test_mzugoss_text_cells_are_warned_with_their_cell(app, mzugoss_workbook):
    parsed = ExcelParser.parse_excel(str(mzugoss_workbook), year=2026, month=3)
    assert parsed['warnings'] == [{'where': "Sheet '2026' cell D11",
                                   'message': "Esther Tembo: 'pending' is not an amount, so it counts as unpaid."}]


# ==================== LAYOUT PAGE ====================

@pytest.fixture
def chair(client, make_user, login):
    make_user(email='chair@example.com')
    login('chair@example.com')


FORM = {'sheet_mode': 'year', 'sheet_pattern': 'Contrib {year}', 'header_row': '3', 'name_column': 'b',
        'financials': 'cells', 'money_dispensed_cell': 'E1', 'book_balance_cell': 'F1',
        'year': '2026', 'month': '3'}


def test_testing_a_sample_shows_what_was_read_and_saves_nothing(client, group, chair, tmp_path):
    path = _other_layout(tmp_path / 'o.xlsx')
    with open(path, 'rb') as fh:
        page = client.post('/settings/workbook-layout', data={**FORM, 'action': 'test', 'file': (fh, 'o.xlsx')},
                           content_type='multipart/form-data').data.decode()

    assert 'Read sheet <strong>Contrib 2026</strong>' in page
    assert 'Ann Banda' in page and "cell E5" in page
    assert db.session.get(Group, group.id).settings.sheet_mapping is None
    assert list((tmp_path.parent).glob('**/uploads/mzugoss/*')) == []   # sample deleted


def test_a_standard_workbook_is_recognised(client, group, chair, tmp_path):
    from app.services.workbook_template import build_template
    path = tmp_path / 'standard.xlsx'
    path.write_bytes(build_template(group, 2026).getvalue())
    with open(path, 'rb') as fh:
        page = client.post('/settings/workbook-layout', data={**FORM, 'action': 'test', 'file': (fh, 's.xlsx')},
                           content_type='multipart/form-data').data
    assert b'in the standard layout' in page


def test_save_then_upload_uses_the_layout_and_reset_clears_it(client, group, chair, tmp_path):
    client.post('/settings/workbook-layout', data={**FORM, 'action': 'save'})
    assert db.session.get(Group, group.id).settings.sheet_mapping['name_column'] == 'B'

    with open(_other_layout(tmp_path / 'o.xlsx'), 'rb') as fh:
        client.post('/upload', data={'file': (fh, 'o.xlsx'), 'year': '2026', 'month': '3'},
                    content_type='multipart/form-data')
    report = GeneratedReport.query.one()
    assert (report.total_contributions, report.money_dispensed) == (1500, 4000)
    assert SyncRun.query.one().warnings[0]['where'] == "Sheet 'Contrib 2026' cell E5"

    client.post('/settings/workbook-layout', data={'action': 'reset'})
    assert db.session.get(Group, group.id).settings.sheet_mapping is None


def test_invalid_settings_are_not_saved(client, group, chair):
    page = client.post('/settings/workbook-layout',
                       data={**FORM, 'january_column': 'C', 'header_row': '', 'action': 'save'}).data
    assert b'also give the header row' in page
    assert db.session.get(Group, group.id).settings.sheet_mapping is None


def test_layout_page_needs_edit_settings(client, group, make_user, login):
    make_user(email='t@example.com', role='Treasurer')
    login('t@example.com')
    assert client.get('/settings/workbook-layout').status_code != 200


# ==================== REGENERATE ====================

def test_regenerate_rebuilds_from_the_latest_sync(client, group, make_user, login, mzugoss_workbook):
    make_user()
    login()
    with open(mzugoss_workbook, 'rb') as fh:
        client.post('/upload', data={'file': (fh, 'm.xlsx'), 'year': '2026', 'month': '3'},
                    content_type='multipart/form-data')
    first = GeneratedReport.query.one()

    # The month is synced again with a late payment
    parsed = ExcelParser.parse_excel(str(mzugoss_workbook), year=2026, month=3)
    parsed['data'].loc[parsed['data']['Name'] == 'Chisomo Mwale', 'March'] = 1000
    PeriodStore.sync(group, parsed)

    response = client.post(f'/reports/{first.id}/regenerate')

    new = GeneratedReport.query.filter(GeneratedReport.id != first.id).one()
    assert response.headers['Location'] == f'/reports/{new.id}'
    assert (new.total_contributions, new.contributors_count) == (3500, 4)
    assert new.file_path != first.file_path


def test_regenerate_copies_when_nothing_is_stored(client, group, make_user, login, tmp_path):
    user = make_user()
    login()
    pdf = tmp_path / 'old.pdf'
    pdf.write_bytes(b'%PDF-1.4 old')
    old = GeneratedReport(group_id=group.id, month=1, year=2024, filename='old.pdf', file_path=str(pdf),
                          generated_by=user.id, total_contributions=700)
    db.session.add(old)
    db.session.commit()

    client.post(f'/reports/{old.id}/regenerate')

    copy = GeneratedReport.query.filter(GeneratedReport.id != old.id).one()
    assert copy.total_contributions == 700 and copy.filename.startswith('copy_')


# ==================== GOOGLE SHEETS ====================

def test_settings_show_the_service_account_email(client, app, group, chair):
    app.config['GOOGLE_CREDENTIALS_JSON'] = json.dumps({'client_email': 'welfare@project.iam.gserviceaccount.com'})
    assert b'welfare@project.iam.gserviceaccount.com' in client.get('/settings').data

    app.config['GOOGLE_CREDENTIALS_JSON'] = ''
    app.config['GOOGLE_CREDENTIALS_PATH'] = ''
    page = client.get('/settings').data.decode()
    assert 'set up on this platform' in page, page[page.find('Leave blank to clear'):][:400]
