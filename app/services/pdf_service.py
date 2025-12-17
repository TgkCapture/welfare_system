# app/services/pdf_service.py
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from flask import current_app
import logging
import pandas as pd

logger = logging.getLogger(__name__)

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
                bottomMargin=72,
                title="Mzugoss Welfare Rules"
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
                spaceAfter=30,
                textColor=colors.HexColor('#2563eb'),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontSize=16,
                spaceAfter=12,
                textColor=colors.HexColor('#1e293b'),
                fontName='Helvetica-Bold',
                borderPadding=5,
                borderColor=colors.HexColor('#2563eb'),
                borderWidth=1,
                leftIndent=10
            )
            
            subheading_style = ParagraphStyle(
                'CustomSubheading',
                parent=styles['Heading3'],
                fontSize=14,
                spaceAfter=6,
                textColor=colors.HexColor('#374151'),
                fontName='Helvetica-Bold'
            )
            
            normal_style = ParagraphStyle(
                'Normal',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=8,
                textColor=colors.HexColor('#4b5563'),
                leading=14
            )
            
            bullet_style = ParagraphStyle(
                'Bullet',
                parent=normal_style,
                leftIndent=20,
                firstLineIndent=-10,
                spaceBefore=4,
                spaceAfter=4
            )
            
            important_style = ParagraphStyle(
                'Important',
                parent=normal_style,
                backColor=colors.HexColor('#fef3c7'),
                borderColor=colors.HexColor('#f59e0b'),
                borderWidth=1,
                borderPadding=10,
                leftIndent=10,
                rightIndent=10,
                spaceBefore=10,
                spaceAfter=10
            )
            
            footer_style = ParagraphStyle(
                'Footer',
                parent=normal_style,
                fontSize=8,
                textColor=colors.HexColor('#666666'),
                alignment=TA_CENTER
            )
            
            # Add Title
            title = Paragraph("Mzugoss Welfare Rules & Guidelines", title_style)
            story.append(title)
            
            # Add date and version
            date_text = f"Last Updated: {datetime.now().strftime('%Y-%m-%d')} | Version {current_app.version if hasattr(current_app, 'version') else '1.0'}"
            story.append(Paragraph(date_text, normal_style))
            story.append(Spacer(1, 20))
            
            # Quick Summary Section
            story.append(Paragraph("Quick Summary", heading_style))
            
            # Fees Table
            fee_data = [
                ['Service', 'Amount', 'Period'],
                ['Monthly Contribution', 'K1,000', 'per month'],
                ['Funeral Support', 'K50,000', 'per incident'],
                ['Wedding Support', 'K80,000', 'per wedding'],
                ['Sickness Support', 'K15,000', 'per admission'],
                ['Member Death Support', 'K80,000', 'per member']
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
                ('FONTSIZE', (0, 1), (-1, -1), 11),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8)
            ]))
            story.append(fee_table)
            story.append(Spacer(1, 20))
            
            # Important Notice
            story.append(Paragraph(
                "<b>Important Notice:</b> Only contributing members are eligible for welfare benefits. "
                "Those who do not contribute regularly cannot receive any welfare money.",
                important_style
            ))
            
            story.append(Spacer(1, 20))
            
            # Funeral Rules Section
            story.append(Paragraph("Funeral Support Rules", heading_style))
            story.append(Paragraph("Financial assistance during bereavement", subheading_style))
            
            funeral_content = [
                "Money will only be released for immediate family members:",
                "• Mother, Father, Sister, Brother",
                "• Legal Guardian, Husband/Wife, Children",
                "",
                "<b>Support Amount:</b> K50,000 per funeral incident",
                "",
                "<b>Note:</b> Documentation may be required to verify relationship."
            ]
            
            for item in funeral_content:
                if item.startswith("•"):
                    story.append(Paragraph(item, bullet_style))
                elif item.startswith("<b>"):
                    story.append(Paragraph(item, normal_style))
                else:
                    story.append(Paragraph(item, normal_style))
            
            story.append(Spacer(1, 15))
            
            # Deceased Member Support Section
            story.append(Paragraph("Deceased Member Support", heading_style))
            story.append(Paragraph("Support for when a contributing member passes away", subheading_style))
            
            deceased_content = [
                "<b>Special Support:</b> K80,000 support for family",
                "",
                "<b>Clarification:</b> This support is specifically for when a member (someone who contributes regularly) passes away. The K80,000 is provided to support the member's family during this difficult time."
            ]
            
            for item in deceased_content:
                story.append(Paragraph(item, normal_style))
            
            story.append(Spacer(1, 15))
            
            # Page Break
            story.append(PageBreak())
            
            # Contribution Rules Section
            story.append(Paragraph("Contribution Rules", heading_style))
            story.append(Paragraph("Monthly contributions and penalties", subheading_style))
            
            contribution_content = [
                "<b>1. Monthly Contribution:</b> K1,000 per month",
                "<b>2. Late Payment Penalties:</b> 5% penalty per month for late contributions.",
                "<i>Example: 2 months late = 10% penalty</i>",
                "",
                "<b>3. Back Payments:</b> Missed months must be paid for the specific period they were missed.",
                "",
                "<b>4. Benefits Calculation:</b> Number of times you can receive help = Number of months you've contributed.",
                "<i>Example: 3 months contribution = 3 times eligible for support</i>"
            ]
            
            for item in contribution_content:
                story.append(Paragraph(item, normal_style))
            
            story.append(Spacer(1, 15))
            
            # Sickness Rules Section
            story.append(Paragraph("Sickness Support", heading_style))
            story.append(Paragraph("Medical and hospitalization assistance", subheading_style))
            
            sickness_content = [
                "<b>Eligibility Criteria:</b>",
                "Support is provided for members who are admitted in the hospital for a couple of days.",
                "Outpatient visits and minor illnesses are not covered.",
                "",
                "<b>Support Amount:</b> K15,000 per hospital admission",
                "",
                "<b>Documentation:</b> Hospital admission records may be required."
            ]
            
            for item in sickness_content:
                story.append(Paragraph(item, normal_style))
            
            story.append(Spacer(1, 15))
            
            # Wedding Rules Section
            story.append(Paragraph("Wedding Support", heading_style))
            story.append(Paragraph("Celebratory financial assistance", subheading_style))
            
            wedding_content = [
                "<b>Support Amount:</b> K80,000 per wedding ceremony",
                "Available to contributing members for their own wedding ceremony",
                "",
                "<b>Note:</b> One-time support per member for wedding ceremonies."
            ]
            
            for item in wedding_content:
                story.append(Paragraph(item, normal_style))
            
            story.append(Spacer(1, 20))
            
            # Key Points Section
            story.append(Paragraph("Key Points to Remember", heading_style))
            
            key_points = [
                "• Regular contributions ensure eligibility for support when needed",
                "• Pay on time to avoid 5% monthly penalties",
                "• Benefits are proportional to your contributions",
                "• Immediate family coverage for funerals",
                "• Sickness support: K15,000 for hospital admissions",
                "• Wedding support: K80,000 per ceremony",
                "• Member death support: K80,000 for family",
                "• No welfare money for non-contributors"
            ]
            
            for point in key_points:
                story.append(Paragraph(point, bullet_style))
            
            story.append(Spacer(1, 20))
            
            # Footer
            footer_text = [
                f"Confidential - For Mzugoss Members Only",
                f"Generated on: {datetime.now().strftime('%Y-%m-%d at %H:%M')}",
                "These rules are designed to ensure fair and sustainable welfare support for all contributing members.",
                "For any clarifications, please contact the welfare committee."
            ]
            
            for line in footer_text:
                story.append(Paragraph(line, footer_style))
            
            # Build PDF
            doc.build(story)
            
            # Get the value of the BytesIO buffer
            pdf = buffer.getvalue()
            buffer.close()
            
            logger.info("Successfully generated welfare rules PDF")
            return pdf
            
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate PDF: {str(e)}")
    
    @staticmethod
    def generate_contribution_report_pdf(data):
        """
        Generate a PDF report from contribution data
        
        Args:
            data (dict): Contribution data from ExcelParser
            
        Returns:
            bytes: PDF file content
        """
        try:
            buffer = io.BytesIO()
            
            # Create PDF document
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=50,
                leftMargin=50,
                topMargin=50,
                bottomMargin=50,
                title=f"Contributions Report - {data.get('month', '')} {data.get('year', '')}"
            )
            
            story = []
            styles = getSampleStyleSheet()
            
            # Custom Styles
            title_style = ParagraphStyle(
                'ReportTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=20,
                textColor=colors.HexColor('#2563eb'),
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            section_style = ParagraphStyle(
                'Section',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=12,
                textColor=colors.HexColor('#1e293b'),
                fontName='Helvetica-Bold',
                leftIndent=10
            )
            
            normal_style = ParagraphStyle(
                'ReportNormal',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                leading=12
            )
            
            # Title
            title = Paragraph(f"MZUGOSS CLASS OF 2018 MONTHLY CONTRIBUTIONS REPORT", title_style)
            story.append(title)
            story.append(Spacer(1, 10))
            
            # Report Period
            period = Paragraph(f"Report for {data.get('month', '')} {data.get('year', '')}", section_style)
            story.append(period)
            story.append(Spacer(1, 15))
            
            # Summary Statistics
            story.append(Paragraph("SUMMARY STATISTICS", section_style))
            
            summary_data = [
                ["Total Contributions:", f"MWK {data.get('total_contributions', 0):,.2f}"],
                ["Number of Contributors:", str(data.get('num_contributors', 0))],
                ["Number of Defaulters:", str(data.get('num_missing', 0))]
            ]
            
            # Add optional financial info
            money_dispensed = data.get('money_dispensed')
            if money_dispensed is not None:
                try:
                    summary_data.append(["Money Dispensed:", f"MWK {float(money_dispensed):,.2f}"])
                except (ValueError, TypeError):
                    summary_data.append(["Money Dispensed:", str(money_dispensed)])
            
            total_book_balance = data.get('total_book_balance')
            if total_book_balance is not None:
                try:
                    summary_data.append(["Total Book Balance:", f"MWK {float(total_book_balance):,.2f}"])
                except (ValueError, TypeError):
                    summary_data.append(["Total Book Balance:", str(total_book_balance)])
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold')
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 20))
            
            # Paid Members Section
            story.append(Paragraph("PAID MEMBERS", section_style))
            
            # Get paid members data
            df = data.get('data')
            month_col = data.get('month_col')
            name_col = data.get('name_col')
            
            if isinstance(df, pd.DataFrame) and not df.empty and month_col and name_col:
                paid_df = df[~df[month_col].isna()]
                
                if not paid_df.empty:
                    # Create table data
                    table_data = [["Name", "Amount (MWK)"]]
                    
                    for _, row in paid_df.iterrows():
                        name = str(row[name_col])
                        amount = row[month_col]
                        try:
                            amount_str = f"{float(amount):,.2f}"
                        except (ValueError, TypeError):
                            amount_str = str(amount)
                        table_data.append([name, amount_str])
                    
                    # Create table
                    paid_table = Table(table_data, colWidths=[3.5*inch, 1.5*inch])
                    paid_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 11),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
                        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('TOPPADDING', (0, 1), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
                    ]))
                    story.append(paid_table)
                else:
                    story.append(Paragraph("No paid members for this period", normal_style))
            else:
                story.append(Paragraph("No member data available", normal_style))
            
            story.append(Spacer(1, 20))
            
            # Defaulters Section (if any)
            num_missing = data.get('num_missing', 0)
            if num_missing > 0:
                story.append(Paragraph("DEFAULTERS", section_style))
                
                # Get defaulters list
                defaulters = data.get('defaulters', [])
                if defaulters:
                    defaulter_data = [["Name"]]
                    defaulter_data.extend([[str(name)] for name in defaulters])
                    
                    defaulter_table = Table(defaulter_data, colWidths=[5*inch])
                    defaulter_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 11),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef2f2')),
                        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#fecaca')),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                        ('TOPPADDING', (0, 1), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 4)
                    ]))
                    story.append(defaulter_table)
            
            story.append(Spacer(1, 20))
            
            # Footer
            footer = Paragraph(
                f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
                f"Version {current_app.version if hasattr(current_app, 'version') else '1.0'}",
                ParagraphStyle(
                    'Footer',
                    parent=normal_style,
                    fontSize=8,
                    textColor=colors.HexColor('#666666'),
                    alignment=TA_CENTER
                )
            )
            story.append(footer)
            
            # Build PDF
            doc.build(story)
            
            pdf = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Successfully generated contribution report PDF for {data.get('month', '')} {data.get('year', '')}")
            return pdf
            
        except Exception as e:
            logger.error(f"Contribution report PDF generation failed: {str(e)}", exc_info=True)
            raise Exception(f"Failed to generate contribution report PDF: {str(e)}")