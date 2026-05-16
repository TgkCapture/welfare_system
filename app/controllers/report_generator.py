# app/services/report_generator.py
"""
PDF report generation using fpdf2.

fpdf2 uses Latin-1 (ISO-8859-1) by default which cannot encode characters
outside that range (e.g. em dash \u2014, curly quotes, etc.).  All text
that comes from user data is sanitised through _safe_str() before being
written to the PDF.
"""
import os
import unicodedata
from datetime import datetime

from fpdf import FPDF
from flask import current_app


# ---------------------------------------------------------------------------
# Unicode → Latin-1 safe conversion
# ---------------------------------------------------------------------------

# Common Unicode characters that have sensible Latin-1 substitutes
_UNICODE_MAP = {
    '\u2014': '-',   # em dash        —
    '\u2013': '-',   # en dash        –
    '\u2018': "'",   # left single quotation mark
    '\u2019': "'",   # right single quotation mark
    '\u201c': '"',   # left double quotation mark
    '\u201d': '"',   # right double quotation mark
    '\u2026': '...', # horizontal ellipsis
    '\u00a0': ' ',   # non-breaking space
    '\u2022': '*',   # bullet
    '\u00b7': '.',   # middle dot
    '\u2012': '-',   # figure dash
    '\u2015': '-',   # horizontal bar
}


def _safe_str(value) -> str:
    """Convert *value* to a Latin-1-safe string.

    Strategy:
    1. Convert to str.
    2. Replace known problematic Unicode characters with ASCII equivalents.
    3. Decompose remaining accented characters (é → e + combining acute).
    4. Drop any character that still cannot be encoded as Latin-1.
    """
    if value is None:
        return ''

    text = str(value)

    # Step 1: explicit substitution map
    for char, replacement in _UNICODE_MAP.items():
        text = text.replace(char, replacement)

    # Step 2: NFKD decomposition — breaks accented chars into base + diacritic
    text = unicodedata.normalize('NFKD', text)

    # Step 3: encode as Latin-1, dropping anything that still won't fit
    text = text.encode('latin-1', errors='ignore').decode('latin-1')

    return text


# ---------------------------------------------------------------------------
# Custom FPDF subclass
# ---------------------------------------------------------------------------

class ReportPDF(FPDF):
    """FPDF subclass with branded header and page-number footer."""

    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(
            0, 10,
            _safe_str('MZUGOSS CLASS OF 2018 \u2014 MONTHLY CONTRIBUTIONS REPORT'),
            border=0, ln=1, align='C',
        )
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', border=0, align='C')


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generate a PDF contribution report from parsed Excel data."""

    @staticmethod
    def generate_contribution_report(data: dict, report_folder: str) -> str:
        """Build the PDF and write it to *report_folder*.

        Args:
            data:          Dict returned by ``ExcelParser.parse_excel()``.
            report_folder: Directory where the PDF will be saved.

        Returns:
            Absolute path to the saved PDF file.
        """
        pdf = ReportPDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_fill_color(240, 240, 240)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('Arial', size=11)

        ReportGenerator._section_header(pdf, data)
        ReportGenerator._summary_section(pdf, data)
        ReportGenerator._paid_members_section(pdf, data)

        if data.get('num_missing', 0) > 0:
            ReportGenerator._defaulters_section(pdf, data)

        ReportGenerator._report_footer(pdf)

        timestamp   = datetime.now().strftime('%Y%m%d%H%M%S')
        month_safe  = _safe_str(data.get('month', 'unknown'))
        filename    = f"contributions_report_{data.get('year', '')}_{month_safe}_{timestamp}.pdf"
        report_path = os.path.join(report_folder, filename)

        os.makedirs(report_folder, exist_ok=True)
        pdf.output(report_path)

        current_app.logger.info(f"ReportGenerator: saved PDF to {report_path}")
        return report_path

    # ------------------------------------------------------------------
    # Private section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _section_header(pdf: ReportPDF, data: dict) -> None:
        pdf.set_font('Arial', 'B', 13)
        pdf.cell(
            0, 10,
            f"Report for {_safe_str(data.get('month'))} {data.get('year', '')}",
            ln=1,
        )
        pdf.ln(4)

    @staticmethod
    def _summary_section(pdf: ReportPDF, data: dict) -> None:
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, 'SUMMARY STATISTICS', ln=1)
        pdf.set_font('Arial', size=11)

        rows = [
            ('Total Contributions',    f"MWK {data.get('total_contributions', 0):,.2f}"),
            ('Number of Contributors', str(data.get('num_contributors', 0))),
            ('Number of Defaulters',   str(data.get('num_missing', 0))),
        ]

        dispensed = data.get('money_dispensed')
        if dispensed is not None:
            rows.append(('Money Dispensed', f"MWK {ReportGenerator._fmt(dispensed)}"))

        balance = data.get('total_book_balance')
        if balance is not None:
            rows.append(('Total Book Balance', f"MWK {ReportGenerator._fmt(balance)}"))

        for label, value in rows:
            pdf.cell(70, 9, _safe_str(label), border=1, fill=True)
            pdf.cell(0,  9, _safe_str(value), border=1, ln=1)

        pdf.ln(8)

    @staticmethod
    def _paid_members_section(pdf: ReportPDF, data: dict) -> None:
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, 'PAID MEMBERS', ln=1)
        pdf.set_font('Arial', size=10)

        df        = data.get('data')
        month_col = data.get('month_col')
        name_col  = data.get('name_col')

        if df is None or df.empty or not month_col or not name_col:
            pdf.cell(0, 8, 'No paid members for this period.', ln=1)
            pdf.ln(6)
            return

        paid_df = df[df[month_col].notna()]
        if paid_df.empty:
            pdf.cell(0, 8, 'No paid members for this period.', ln=1)
            pdf.ln(6)
            return

        # Table header
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(120, 9, 'Name',         border=1, align='C', fill=True)
        pdf.cell(0,   9, 'Amount (MWK)', border=1, align='C', fill=True, ln=1)
        pdf.set_fill_color(255, 255, 255)

        for _, row in paid_df.iterrows():
            name   = _safe_str(row.get(name_col, ''))
            amount = float(row[month_col])
            pdf.cell(120, 8, name,              border=1)
            pdf.cell(0,   8, f'{amount:,.2f}',  border=1, align='R', ln=1)

        pdf.ln(8)

    @staticmethod
    def _defaulters_section(pdf: ReportPDF, data: dict) -> None:
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, 'DEFAULTERS', ln=1)
        pdf.set_font('Arial', size=10)

        pdf.set_fill_color(255, 200, 200)
        pdf.cell(0, 9, 'Name', border=1, align='C', fill=True, ln=1)
        pdf.set_fill_color(255, 255, 255)

        for name in data.get('defaulters', []):
            pdf.cell(0, 8, _safe_str(name), border=1, ln=1)

        pdf.ln(6)

    @staticmethod
    def _report_footer(pdf: ReportPDF) -> None:
        pdf.ln(8)
        pdf.set_font('Arial', 'I', 9)
        pdf.cell(
            0, 8,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            align='C', ln=1,
        )

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(value) -> str:
        try:
            return f"{float(value):,.2f}"
        except (ValueError, TypeError):
            return _safe_str(value)