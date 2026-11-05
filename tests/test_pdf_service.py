import os

from app.services.excel_parser import ExcelParser
from app.services.pdf_service import PDFGenerator, _Styles


def test_save_contribution_report_writes_pdf(app, mzugoss_workbook, tmp_path):
    data = ExcelParser.parse_excel(str(mzugoss_workbook), year=2026, month=3)

    path = PDFGenerator.save_contribution_report(data, str(tmp_path / 'out'))

    assert os.path.basename(path).startswith('contributions_report_2026_March_')
    with open(path, 'rb') as fh:
        assert fh.read(5) == b'%PDF-'


def test_paid_members_table_excludes_zero_amounts(app, mzugoss_workbook):
    data = ExcelParser.parse_excel(str(mzugoss_workbook), year=2026, month=3)

    _, table = PDFGenerator._paid_members_section(data, _Styles.get())
    names = [row[0] for row in table._cellvalues[1:]]

    assert names == ['Alinafe Banda', 'Bright Phiri', 'Fañny Kumwenda']
