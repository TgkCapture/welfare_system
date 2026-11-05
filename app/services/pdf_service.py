# app/services/pdf_service.py
"""
PDF generation using ReportLab.

Two documents are produced here:

  generate_welfare_rules_pdf()        — a group's rules document, from its rule sections
  generate_contribution_report_pdf()  — per-month financial report

Both return raw ``bytes`` so the caller can stream them directly via
``make_response`` or write them to disk.  ``save_contribution_report()``
writes the contribution report to the report folder and returns its path.

Design notes:
  - All styles are defined once in ``_Styles`` and shared across both
    generators — change a colour/font there to re-theme everything.
  - Section builders are private static methods so each logical block
    is independently readable and testable.
  - Every public method re-raises on failure after logging — callers
    decide how to handle the error (flash, fallback, etc.).
"""
import io
import logging
import os
import re
import uuid
from datetime import datetime

import pandas as pd
from flask import current_app
from markupsafe import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared colour constants
# ---------------------------------------------------------------------------
_BLUE        = colors.HexColor('#2563eb')
_BLUE_DARK   = colors.HexColor('#1d4ed8')
_BLUE_LIGHT  = colors.HexColor('#dbeafe')
_SLATE_900   = colors.HexColor('#0f172a')
_SLATE_700   = colors.HexColor('#374151')
_SLATE_500   = colors.HexColor('#6b7280')
_SLATE_100   = colors.HexColor('#f1f5f9')
_SLATE_50    = colors.HexColor('#f8fafc')
_WHITE       = colors.white
_RED_HDR     = colors.HexColor('#ef4444')
_RED_LIGHT   = colors.HexColor('#fef2f2')
_RED_BORDER  = colors.HexColor('#fecaca')
_AMBER_BG    = colors.HexColor('#fef3c7')
_AMBER_BORDER= colors.HexColor('#f59e0b')
_GRID        = colors.HexColor('#e2e8f0')


class _Styles:
    """Lazy-initialised paragraph style registry."""

    _cache: dict = {}

    @classmethod
    def get(cls) -> dict:
        if cls._cache:
            return cls._cache

        base = getSampleStyleSheet()

        def ps(name, **kw):
            parent = kw.pop('parent', base['Normal'])
            return ParagraphStyle(name, parent=parent, **kw)

        cls._cache = {
            # ── Welfare rules ──────────────────────────────────────────
            'title': ps(
                'WR_Title', parent=base['Heading1'],
                fontSize=22, spaceAfter=24,
                textColor=_BLUE, alignment=TA_CENTER,
                fontName='Helvetica-Bold',
            ),
            'heading': ps(
                'WR_Heading', parent=base['Heading2'],
                fontSize=15, spaceAfter=10, spaceBefore=6,
                textColor=_SLATE_900, fontName='Helvetica-Bold',
                leftIndent=8,
            ),
            'subheading': ps(
                'WR_Sub', parent=base['Heading3'],
                fontSize=12, spaceAfter=4,
                textColor=_SLATE_700, fontName='Helvetica-Bold',
            ),
            'body': ps(
                'WR_Body',
                fontSize=10, spaceAfter=6,
                textColor=_SLATE_700, leading=14,
            ),
            'bullet': ps(
                'WR_Bullet',
                fontSize=10, spaceAfter=3, spaceBefore=2,
                textColor=_SLATE_700, leading=14,
                leftIndent=18, firstLineIndent=-10,
            ),
            'important': ps(
                'WR_Important',
                fontSize=10, spaceAfter=10, spaceBefore=10,
                textColor=_SLATE_700, leading=14,
                backColor=_AMBER_BG,
                borderColor=_AMBER_BORDER,
                borderWidth=1, borderPadding=10,
                leftIndent=8, rightIndent=8,
            ),
            'footer': ps(
                'WR_Footer',
                fontSize=8, spaceAfter=0,
                textColor=_SLATE_500, alignment=TA_CENTER,
            ),
            # ── Contribution report ────────────────────────────────────
            'rpt_title': ps(
                'RPT_Title', parent=base['Heading1'],
                fontSize=16, spaceAfter=16,
                textColor=_BLUE, alignment=TA_CENTER,
                fontName='Helvetica-Bold',
            ),
            'rpt_section': ps(
                'RPT_Section', parent=base['Heading2'],
                fontSize=12, spaceAfter=10, spaceBefore=4,
                textColor=_SLATE_900, fontName='Helvetica-Bold',
                leftIndent=8,
            ),
            'rpt_body': ps(
                'RPT_Body',
                fontSize=9, spaceAfter=4,
                textColor=_SLATE_700, leading=12,
            ),
            'rpt_footer': ps(
                'RPT_Footer',
                fontSize=7, spaceAfter=0,
                textColor=_SLATE_500, alignment=TA_CENTER,
            ),
        }
        return cls._cache


# ---------------------------------------------------------------------------
# Reusable table-style helpers
# ---------------------------------------------------------------------------

def _blue_header_table_style(extra=None):
    base = [
        ('BACKGROUND',  (0, 0), (-1,  0), _BLUE),
        ('TEXTCOLOR',   (0, 0), (-1,  0), _WHITE),
        ('ALIGN',       (0, 0), (-1,  0), 'CENTER'),
        ('FONTNAME',    (0, 0), (-1,  0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1,  0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND',  (0, 1), (-1, -1), _WHITE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [_WHITE, _SLATE_50]),
        ('GRID',        (0, 0), (-1, -1), 0.5, _GRID),
        ('FONTNAME',    (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE',    (0, 1), (-1, -1), 9),
        ('TOPPADDING',  (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]
    return TableStyle(base + (extra or []))


def _summary_table_style():
    return TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), _SLATE_50),
        ('GRID',          (0, 0), (-1, -1), 0.5, _GRID),
        ('FONTNAME',      (0, 0), (0,  -1), 'Helvetica-Bold'),
        ('FONTNAME',      (1, 0), (1,  -1), 'Helvetica'),
        ('FONTSIZE',      (0, 0), (-1, -1), 10),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ])


# ---------------------------------------------------------------------------
# Main public class
# ---------------------------------------------------------------------------

class PDFGenerator:
    """ReportLab-based PDF generation for welfare documents."""

    # ------------------------------------------------------------------
    # Welfare rules PDF
    # ------------------------------------------------------------------

    @staticmethod
    def generate_welfare_rules_pdf(brand, sections) -> bytes:
        """Build a group's welfare rules document from its rule sections.

        *sections* are RuleSection rows in order; their bodies use the rules
        markup, which turns into the same bold, italic and lists as on the
        web page.

        Raises:
            Exception: on any ReportLab failure.
        """
        from app.services.rules_markup import parse

        try:
            buf = io.BytesIO()
            doc = SimpleDocTemplate(
                buf, pagesize=A4,
                rightMargin=60, leftMargin=60,
                topMargin=60,   bottomMargin=60,
                title=f'{brand.name} welfare rules',
            )

            s     = _Styles.get()
            story = PDFGenerator._logo(brand.logo_file) + [
                Paragraph(f'{escape(brand.name)} — welfare rules', s['title']),
                Paragraph(f"Printed {datetime.now().strftime('%d %B %Y')}", s['body']),
                Spacer(1, 16),
            ]

            if not sections:
                story.append(Paragraph('No rules have been written yet.', s['body']))
            for section in sections:
                story.append(Paragraph(escape(section.title), s['heading']))
                if section.subtitle:
                    story.append(Paragraph(escape(section.subtitle), s['subheading']))
                for block in parse(section.body):
                    if block.kind == 'ul':
                        story.extend(Paragraph(f'• {item}', s['bullet']) for item in block.items)
                    elif block.kind == 'ol':
                        story.extend(Paragraph(f'{n}. {item}', s['bullet'])
                                     for n, item in enumerate(block.items, start=1))
                    elif block.kind == 'note':
                        story.append(Paragraph(f'<i>{block.items[0]}</i>', s['body']))
                    else:
                        story.append(Paragraph(str(block.items[0]), s['body']))
                story.append(Spacer(1, 14))

            story.append(Spacer(1, 10))
            story.append(Paragraph(f'For {escape(brand.name)} members.', s['footer']))

            doc.build(story)
            pdf = buf.getvalue()
            buf.close()

            logger.info('Generated welfare rules PDF')
            return pdf

        except Exception as e:
            logger.error(f'Welfare rules PDF failed: {e}', exc_info=True)
            raise Exception(f'Failed to generate welfare rules PDF: {e}') from e

    # ------------------------------------------------------------------
    # Contribution report PDF
    # ------------------------------------------------------------------

    @staticmethod
    def generate_contribution_report_pdf(data: dict) -> bytes:
        """Generate a per-month contribution report.

        Args:
            data: Dict from ``ExcelParser.parse_excel()``.

        Returns:
            Raw PDF bytes.

        Raises:
            Exception: on any ReportLab failure.
        """
        month = data.get('month', '')
        year  = data.get('year', '')

        try:
            buf = io.BytesIO()
            doc = SimpleDocTemplate(
                buf, pagesize=A4,
                rightMargin=50, leftMargin=50,
                topMargin=50,   bottomMargin=50,
                title=f'Contributions Report — {month} {year}',
            )

            s     = _Styles.get()
            story = PDFGenerator._logo(data.get('logo_file'))

            # ── Title ──────────────────────────────────────────────────
            story.append(Paragraph(
                escape(data.get('report_title') or 'Monthly contributions report').upper(),
                s['rpt_title'],
            ))
            story.append(Paragraph(f'Report for {month} {year}', s['rpt_section']))
            story.append(Spacer(1, 12))

            # ── Summary ────────────────────────────────────────────────
            story.extend(PDFGenerator._summary_section(data, s))
            story.append(Spacer(1, 16))

            # ── Balances and payouts, the year so far ──────────────────
            if 'dispensed_to_date' in data:
                story.extend(PDFGenerator._balance_section(data, s))
                story.append(Spacer(1, 16))
                story.extend(PDFGenerator._payouts_section(data, s))
                story.append(Spacer(1, 16))

            # ── Paid members ───────────────────────────────────────────
            story.extend(PDFGenerator._paid_members_section(data, s))
            story.append(Spacer(1, 16))

            # ── Defaulters ─────────────────────────────────────────────
            if data.get('num_missing', 0) > 0:
                story.extend(PDFGenerator._defaulters_section(data, s))
                story.append(Spacer(1, 16))

            # ── Footer ─────────────────────────────────────────────────
            version = getattr(current_app, 'version', '1.0')
            story.append(Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                f"&nbsp;|&nbsp; Version {version}",
                s['rpt_footer'],
            ))

            doc.build(story)
            pdf = buf.getvalue()
            buf.close()

            logger.info(f'Generated contribution report PDF for {month} {year}')
            return pdf

        except Exception as e:
            logger.error(
                f'Contribution report PDF failed ({month} {year}): {e}',
                exc_info=True,
            )
            raise Exception(
                f'Failed to generate contribution report PDF: {e}'
            ) from e

    @staticmethod
    def save_contribution_report(data: dict, report_folder: str) -> str:
        """Generate the contribution report and write it to *report_folder*.

        Returns:
            Absolute path to the saved PDF file.
        """
        pdf = PDFGenerator.generate_contribution_report_pdf(data)

        timestamp  = datetime.now().strftime('%Y%m%d%H%M%S')
        month_safe = re.sub(r'[^A-Za-z0-9]+', '', str(data.get('month', ''))) or 'unknown'
        # The random part keeps two reports made in the same second from sharing a file
        filename   = (
            f"contributions_report"
            f"_{data.get('year', '')}_{month_safe}_{timestamp}_{uuid.uuid4().hex[:6]}.pdf"
        )
        report_path = os.path.join(report_folder, filename)

        os.makedirs(report_folder, exist_ok=True)
        with open(report_path, 'wb') as fh:
            fh.write(pdf)

        logger.info(f'Saved contribution report PDF to {report_path}')
        return report_path

    # ------------------------------------------------------------------
    # Private section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _logo(path) -> list:
        """The group's logo, centred above the title, if it has one."""
        if not path or not os.path.isfile(path):
            return []
        try:
            from PIL import Image as PILImage
            with PILImage.open(path) as img:
                width, height = img.size
            size = 0.9 * inch
            scale = size / max(width, height)
            logo = Image(path, width=width * scale, height=height * scale)
            logo.hAlign = 'CENTER'
            return [logo, Spacer(1, 8)]
        except Exception as e:
            logger.warning(f'Could not add the logo to a PDF: {e}')
            return []

    @staticmethod
    def _summary_section(data: dict, s: dict) -> list:
        """Build the summary statistics table flowables."""
        cur = data.get('currency', 'MWK')
        rows = [
            ['Total Contributions',    f"{cur} {data.get('total_contributions', 0):,.2f}"],
            ['Number of Contributors', str(data.get('num_contributors', 0))],
            ['Number of Defaulters',   str(data.get('num_missing', 0))],
        ]

        # Groups with calculated balances get the balance section instead
        if 'dispensed_to_date' not in data:
            dispensed = data.get('money_dispensed')
            if dispensed is not None:
                rows.append(['Money Dispensed', f"{cur} {PDFGenerator._fmt(dispensed)}"])

            balance = data.get('total_book_balance')
            if balance is not None:
                rows.append(['Total Book Balance', f"{cur} {PDFGenerator._fmt(balance)}"])

        return [
            Paragraph('SUMMARY STATISTICS', s['rpt_section']),
            Table(
                rows,
                colWidths=[3.0*inch, 2.2*inch],
                style=_summary_table_style(),
            ),
        ]

    @staticmethod
    def _balance_section(data: dict, s: dict) -> list:
        """Opening balance, money in and out (this month and the year so far), book balance."""
        cur, fmt = data.get('currency', 'MWK'), PDFGenerator._fmt
        month, year = data.get('month', ''), data.get('year', '')
        so_far = f'Jan–{month[:3]} {year}' if month[:3] != 'Jan' else f'{month} {year}'
        rows = [
            ['', f'{month} {year}', so_far],
            [f'Opening balance, 1 January {year}', '', f"{cur} {fmt(data['opening_balance'])}"],
            ['Paid in', f"{cur} {fmt(data.get('total_contributions') or 0)}",
             f"{cur} {fmt(data['contributions_to_date'])}"],
            ['Money dispensed', f"{cur} {fmt(data.get('money_dispensed') or 0)}",
             f"{cur} {fmt(data['dispensed_to_date'])}"],
            [f'Book balance, end of {month} {year}', '', f"{cur} {fmt(data.get('total_book_balance') or 0)}"],
        ]
        return [
            Paragraph('BALANCES', s['rpt_section']),
            Table(rows, colWidths=[2.6*inch, 1.4*inch, 1.4*inch], style=_blue_header_table_style([
                ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ])),
        ]

    @staticmethod
    def _payouts_section(data: dict, s: dict) -> list:
        """Every payout of the year up to the end of the report's month."""
        year, payouts = data.get('year', ''), data.get('payouts_to_date') or []
        flowables = [Paragraph(f'MONEY DISPENSED IN {year}', s['rpt_section'])]
        if not payouts:
            flowables.append(Paragraph('Nothing paid out so far this year.', s['rpt_body']))
            return flowables
        rows = [['Date', 'To', 'Purpose', 'Amount']] + [
            [p['paid_on'].strftime('%d %b %Y'), Paragraph(escape(p['beneficiary']), s['rpt_body']),
             Paragraph(escape(p['purpose']), s['rpt_body']), PDFGenerator._fmt(p['amount'])]
            for p in payouts
        ] + [['', '', 'Total', PDFGenerator._fmt(data['dispensed_to_date'])]]
        flowables.append(Table(rows, colWidths=[1.0*inch, 2.0*inch, 1.6*inch, 1.0*inch], repeatRows=1,
                               style=_blue_header_table_style([
                                   ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
                                   ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                                   ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                               ])))
        return flowables

    @staticmethod
    def _paid_members_section(data: dict, s: dict) -> list:
        """Build the paid-members table flowables."""
        flowables = [Paragraph('PAID MEMBERS', s['rpt_section'])]

        df        = data.get('data')
        month_col = data.get('month_col')
        name_col  = data.get('name_col')

        if not isinstance(df, pd.DataFrame) or df.empty or not month_col or not name_col:
            flowables.append(Paragraph('No member data available.', s['rpt_body']))
            return flowables

        paid_df = df[df[month_col].notna() & (df[month_col] > 0)]
        if paid_df.empty:
            flowables.append(Paragraph('No paid members for this period.', s['rpt_body']))
            return flowables

        rows = [['Name', f"Amount ({data.get('currency', 'MWK')})"]]
        for _, row in paid_df.iterrows():
            rows.append([
                str(row[name_col]),
                PDFGenerator._fmt(row[month_col]),
            ])

        flowables.append(
            Table(
                rows,
                colWidths=[3.8*inch, 1.6*inch],
                style=_blue_header_table_style([
                    ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                ]),
            )
        )
        return flowables

    @staticmethod
    def _defaulters_section(data: dict, s: dict) -> list:
        """Build the defaulters table flowables."""
        flowables  = [Paragraph('DEFAULTERS', s['rpt_section'])]
        defaulters = data.get('defaulters', [])

        if not defaulters:
            flowables.append(Paragraph('No defaulters recorded.', s['rpt_body']))
            return flowables

        rows = [['Name']] + [[str(n)] for n in defaulters]
        flowables.append(
            Table(
                rows,
                colWidths=[5.4*inch],
                style=TableStyle([
                    ('BACKGROUND',    (0, 0), (-1,  0), _RED_HDR),
                    ('TEXTCOLOR',     (0, 0), (-1,  0), _WHITE),
                    ('ALIGN',         (0, 0), (-1,  0), 'CENTER'),
                    ('FONTNAME',      (0, 0), (-1,  0), 'Helvetica-Bold'),
                    ('FONTSIZE',      (0, 0), (-1,  0), 11),
                    ('BACKGROUND',    (0, 1), (-1, -1), _RED_LIGHT),
                    ('GRID',          (0, 0), (-1, -1), 0.5, _RED_BORDER),
                    ('FONTSIZE',      (0, 1), (-1, -1), 9),
                    ('TOPPADDING',    (0, 1), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ]),
            )
        )
        return flowables

    # ------------------------------------------------------------------
    # Private — formatting
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt(value) -> str:
        """Format a numeric amount with thousands separators."""
        try:
            return f"{float(value):,.2f}"
        except (ValueError, TypeError):
            return str(value)