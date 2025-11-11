# app/utils/pdf_utils.py
import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from flask import current_app

class PDFGenerator:
    """Utility class for generating PDF documents using ReportLab"""
    
    @staticmethod
    def generate_welfare_rules_pdf():
        """
        Generate PDF from welfare rules using ReportLab
        
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
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            
            # Container for the 'Flowable' objects
            story = []
            
            # Get styles
            styles = getSampleStyleSheet()
            
            # Title Style
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                textColor=colors.HexColor('#2563eb'),
                alignment=1  # Center aligned
            )
            
            # Heading Style
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                spaceAfter=12,
                textColor=colors.HexColor('#1e293b'),
                borderPadding=5,
                borderColor=colors.HexColor('#2563eb'),
                borderWidth=1
            )
            
            # Subheading Style
            subheading_style = ParagraphStyle(
                'CustomSubheading',
                parent=styles['Heading3'],
                fontSize=14,
                spaceAfter=6,
                textColor=colors.HexColor('#374151')
            )
            
            # Normal Style
            normal_style = styles['Normal']
            
            # Add Title
            title = Paragraph("Mzugoss Welfare Rules & Guidelines", title_style)
            story.append(title)
            
            # Add date
            date_text = Paragraph(f"Last Updated: {datetime.now().strftime('%Y-%m-%d')}", normal_style)
            story.append(date_text)
            story.append(Spacer(1, 20))
            
            # Quick Summary Section
            story.append(Paragraph("Quick Summary", heading_style))
            
            # Fees Table
            fee_data = [
                ['Service', 'Amount', 'Period'],
                ['Monthly Contribution', 'K1,000', 'per month'],
                ['Funeral Support', 'K20,000', 'per incident'],
                ['Wedding Support', 'K50,000', 'per wedding'],
                ['Sickness Support', 'K5,000', 'per admission']
            ]
            
            fee_table = Table(fee_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
            fee_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f8fafc')),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1'))
            ]))
            story.append(fee_table)
            story.append(Spacer(1, 20))
            
            # Funeral Rules Section
            story.append(Paragraph("Funeral Support Rules", heading_style))
            story.append(Paragraph("Financial assistance during bereavement", subheading_style))
            
            funeral_rules = [
                "Money will only be released for immediate family members:",
                "• Mother, Father, Sister, Brother",
                "• Legal Guardian, Husband/Wife, Children",
                "",
                "Support Amount: K20,000 per funeral incident"
            ]
            
            for rule in funeral_rules:
                story.append(Paragraph(rule, normal_style))
                story.append(Spacer(1, 6))
            
            story.append(Spacer(1, 15))
            
            # Contribution Rules Section
            story.append(Paragraph("Contribution Rules", heading_style))
            story.append(Paragraph("Monthly contributions and penalties", subheading_style))
            
            # Important Notice
            important_style = ParagraphStyle(
                'Important',
                parent=normal_style,
                backColor=colors.HexColor('#fef3c7'),
                borderColor=colors.HexColor('#f59e0b'),
                borderWidth=1,
                borderPadding=10,
                leftIndent=10
            )
            
            story.append(Paragraph(
                "<b>Important Notice:</b> Non-contributors will not receive any welfare money. "
                "There will be no separate contributions for people who do not contribute regularly.",
                important_style
            ))
            story.append(Spacer(1, 12))
            
            contribution_rules = [
                "<b>1. Late Payment Penalties</b>",
                "5% penalty per month for late contributions. Multiple months accumulate penalties.",
                "<i>Example: 2 months late = 10% penalty</i>",
                "",
                "<b>2. Back Payments</b>", 
                "Missed months must be paid for the specific period they were missed.",
                "",
                "<b>3. Benefits Calculation</b>",
                "Number of times you can receive help = Number of months you've contributed.",
                "<i>Example: 3 months contribution = 3 times eligible for support</i>",
                "",
                "<b>4. Partial Contributions</b>",
                "For irregular contributions, penalties apply based on months skipped."
            ]
            
            for rule in contribution_rules:
                if rule.startswith("<b>") or rule.startswith("<i>"):
                    story.append(Paragraph(rule, normal_style))
                else:
                    story.append(Paragraph(rule, normal_style))
                story.append(Spacer(1, 4))
            
            story.append(PageBreak())
            
            # Sickness Rules Section
            story.append(Paragraph("Sickness Support", heading_style))
            story.append(Paragraph("Medical and hospitalization assistance", subheading_style))
            
            sickness_rules = [
                "<b>Eligibility Criteria:</b>",
                "Support is provided for members who are admitted in the hospital for a couple of days.",
                "Outpatient visits and minor illnesses are not covered.",
                "",
                "<b>Support Amount:</b> K5,000 per hospital admission"
            ]
            
            for rule in sickness_rules:
                story.append(Paragraph(rule, normal_style))
                story.append(Spacer(1, 6))
            
            story.append(Spacer(1, 15))
            
            # Wedding Rules Section
            story.append(Paragraph("Wedding Support", heading_style))
            story.append(Paragraph("Celebratory financial assistance", subheading_style))
            
            wedding_rules = [
                "<b>Support Amount:</b> K50,000 per wedding ceremony",
                "Available to contributing members for their own wedding ceremony"
            ]
            
            for rule in wedding_rules:
                story.append(Paragraph(rule, normal_style))
                story.append(Spacer(1, 6))
            
            story.append(Spacer(1, 20))
            
            # Key Points Section
            story.append(Paragraph("Key Points to Remember", heading_style))
            
            key_points = [
                "• Regular contributions ensure eligibility for support when needed",
                "• Pay on time to avoid 5% monthly penalties",
                "• Benefits are proportional to your contributions", 
                "• Immediate family coverage for funerals",
                "• Sickness support only for hospital admissions",
                "• No welfare money for non-contributors"
            ]
            
            for point in key_points:
                story.append(Paragraph(point, normal_style))
                story.append(Spacer(1, 4))
            
            story.append(Spacer(1, 20))
            
            # Footer
            footer_style = ParagraphStyle(
                'Footer',
                parent=normal_style,
                fontSize=8,
                textColor=colors.HexColor('#666666'),
                alignment=1
            )
            
            story.append(Paragraph(
                f"Confidential - For Mzugoss Members Only | Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                footer_style
            ))
            
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
    """Utility class for sharing functionality"""
    
    @staticmethod
    def get_share_text(share_type='general'):
        """Get pre-formatted share text"""
        from flask import url_for
        
        base_url = url_for('main.welfare_rules', _external=True)
        
        share_texts = {
            'whatsapp': {
                'text': f"📋 *Mzugoss Welfare Rules*\n\n"
                       f"Here are our community welfare rules and contribution system:\n"
                       f"{base_url}\n\n"
                       f"*Key Fees:*\n"
                       f"• Monthly: K1,000\n"
                       f"• Funeral: K20,000\n" 
                       f"• Wedding: K50,000\n"
                       f"• Sickness: K5,000\n\n"
                       f"Please review the full rules at the link above.",
                'url': base_url
            },
            'email': {
                'subject': "Mzugoss Welfare Rules & Guidelines",
                'body': f"""Hello,

I wanted to share the Mzugoss Welfare Rules with you. These outline our community's contribution system and benefits:

{base_url}

Key Information:
• Monthly Contribution: K1,000
• Funeral Support: K20,000 (immediate family only)
• Wedding Support: K50,000  
• Sickness Support: K5,000 (hospital admission required)
• Late Payment Penalty: 5% per month

Important Rules:
- Benefits are proportional to months contributed
- Non-contributors receive no welfare support
- Immediate family coverage for funerals

Please review the full rules at the link above.

Best regards"""
            },
            'sms': {
                'text': f"Mzugoss Welfare Rules: {base_url} "
                       f"Monthly: K1000, Funeral: K20000, Wedding: K50000, Sickness: K5000"
            },
            'general': {
                'text': f"Check out Mzugoss Welfare Rules: {base_url}",
                'url': base_url
            }
        }
        
        return share_texts.get(share_type, share_texts['general'])