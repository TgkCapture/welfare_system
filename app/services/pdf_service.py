# app/services/pdf_service.py
"""
PDF generation using ReportLab.

Two documents are produced here:

  generate_welfare_rules_pdf()        — static rules document, public
  generate_contribution_report_pdf()  — per-month financial report

Both return raw ``bytes`` so the caller can stream them directly via
``make_response`` or write them to disk.

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
from datetime import datetime

import pandas as pd
from flask import current_app
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
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
    def generate_welfare_rules_pdf() -> bytes:
        """Generate the static welfare rules document.

        Returns:
            Raw PDF bytes.

        Raises:
            Exception: on any ReportLab failure.
        """
        try:
            buf = io.BytesIO()
            doc = SimpleDocTemplate(
                buf, pagesize=A4,
                rightMargin=60, leftMargin=60,
                topMargin=60,   bottomMargin=60,
                title='Mzugoss Welfare Rules',
            )

            s     = _Styles.get()
            story = []

            # ── Title block ────────────────────────────────────────────
            story.append(Paragraph('Mzugoss Welfare Rules & Guidelines', s['title']))
            version = getattr(current_app, 'version', '1.0')
            story.append(Paragraph(
                f"Last updated: {datetime.now().strftime('%Y-%m-%d')} "
                f"&nbsp;|&nbsp; Version {version}",
                s['body'],
            ))
            story.append(Spacer(1, 16))

            # ── Quick-summary fee table ────────────────────────────────
            story.append(Paragraph('Quick Summary', s['heading']))
            fee_data = [
                ['Service',             'Amount',   'Period'],
                ['Monthly Contribution','K1,000',   'per month'],
                ['Funeral Support',     'K50,000',  'per incident'],
                ['Wedding Support',     'K80,000',  'per wedding'],
                ['Sickness Support',    'K15,000',  'per admission'],
                ['Member Death Support','K80,000',  'per member'],
            ]
            story.append(
                Table(
                    fee_data,
                    colWidths=[2.6*inch, 1.4*inch, 1.4*inch],
                    style=_blue_header_table_style([
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                    ]),
                )
            )
            story.append(Spacer(1, 12))
            story.append(Paragraph(
                '<b>Important:</b> Only contributing members are eligible '
                'for welfare benefits. Members who do not contribute '
                'regularly cannot receive welfare money.',
                s['important'],
            ))
            story.append(Spacer(1, 16))

            # ── Section builder ────────────────────────────────────────
            def section(title, subtitle, paragraphs):
                story.append(Paragraph(title,    s['heading']))
                story.append(Paragraph(subtitle, s['subheading']))
                for line in paragraphs:
                    style = s['bullet'] if line.startswith('•') else s['body']
                    story.append(Paragraph(line, style))
                story.append(Spacer(1, 14))

            section(
                'Funeral Support Rules',
                'Financial assistance during bereavement',
                [
                    'Money is released only for immediate family members:',
                    '• Mother, Father, Sister, Brother',
                    '• Legal Guardian, Spouse, Children',
                    '<b>Amount:</b> K50,000 per funeral incident.',
                    '<i>Documentation may be required to verify relationship.</i>',
                ],
            )

            section(
                'Deceased Member Support',
                'Support for when a contributing member passes away',
                [
                    '<b>Amount:</b> K80,000 for the member\'s family.',
                    'This applies when a regularly contributing member dies. '
                    'The K80,000 is provided to support the family.',
                ],
            )

            story.append(PageBreak())

            section(
                'Contribution Rules',
                'Monthly contributions and penalties',
                [
                    '<b>1. Monthly Contribution:</b> K1,000 per month.',
                    '<b>2. Late-payment Penalty:</b> 5% per month.',
                    '<i>Example: 2 months late = 10% penalty.</i>',
                    '<b>3. Back Payments:</b> Missed months must be paid for the exact period missed.',
                    '<b>4. Benefit Calculation:</b> Months contributed = times eligible for support.',
                    '<i>Example: 3 months contribution = 3 times eligible.</i>',
                ],
            )

            section(
                'Sickness Support',
                'Medical and hospitalisation assistance',
                [
                    'Provided for members admitted to hospital for multiple days.',
                    'Outpatient visits and minor illnesses are <b>not</b> covered.',
                    '<b>Amount:</b> K15,000 per hospital admission.',
                    '<i>Hospital admission records may be required.</i>',
                ],
            )

            section(
                'Wedding Support',
                'Celebratory financial assistance',
                [
                    '<b>Amount:</b> K80,000 per wedding ceremony.',
                    'Available once per member for their own wedding ceremony.',
                ],
            )

            # ── Key points ─────────────────────────────────────────────
            story.append(Paragraph('Key Points to Remember', s['heading']))
            key_points = [
                '• Regular contributions ensure eligibility for all benefits.',
                '• Pay on time to avoid the 5% monthly penalty.',
                '• Sickness support: K15,000 for hospital admissions.',
                '• Wedding support: K80,000 — one-time per member.',
                '• Funeral support: K50,000 for immediate family.',
                '• Deceased-member support: K80,000 for the family.',
                '• No welfare money is paid to non-contributors.',
            ]
            for kp in key_points:
                story.append(Paragraph(kp, s['bullet']))
            story.append(Spacer(1, 20))

            # ── Footer ─────────────────────────────────────────────────
            for line in [
                'Confidential — For Mzugoss Members Only',
                f"Generated: {datetime.now().strftime('%Y-%m-%d at %H:%M')}",
                'For clarifications, contact the welfare committee.',
            ]:
                story.append(Paragraph(line, s['footer']))

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
            story = []

            # ── Title ──────────────────────────────────────────────────
            story.append(Paragraph(
                'MZUGOSS CLASS OF 2018 — MONTHLY CONTRIBUTIONS REPORT',
                s['rpt_title'],
            ))
            story.append(Paragraph(f'Report for {month} {year}', s['rpt_section']))
            story.append(Spacer(1, 12))

            # ── Summary ────────────────────────────────────────────────
            story.extend(PDFGenerator._summary_section(data, s))
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

    # ------------------------------------------------------------------
    # Private section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _summary_section(data: dict, s: dict) -> list:
        """Build the summary statistics table flowables."""
        rows = [
            ['Total Contributions',    f"MWK {data.get('total_contributions', 0):,.2f}"],
            ['Number of Contributors', str(data.get('num_contributors', 0))],
            ['Number of Defaulters',   str(data.get('num_missing', 0))],
        ]

        dispensed = data.get('money_dispensed')
        if dispensed is not None:
            rows.append(['Money Dispensed', f"MWK {PDFGenerator._fmt(dispensed)}"])

        balance = data.get('total_book_balance')
        if balance is not None:
            rows.append(['Total Book Balance', f"MWK {PDFGenerator._fmt(balance)}"])

        return [
            Paragraph('SUMMARY STATISTICS', s['rpt_section']),
            Table(
                rows,
                colWidths=[3.0*inch, 2.2*inch],
                style=_summary_table_style(),
            ),
        ]

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

        rows = [['Name', 'Amount (MWK)']]
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