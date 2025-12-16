# app/utils/pdf_utils.py
import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import current_app, url_for
import textwrap

class PDFGenerator:
    """Utility class for generating PDF documents using ReportLab"""
    
    @staticmethod
    def generate_welfare_rules_pdf():
        """
        Generate PDF from welfare rules using ReportLab with updated figures
        
        Returns:
            bytes: PDF file content
        """
        try:
            # Create a bytes buffer for the PDF
            buffer = io.BytesIO()
            
            # Create the PDF document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=36,
                leftMargin=36,
                topMargin=36,
                bottomMargin=36
            )
            
            # Container for the 'Flowable' objects
            story = []
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Custom Styles
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=20,
                textColor=colors.HexColor('#2563eb'),
                alignment=1,  # Center aligned
                fontName='Helvetica-Bold'
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Normal'],
                fontSize=12,
                spaceAfter=30,
                textColor=colors.HexColor('#4b5563'),
                alignment=1
            )
            
            section_style = ParagraphStyle(
                'SectionTitle',
                parent=styles['Heading2'],
                fontSize=18,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.HexColor('#1e293b'),
                borderPadding=(0, 0, 6, 0),
                borderColor=colors.HexColor('#2563eb'),
                borderWidth=(0, 0, 2, 0)
            )
            
            subsection_style = ParagraphStyle(
                'SubsectionTitle',
                parent=styles['Heading3'],
                fontSize=14,
                spaceAfter=8,
                textColor=colors.HexColor('#374151'),
                fontName='Helvetica-Bold'
            )
            
            normal_style = styles['Normal']
            normal_style.fontSize = 10
            normal_style.spaceAfter = 6
            
            bullet_style = ParagraphStyle(
                'BulletStyle',
                parent=normal_style,
                leftIndent=20,
                firstLineIndent=-10,
                bulletIndent=10,
                spaceAfter=4
            )
            
            # Add Header with gradient effect (simulated)
            story.append(Paragraph("Mzugoss Welfare Association", title_style))
            story.append(Paragraph("Rules & Guidelines", subtitle_style))
            story.append(Paragraph(f"Version 2.0 • Updated: {datetime.now().strftime('%Y-%m-%d')}", subtitle_style))
            story.append(Spacer(1, 30))
            
            # Quick Summary Section
            story.append(Paragraph("Quick Summary", section_style))
            
            # Summary table with updated figures
            summary_data = [
                ['Support Type', 'Amount', 'Frequency'],
                ['Monthly Contribution', '<b>K1,000</b>', 'per month'],
                ['Funeral Support', '<b>K50,000</b>', 'per incident'],
                ['Wedding Support', '<b>K80,000</b>', 'per wedding'],
                ['Sickness Support', '<b>K15,000</b>', 'per admission'],
                ['Member Death Support', '<font color="#dc2626"><b>K80,000</b></font>', 'per member']
            ]
            
            summary_table = Table(summary_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 30))
            
            # Funeral Rules Section
            story.append(Paragraph("Funeral Support Rules", section_style))
            story.append(Paragraph("Financial assistance during bereavement", subsection_style))
            
            funeral_content = [
                Paragraph("<b>Eligibility Criteria:</b>", normal_style),
                Paragraph("Money will only be released for immediate family members:", normal_style),
                Spacer(1, 10),
            ]
            
            # Family members list
            family_members = [
                "✓ Mother", "✓ Father", "✓ Sister", "✓ Brother",
                "✓ Legal Guardian", "✓ Husband/Wife", "✓ Children"
            ]
            
            # Create two columns for family members
            col1 = family_members[:4]
            col2 = family_members[4:]
            
            family_table_data = []
            max_len = max(len(col1), len(col2))
            for i in range(max_len):
                row = []
                row.append(col1[i] if i < len(col1) else "")
                row.append(col2[i] if i < len(col2) else "")
                family_table_data.append(row)
            
            family_table = Table(family_table_data, colWidths=[2.5*inch, 2.5*inch])
            family_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            
            funeral_content.append(family_table)
            funeral_content.append(Spacer(1, 15))
            
            # Support amount highlight
            amount_style = ParagraphStyle(
                'AmountHighlight',
                parent=normal_style,
                fontSize=14,
                textColor=colors.HexColor('#2563eb'),
                alignment=1,
                fontName='Helvetica-Bold',
                backColor=colors.HexColor('#eff6ff'),
                borderColor=colors.HexColor('#3b82f6'),
                borderWidth=1,
                borderPadding=10,
                spaceAfter=15
            )
            
            funeral_content.append(Paragraph("<b>Support Amount: K50,000</b> per funeral incident", amount_style))
            
            # Add all funeral content to story
            for item in funeral_content:
                story.append(item)
            
            story.append(Spacer(1, 25))
            
            # Deceased Member Support Section (NEW)
            story.append(Paragraph("Deceased Member Support", section_style))
            story.append(Paragraph("Special support for contributing members", subsection_style))
            
            deceased_style = ParagraphStyle(
                'DeceasedHighlight',
                parent=normal_style,
                fontSize=14,
                textColor=colors.HexColor('#dc2626'),
                alignment=1,
                fontName='Helvetica-Bold',
                backColor=colors.HexColor('#fef2f2'),
                borderColor=colors.HexColor('#dc2626'),
                borderWidth=1,
                borderPadding=15,
                spaceAfter=10
            )
            
            clarification_style = ParagraphStyle(
                'ClarificationStyle',
                parent=normal_style,
                fontSize=9,
                textColor=colors.HexColor('#7f1d1d'),
                backColor=colors.HexColor('#fef2f2'),
                borderColor=colors.HexColor('#fca5a5'),
                borderWidth=(0, 0, 0, 3),
                borderPadding=(5, 5, 5, 10),
                leftIndent=5
            )
            
            story.append(Paragraph("<b>When a contributing member dies:</b>", normal_style))
            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>K80,000</b> support for the member's family", deceased_style))
            story.append(Spacer(1, 10))
            story.append(Paragraph(
                "<b>Clarification:</b> This support is specifically for when a member "
                "(someone who contributes regularly) passes away. The K80,000 is provided "
                "to support the member's family during this difficult time.",
                clarification_style
            ))
            
            story.append(Spacer(1, 30))
            
            # Contribution Rules Section
            story.append(Paragraph("Contribution Rules", section_style))
            story.append(Paragraph("Monthly contributions and penalties", subsection_style))
            
            # Important Notice
            warning_style = ParagraphStyle(
                'WarningStyle',
                parent=normal_style,
                fontSize=11,
                textColor=colors.HexColor('#92400e'),
                backColor=colors.HexColor('#fef3c7'),
                borderColor=colors.HexColor('#f59e0b'),
                borderWidth=1,
                borderPadding=15,
                spaceAfter=15
            )
            
            story.append(Paragraph(
                "<b>Important Notice:</b> Those who are eligible to receive the welfare money "
                "are only those who contribute; therefore, those who do not contribute are "
                "not eligible to receive the money.",
                warning_style
            ))
            story.append(Spacer(1, 15))
            
            # Contribution rules with examples
            contribution_rules = [
                {
                    'title': "1. Late Payment Penalties",
                    'content': "5% penalty per month for late contributions. Multiple months accumulate penalties.",
                    'example': "Example: 2 months late = 10% penalty"
                },
                {
                    'title': "2. Back Payments", 
                    'content': "Missed months must be paid for the specific period they were missed."
                },
                {
                    'title': "3. Benefits Calculation",
                    'content': "Number of times you can receive help = Number of months you've contributed.",
                    'example': "Example: 3 months contribution = 3 times eligible for support"
                },
                {
                    'title': "4. Partial Contributions",
                    'content': "For those contributing irregularly, penalties apply based on months skipped."
                }
            ]
            
            for rule in contribution_rules:
                story.append(Paragraph(f"<b>{rule['title']}</b>", normal_style))
                story.append(Paragraph(rule['content'], normal_style))
                if 'example' in rule:
                    example_style = ParagraphStyle(
                        'ExampleStyle',
                        parent=normal_style,
                        fontSize=9,
                        textColor=colors.HexColor('#92400e'),
                        backColor=colors.HexColor('#fffbeb'),
                        borderPadding=5,
                        leftIndent=10
                    )
                    story.append(Paragraph(rule['example'], example_style))
                story.append(Spacer(1, 10))
            
            story.append(PageBreak())
            
            # Sickness Rules Section
            story.append(Paragraph("Sickness Support", section_style))
            story.append(Paragraph("Medical and hospitalization assistance", subsection_style))
            
            sickness_content = [
                Paragraph("<b>Eligibility Criteria:</b>", normal_style),
                Paragraph("Support is provided for members who are <b>admitted in the hospital "
                         "for a couple of days</b>. Outpatient visits and minor illnesses are not covered.", 
                         normal_style),
                Spacer(1, 15),
            ]
            
            for item in sickness_content:
                story.append(item)
            
            story.append(Paragraph("<b>Medical Support: K15,000</b> per hospital admission", amount_style))
            
            story.append(Spacer(1, 30))
            
            # Wedding Rules Section
            story.append(Paragraph("Wedding Support", section_style))
            story.append(Paragraph("Celebratory financial assistance", subsection_style))
            
            wedding_content = [
                Paragraph("<b>Support Amount: K80,000</b> per wedding ceremony", amount_style),
                Spacer(1, 10),
                Paragraph("<i>Available to contributing members for their own wedding ceremony</i>", normal_style)
            ]
            
            for item in wedding_content:
                story.append(item)
            
            story.append(Spacer(1, 30))
            
            # Key Points Section
            story.append(Paragraph("Key Points to Remember", section_style))
            
            key_points = [
                "Regular contributions ensure eligibility for support when needed",
                "Pay on time to avoid 5% monthly penalties on late contributions",
                "Benefits are proportional to your contributions",
                "K80,000 support when a contributing member passes away",
                "Immediate family coverage for funerals including spouses and children",
                "K15,000 for hospital admissions requiring multiple days",
                "K80,000 wedding support for members getting married",
                "No welfare money for non-contributors; only personal donations allowed"
            ]
            
            for point in key_points:
                if "K80,000" in point and "member" in point:
                    # Highlight member death support
                    point_style = ParagraphStyle(
                        'ImportantPoint',
                        parent=bullet_style,
                        textColor=colors.HexColor('#dc2626'),
                        fontName='Helvetica-Bold'
                    )
                    story.append(Paragraph(f"• {point}", point_style))
                else:
                    story.append(Paragraph(f"• {point}", bullet_style))
            
            story.append(Spacer(1, 30))
            
            # Penalty Calculation Guide
            story.append(Paragraph("Penalty Calculation Guide", subsection_style))
            
            penalty_content = [
                Paragraph("<b>Penalty Rate: 5% per month</b>", normal_style),
                Paragraph("<b>Formula:</b> Penalty = Monthly Contribution × (5% × Number of Late Months)", normal_style),
                Spacer(1, 10),
            ]
            
            for item in penalty_content:
                story.append(item)
            
            # Example table
            penalty_examples = [
                ['Late Months', 'Penalty %', 'Penalty Amount', 'Total to Pay'],
                ['1 month', '5%', 'K50', 'K1,050'],
                ['2 months', '10%', 'K100', 'K1,100'],
                ['3 months', '15%', 'K150', 'K1,150'],
                ['6 months', '30%', 'K300', 'K1,300']
            ]
            
            penalty_table = Table(penalty_examples, colWidths=[1*inch, 1*inch, 1.5*inch, 1.5*inch])
            penalty_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4b5563')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f9fafb')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
            ]))
            
            story.append(penalty_table)
            story.append(Spacer(1, 30))
            
            # Benefits Eligibility Guide
            story.append(Paragraph("Benefits Eligibility Guide", subsection_style))
            
            benefits_content = [
                Paragraph("<b>1:1 Benefit Ratio Rule:</b>", normal_style),
                Paragraph("Each month of contribution = One time eligible for support", normal_style),
                Spacer(1, 15),
                Paragraph("<b>Scenario Examples:</b>", normal_style),
            ]
            
            for item in benefits_content:
                story.append(item)
            
            scenarios = [
                {
                    'title': "Scenario 1:",
                    'content': "6 months contributed = Eligible for support 6 times total "
                              "(any combination of funeral, sickness, wedding, or member death support)"
                },
                {
                    'title': "Scenario 2:",
                    'content': "2 months contributed = Eligible for support 2 times only. "
                              "Once used, must contribute more to be eligible again"
                },
                {
                    'title': "Scenario 3:",
                    'content': "Member death support counts as one support instance. "
                              "If a member contributed for 5 months and passes away:"
                              "<br/>• Family receives K80,000 support"
                              "<br/>• This counts as 1 support instance used"
                              "<br/>• Member had contributed for 4 other potential support instances"
                }
            ]
            
            for scenario in scenarios:
                story.append(Paragraph(f"<b>{scenario['title']}</b>", normal_style))
                story.append(Paragraph(scenario['content'], normal_style))
                story.append(Spacer(1, 10))
            
            story.append(Spacer(1, 30))
            
            # Support Comparison Table
            story.append(Paragraph("Support Amounts Comparison", subsection_style))
            
            comparison_data = [
                ['Support Type', 'Amount', 'Eligibility'],
                ['Funeral Support', 'K50,000', 'Immediate family members'],
                ['<font color="#dc2626">Member Death Support</font>', '<font color="#dc2626"><b>K80,000</b></font>', 
                 'When a contributing member passes away'],
                ['Wedding Support', 'K80,000', "Member's own wedding"],
                ['Sickness Support', 'K15,000', 'Hospital admission (multiple days)']
            ]
            
            comparison_table = Table(comparison_data, colWidths=[2*inch, 1.5*inch, 2.5*inch])
            comparison_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#fef2f2')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#d1d5db')),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            story.append(comparison_table)
            story.append(Spacer(1, 40))
            
            # Footer
            footer_style = ParagraphStyle(
                'FooterStyle',
                parent=normal_style,
                fontSize=8,
                textColor=colors.HexColor('#6b7280'),
                alignment=1,
                spaceBefore=20,
                borderColor=colors.HexColor('#e5e7eb'),
                borderWidth=(1, 0, 0, 0),
                borderPadding=(10, 0, 0, 0)
            )
            
            footer_content = [
                Paragraph("<b>Confidential - For Mzugoss Members Only</b>", footer_style),
                Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d at %H:%M')} | Version 2.0", footer_style),
                Paragraph("These rules are designed to ensure fair and sustainable welfare support "
                         "for all contributing members.", footer_style),
                Paragraph("For any clarifications, please contact the welfare committee.", footer_style)
            ]
            
            for item in footer_content:
                story.append(item)
            
            # Build PDF
            doc.build(story)
            
            # Get the value of the BytesIO buffer
            pdf = buffer.getvalue()
            buffer.close()
            
            return pdf
            
        except Exception as e:
            current_app.logger.error(f"PDF generation failed: {str(e)}")
            raise Exception(f"Failed to generate PDF: {str(e)}")


class ShareUtils:
    """Utility class for sharing functionality with updated figures"""
    
    @staticmethod
    def get_share_text(share_type='general'):
        """Get pre-formatted share text with updated figures"""
        from flask import url_for
        
        base_url = url_for('main.welfare_rules', _external=True)
        
        share_texts = {
            'whatsapp': {
                'text': f"📋 *Mzugoss Welfare Rules v2.0*\n\n"
                       f"Updated community welfare rules and contribution system:\n"
                       f"{base_url}\n\n"
                       f"*Updated Support Amounts:*\n"
                       f"• Monthly Contribution: K1,000\n"
                       f"• Funeral Support: K50,000\n" 
                       f"• Wedding Support: K80,000\n"
                       f"• Sickness Support: K15,000\n"
                       f"• *NEW* Member Death Support: K80,000\n\n"
                       f"*Key Rule:* When a contributing member passes away, "
                       f"their family receives K80,000 in support.\n\n"
                       f"Please review the full updated rules at the link above.",
                'url': base_url
            },
            'email': {
                'subject': "Updated: Mzugoss Welfare Rules & Guidelines v2.0",
                'body': f"""Hello,

I wanted to share the updated Mzugoss Welfare Rules with you. We have revised our support amounts and added new benefits:

{base_url}

Updated Support Amounts:
• Monthly Contribution: K1,000
• Funeral Support: K50,000 (immediate family only)
• Wedding Support: K80,000  
• Sickness Support: K15,000 (hospital admission required)
• Member Death Support: K80,000 (NEW)

Important Updates:
- When a contributing member passes away, their family receives K80,000 support
- Increased wedding support to K80,000
- Enhanced sickness support to K15,000
- Funeral support increased to K50,000

Key Rules:
- Benefits are proportional to months contributed (1 month = 1 support instance)
- Late payment penalty: 5% per month
- Non-contributors receive no welfare support
- Immediate family coverage for funerals

Please review the full updated rules at the link above.

Best regards""",
                'html_body': f"""<html>
<body>
<p>Hello,</p>
<p>I wanted to share the updated Mzugoss Welfare Rules with you. We have revised our support amounts and added new benefits:</p>
<p><a href="{base_url}">{base_url}</a></p>

<h3>Updated Support Amounts:</h3>
<ul>
<li><strong>Monthly Contribution:</strong> K1,000</li>
<li><strong>Funeral Support:</strong> K50,000 (immediate family only)</li>
<li><strong>Wedding Support:</strong> K80,000</li>
<li><strong>Sickness Support:</strong> K15,000 (hospital admission required)</li>
<li><strong style="color: #dc2626;">Member Death Support:</strong> K80,000 (NEW)</li>
</ul>

<h3>Important Updates:</h3>
<ul>
<li>When a contributing member passes away, their family receives K80,000 support</li>
<li>Increased wedding support to K80,000</li>
<li>Enhanced sickness support to K15,000</li>
<li>Funeral support increased to K50,000</li>
</ul>

<h3>Key Rules:</h3>
<ul>
<li>Benefits are proportional to months contributed (1 month = 1 support instance)</li>
<li>Late payment penalty: 5% per month</li>
<li>Non-contributors receive no welfare support</li>
<li>Immediate family coverage for funerals</li>
</ul>

<p>Please review the full updated rules at the link above.</p>
<p>Best regards</p>
</body>
</html>"""
            },
            'sms': {
                'text': f"Mzugoss Welfare Rules v2.0: {base_url} "
                       f"Monthly: K1000, Funeral: K50000, Wedding: K80000, Sickness: K15000, Member Death: K80000"
            },
            'twitter': {
                'text': f"Updated Mzugoss Welfare Rules v2.0!\n"
                       f"New: Member Death Support K80,000\n"
                       f"Wedding: K80,000 | Funeral: K50,000\n"
                       f"Sickness: K15,000\n"
                       f"{base_url}"
            },
            'facebook': {
                'text': f"Check out our updated Mzugoss Welfare Rules v2.0!\n\n"
                       f"• Member Death Support: K80,000 (NEW!)\n"
                       f"• Wedding Support: K80,000\n"
                       f"• Funeral Support: K50,000\n"
                       f"• Sickness Support: K15,000\n"
                       f"• Monthly Contribution: K1,000\n\n"
                       f"When a contributing member passes away, their family receives K80,000 in support.\n\n"
                       f"View all rules: {base_url}"
            },
            'general': {
                'text': f"Updated Mzugoss Welfare Rules v2.0: {base_url}",
                'url': base_url
            }
        }
        
        return share_texts.get(share_type, share_texts['general'])
    
    @staticmethod
    def get_share_url(share_type, text_data=None):
        """Generate share URLs for different platforms"""
        if text_data is None:
            text_data = ShareUtils.get_share_text(share_type)
        
        if share_type == 'whatsapp':
            text = text_data['text']
            url = text_data.get('url', '')
            return f"https://wa.me/?text={ShareUtils._url_encode(text)}"
        
        elif share_type == 'twitter':
            text = text_data['text']
            return f"https://twitter.com/intent/tweet?text={ShareUtils._url_encode(text)}"
        
        elif share_type == 'facebook':
            text = text_data['text']
            url = text_data.get('url', '')
            return f"https://www.facebook.com/sharer/sharer.php?u={ShareUtils._url_encode(url)}&quote={ShareUtils._url_encode(text)}"
        
        elif share_type == 'email':
            subject = text_data['subject']
            body = text_data['body']
            return f"mailto:?subject={ShareUtils._url_encode(subject)}&body={ShareUtils._url_encode(body)}"
        
        elif share_type == 'sms':
            text = text_data['text']
            return f"sms:?body={ShareUtils._url_encode(text)}"
        
        return text_data.get('url', '')
    
    @staticmethod
    def _url_encode(text):
        """URL encode text for sharing"""
        import urllib.parse
        return urllib.parse.quote(text)


class WelfareRulesData:
    """Centralized data store for welfare rules to ensure consistency"""
    
    VERSION = "2.0"
    
    @staticmethod
    def get_summary():
        """Get summary of welfare rules"""
        return {
            'monthly_contribution': 'K1,000',
            'funeral_support': 'K50,000',
            'wedding_support': 'K80,000',
            'sickness_support': 'K15,000',
            'member_death_support': 'K80,000',
            'version': WelfareRulesData.VERSION,
            'last_updated': '2025'
        }
    
    @staticmethod
    def get_funeral_eligibility():
        """Get list of eligible family members for funeral support"""
        return [
            "Mother", "Father", "Sister", "Brother",
            "Legal Guardian", "Husband/Wife", "Children"
        ]
    
    @staticmethod
    def get_penalty_info():
        """Get penalty calculation information"""
        return {
            'rate': '5%',
            'period': 'per month',
            'examples': [
                {'months': 1, 'penalty': '5%', 'amount': 'K50', 'total': 'K1,050'},
                {'months': 2, 'penalty': '10%', 'amount': 'K100', 'total': 'K1,100'},
                {'months': 3, 'penalty': '15%', 'amount': 'K150', 'total': 'K1,150'},
                {'months': 6, 'penalty': '30%', 'amount': 'K300', 'total': 'K1,300'}
            ]
        }
    
    @staticmethod
    def get_benefit_scenarios():
        """Get benefit calculation scenarios"""
        return [
            {
                'title': 'Scenario 1',
                'months': 6,
                'description': '6 months contributed = Eligible for support 6 times total',
                'details': 'Can be any combination of funeral, sickness, wedding, or member death support'
            },
            {
                'title': 'Scenario 2',
                'months': 2,
                'description': '2 months contributed = Eligible for support 2 times only',
                'details': 'Once used, must contribute more to be eligible again'
            },
            {
                'title': 'Scenario 3',
                'months': 5,
                'description': 'Member death support scenario',
                'details': [
                    'If a member contributed for 5 months and passes away:',
                    '- Family receives K80,000 support',
                    '- This counts as 1 support instance used',
                    '- Member had contributed for 4 other potential support instances'
                ]
            }
        ]