# app/services/report_generator.py
"""
PDF report generation using fpdf2.

fpdf2 uses Latin-1 (ISO-8859-1) for its built-in fonts.  Every string
written to the PDF — including hardcoded strings — must be Latin-1 safe.
The em dash in the original header title was \u2014 (position 72), which
is outside Latin-1 and caused the UnicodeEncodeError on every upload.
"""
import os
import unicodedata
from datetime import datetime

from fpdf import FPDF
from flask import current_app


# ---------------------------------------------------------------------------
# Latin-1 sanitiser — applied to EVERY string written to the PDF
# ---------------------------------------------------------------------------

_CHAR_MAP = {
    '\u2014': '-',    # em dash           —
    '\u2013': '-',    # en dash           –
    '\u2012': '-',    # figure dash
    '\u2015': '-',    # horizontal bar
    '\u2018': "'",    # left single quote
    '\u2019': "'",    # right single quote
    '\u201c': '"',    # left double quote
    '\u201d': '"',    # right double quote
    '\u2026': '...',  # ellipsis
    '\u00a0': ' ',    # non-breaking space
    '\u2022': '*',    # bullet
    '\u00b7': '.',    # middle dot
}


def _s(value) -> str:
    """Return a Latin-1-safe string from *value*.

    Steps:
      1. Explicit substitution of common problem characters.
      2. NFKD decomposition (e.g. é → e + combining accent).
      3. Encode as Latin-1, silently dropping anything that still won't fit.
    """
    if value is None:
        return ''
    text = str(value)
    for char, sub in _CHAR_MAP.items():
        text = text.replace(char, sub)
    text = unicodedata.normalize('NFKD', text)
    return text.encode('latin-1', errors='ignore').decode('latin-1')


# ---------------------------------------------------------------------------
# Custom FPDF subclass
# ---------------------------------------------------------------------------

class ReportPDF(FPDF):
    """FPDF subclass with branded header and page-number footer."""

    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(
            0, 10,
            'MZUGOSS CLASS OF 2018 - MONTHLY CONTRIBUTIONS REPORT',
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
        month_safe  = _s(data.get('month', 'unknown'))
        filename    = (
            f"contributions_report"
            f"_{data.get('year', '')}_{month_safe}_{timestamp}.pdf"
        )
        report_path = os.path.join(report_folder, filename)

        # Ensure the folder exists
        os.makedirs(report_folder, exist_ok=True)
        pdf.output(report_path)

        current_app.logger.info(f"ReportGenerator: saved PDF to {report_path}")
        return report_path

    # ------------------------------------------------------------------
    # Private section builders — all text through _s()
    # ------------------------------------------------------------------

    @staticmethod
    def _section_header(pdf: ReportPDF, data: dict) -> None:
        pdf.set_font('Arial', 'B', 13)
        pdf.cell(
            0, 10,
            _s(f"Report for {data.get('month', '')} {data.get('year', '')}"),
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
            rows.append(('Money Dispensed',    f"MWK {ReportGenerator._fmt(dispensed)}"))

        balance = data.get('total_book_balance')
        if balance is not None:
            rows.append(('Total Book Balance', f"MWK {ReportGenerator._fmt(balance)}"))

        for label, value in rows:
            pdf.cell(70, 9, _s(label), border=1, fill=True)
            pdf.cell(0,  9, _s(value), border=1, ln=1)

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
            pdf.cell(0, 8, 'No member data available.', ln=1)
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
            name   = _s(row.get(name_col, ''))
            amount = float(row[month_col])
            pdf.cell(120, 8, name,             border=1)
            pdf.cell(0,   8, f'{amount:,.2f}', border=1, align='R', ln=1)

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
            pdf.cell(0, 8, _s(name), border=1, ln=1)

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
            return _s(str(value))