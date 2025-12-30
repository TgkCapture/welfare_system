# app/services/report_generator.py
from fpdf import FPDF
from datetime import datetime
import os
from flask import current_app

class ReportPDF(FPDF):
    """Custom PDF generator for contribution reports"""
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'MZUGOSS CLASS OF 2018 MONTHLY CONTRIBUTIONS REPORT', 0, 1, 'C')
        self.ln(10)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

class ReportGenerator:
    @staticmethod
    def generate_contribution_report(data, report_folder):
        """Generate a PDF report from parsed contribution data"""
        pdf = ReportPDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Set colors and fonts
        pdf.set_fill_color(240, 240, 240)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", size=12)
        
        # Report Header
        ReportGenerator._add_report_header(pdf, data)
        
        # Summary Statistics
        ReportGenerator._add_summary_section(pdf, data)
        
        # Paid Members Section
        ReportGenerator._add_paid_members_section(pdf, data)
        
        # Defaulters Section
        if data['num_missing'] > 0:
            ReportGenerator._add_defaulters_section(pdf, data)
        
        # Footer
        ReportGenerator._add_report_footer(pdf)
        
        # Save the file
        filename = f"contributions_report_{data['year']}_{data['month']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        report_path = os.path.join(report_folder, filename)
        pdf.output(report_path)
        
        return report_path
    
    @staticmethod
    def _add_report_header(pdf, data):
        """Add report header section"""
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, f"Report for {data['month']} {data['year']}", 0, 1, 'L')
        pdf.ln(5)
    
    @staticmethod
    def _add_summary_section(pdf, data):
        """Add summary statistics section"""
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "SUMMARY STATISTICS", 0, 1, 'L')
        pdf.set_font("Arial", size=12)
        
        pdf.set_fill_color(220, 220, 220)
        summary_items = [
            ("Total Contributions:", f"MWK {data['total_contributions']:,.2f}"),
            ("Number of Contributors:", str(data['num_contributors'])),
            ("Number of Defaulters:", str(data['num_missing']))
        ]
        
        if data.get('money_dispensed') is not None:
            money_dispensed = ReportGenerator._format_amount(data['money_dispensed'])
            summary_items.append(("Money Dispensed:", f"MWK {money_dispensed}"))
        
        if data.get('total_book_balance') is not None:
            total_book_balance = ReportGenerator._format_amount(data['total_book_balance'])
            summary_items.append(("Total Book Balance:", f"MWK {total_book_balance}"))
        
        for label, value in summary_items:
            pdf.cell(60, 10, label, 1, 0, 'L', 1)
            pdf.cell(0, 10, value, 1, 1, 'L')
        
        pdf.ln(10)
    
    @staticmethod
    def _add_paid_members_section(pdf, data):
        """Add paid members section"""
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "PAID MEMBERS", 0, 1, 'L')
        pdf.set_font("Arial", size=12)
        
        paid_df = data['data'][~data['data'][data['month_col']].isna()]
        
        if not paid_df.empty:
            pdf.set_fill_color(200, 220, 255)
            pdf.cell(120, 10, "Name", 1, 0, 'C', 1)
            pdf.cell(0, 10, "Amount (MWK)", 1, 1, 'C', 1)
            pdf.set_fill_color(255, 255, 255)
            
            for _, row in paid_df.iterrows():
                pdf.cell(120, 10, str(row[data['name_col']]), 1, 0, 'L')
                amount = float(row[data['month_col']])
                pdf.cell(0, 10, f"{amount:,.2f}", 1, 1, 'R')
        else:
            pdf.cell(0, 10, "No paid members for this period", 0, 1)
        
        pdf.ln(10)
    
    @staticmethod
    def _add_defaulters_section(pdf, data):
        """Add defaulters section"""
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "DEFAULTERS", 0, 1, 'L')
        pdf.set_font("Arial", size=12)
        
        pdf.set_fill_color(255, 200, 200)
        pdf.cell(0, 10, "Name", 1, 1, 'C', 1)
        pdf.set_fill_color(255, 255, 255)
        
        for name in data['defaulters']:
            pdf.cell(0, 10, str(name), 1, 1, 'L')
    
    @staticmethod
    def _add_report_footer(pdf):
        """Add report footer"""
        pdf.ln(10)
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(0, 10, f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1, 'C')
    
    @staticmethod
    def _format_amount(amount):
        """Format amount with commas for thousands"""
        try:
            return f"{float(amount):,.2f}"
        except (ValueError, TypeError):
            return str(amount)