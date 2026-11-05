"""
Characterisation tests for ExcelParser.

These pin the parser's current behaviour on the Mzugoss layout so the
Phase 2 refactor (standard template, configurable column mapping) can be
checked against them. Where current behaviour is known to be wrong, the
test says so; change it deliberately when the behaviour is fixed.
"""
import pandas as pd
import pytest

from app.services.excel_parser import ExcelParser
from tests.workbooks import MONEY_DISPENSED_2026, TOTAL_BOOK_BALANCE_2026


@pytest.fixture
def march_2026(app, mzugoss_workbook):
    return ExcelParser.parse_excel(str(mzugoss_workbook), year=2026, month=3)


def test_detects_columns_and_period(march_2026):
    assert march_2026['month'] == 'March'
    assert march_2026['year'] == 2026
    assert march_2026['name_col'] == 'Name'
    assert march_2026['month_col'] == 'March'


def test_member_rows_exclude_blank_and_total_rows(march_2026):
    assert march_2026['data']['Name'].tolist() == [
        'Alinafe Banda', 'Bright Phiri', 'Chisomo Mwale', 'Dumisani Zulu',
        'Esther Tembo', 'Fañny Kumwenda', 'Gift  Nyirenda',
    ]


def test_totals_count_only_positive_amounts(march_2026):
    assert march_2026['total_contributions'] == 2500.0
    assert march_2026['num_contributors'] == 3


def test_partial_payment_counts_as_paid(march_2026):
    # Known gap: 500 against a 1000 rate is treated as fully paid.
    # Phase 2 introduces rates and a 'partial' status.
    paid = march_2026['data'].loc[march_2026['data']['March'] > 0, 'Name']
    assert 'Bright Phiri' in paid.tolist()


def test_blank_zero_text_and_not_yet_joined_are_defaulters(march_2026):
    # Known gap: Gift Nyirenda joined in April but is listed as a
    # defaulter for March. Phase 2 adds member join dates.
    assert march_2026['defaulters'] == [
        'Chisomo Mwale', 'Dumisani Zulu', 'Esther Tembo', 'Gift  Nyirenda',
    ]
    assert march_2026['num_missing'] == 4


def test_reads_financial_rows_above_the_header(march_2026):
    assert march_2026['money_dispensed'] == MONEY_DISPENSED_2026
    assert march_2026['total_book_balance'] == TOTAL_BOOK_BALANCE_2026


def test_selects_sheet_by_year(app, mzugoss_workbook):
    data = ExcelParser.parse_excel(str(mzugoss_workbook), year=2025, month=3)
    assert data['total_contributions'] == 1000.0
    assert data['defaulters'] == ['Bright Phiri']
    assert data['money_dispensed'] == 5000


def test_falls_back_to_first_sheet_for_unknown_year(app, mzugoss_workbook):
    data = ExcelParser.parse_excel(str(mzugoss_workbook), year=2019, month=8)
    assert data['total_contributions'] == 1000.0
    assert data['money_dispensed'] == 1000


def test_missing_month_column_raises_value_error():
    df = pd.DataFrame(columns=['No', 'Name', 'January'])
    with pytest.raises(ValueError, match="No column found for month 'March'"):
        ExcelParser._find_month_column(df, 'March')
