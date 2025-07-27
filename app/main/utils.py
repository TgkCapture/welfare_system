import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime
from flask import current_app, request
import calendar
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

class PDF(FPDF):
    def header(self):
        
        # Title
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'MZUGOSS CLASS OF 2018 MONTHLY CONTRIBUTIONS REPORT', 0, 1, 'C')
        # Line break
        self.ln(10)
    
    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        # Page number
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

def find_month_row(df, month_name):
    """Scan through the dataframe to find the row containing month names"""
    for i, row in df.iterrows():
        for cell in row:
            if pd.notna(cell) and month_name.lower() in str(cell).lower():
                return i
    return None

def parse_excel(filepath, year=None, month=None):
    """Parse the Excel file and return data for specified month/year"""
    # Use current month/year if not specified
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month
    
    month_name = calendar.month_name[month]
    
    # Read all sheets
    all_sheets = pd.read_excel(filepath, sheet_name=None, header=None)
    
    # Find the sheet for specified year
    year_sheet = None
    for sheet_name in all_sheets:
        if str(year) in sheet_name:
            year_sheet = sheet_name
            break
    
    if not year_sheet:
        raise ValueError(f"No sheet found for year {year}")
    
    # Get the raw sheet data
    raw_df = all_sheets[year_sheet]
    
    # Find the row containing month names
    month_row = find_month_row(raw_df, month_name)
    if month_row is None:
        raise ValueError(f"No row found containing month {month_name}")
    
    # Re-read the sheet with proper headers
    df = pd.read_excel(filepath, sheet_name=year_sheet, header=month_row)
    
    # Find the column for specified month
    month_col = None
    for col in df.columns:
        if pd.notna(col) and month_name.lower() in str(col).lower():
            month_col = col
            break
    
    if not month_col:
        raise ValueError(f"No column found for month {month_name}")
    
    # Find the name column 
    name_col = None
    for col in df.columns:
        if any(isinstance(val, str) and "name" in val.lower() for val in df[col].dropna()):
            name_col = col
            break
    if not name_col:
        name_col = df.columns[0]  # Fallback to first column
    
    # Clean and process the data
    df = df[[name_col, month_col]].dropna(subset=[name_col])
    df = df[df[name_col].astype(str).str.strip() != '']
    df = df[~df[name_col].str.lower().str.contains('total')]  # Exclude totals row
    
    # Convert amounts to numeric
    df[month_col] = pd.to_numeric(df[month_col], errors='coerce')
    
    # Calculate summary stats
    total_contributions = float(df[month_col].sum()) if not df[month_col].empty else 0.0
    num_contributors = int(df[month_col].count()) if not df[month_col].empty else 0
    num_missing = int(len(df) - num_contributors)
    
    return {
        'data': df,
        'month': month_name,
        'year': year,
        'total_contributions': total_contributions,
        'num_contributors': num_contributors,
        'num_missing': num_missing,
        'defaulters': df[df[month_col].isna()][name_col].tolist(),
        'name_col': name_col,
        'month_col': month_col
    }

def generate_report(data, original_name):
    """Generate a PDF report from the parsed data"""
    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Set colors and fonts
    pdf.set_fill_color(240, 240, 240)  # Light gray for header rows
    pdf.set_text_color(0, 0, 0)  # Black text
    pdf.set_font("Arial", size=12)
    
    # Report Header
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Report for {data['month']} {data['year']}", 0, 1, 'L')
    pdf.ln(5)
    
    # Summary section with better styling
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "SUMMARY STATISTICS", 0, 1, 'L')
    pdf.set_font("Arial", size=12)
    
    # Summary table
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(60, 10, "Total Contributions:", 1, 0, 'L', 1)
    pdf.cell(0, 10, f"MWK {data['total_contributions']:,.2f}", 1, 1, 'L')
    pdf.cell(60, 10, "Number of Contributors:", 1, 0, 'L', 1)
    pdf.cell(0, 10, str(data['num_contributors']), 1, 1, 'L')
    pdf.cell(60, 10, "Number of Defaulters:", 1, 0, 'L', 1)
    pdf.cell(0, 10, str(data['num_missing']), 1, 1, 'L')
    pdf.ln(10)
    
    # Paid Members Section
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "PAID MEMBERS", 0, 1, 'L')
    pdf.set_font("Arial", size=12)
    
    # Create paid members table
    paid_df = data['data'][~data['data'][data['month_col']].isna()]
    if not paid_df.empty:
        # Table header
        pdf.set_fill_color(200, 220, 255)  # Light blue for header
        pdf.cell(120, 10, "Name", 1, 0, 'C', 1)
        pdf.cell(0, 10, "Amount (MWK)", 1, 1, 'C', 1)
        pdf.set_fill_color(255, 255, 255)  # White for data rows
        
        # Table rows
        for _, row in paid_df.iterrows():
            pdf.cell(120, 10, str(row[data['name_col']]), 1, 0, 'L')
            pdf.cell(0, 10, f"{row[data['month_col']]:,.2f}", 1, 1, 'R')
    else:
        pdf.cell(0, 10, "No paid members for this period", 0, 1)
    pdf.ln(10)
    
    # Defaulters Section
    if data['num_missing'] > 0:
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, "DEFAULTERS", 0, 1, 'L')
        pdf.set_font("Arial", size=12)
        
        # Table header
        pdf.set_fill_color(255, 200, 200)  # Light red for header
        pdf.cell(0, 10, "Name", 1, 1, 'C', 1)
        pdf.set_fill_color(255, 255, 255)  # White for data rows
        
        # Table rows
        for name in data['defaulters']:
            pdf.cell(0, 10, str(name), 1, 1, 'L')
    
    # Footer
    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 10, f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 0, 1, 'C')
    
    # Save the file
    filename = f"contributions_report_{data['year']}_{data['month']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    report_path = os.path.join(current_app.config['REPORT_FOLDER'], filename)
    pdf.output(report_path)
    
    return report_path

def generate_paid_members_image(data):
    """Generate PNG image of paid members only"""
    # Filter paid members
    paid_df = data['data'][~data['data'][data['month_col']].isna()]
    
    if paid_df.empty:
        return None
    
    # Create figure
    plt.figure(figsize=(10, paid_df.shape[0] * 0.3 + 2))
    plt.axis('off')
    
    # Create table
    table_data = [[name, f"MWK {amount:,.2f}"] 
                 for name, amount in zip(paid_df[data['name_col']], paid_df[data['month_col']])]
    
    table = plt.table(cellText=table_data,
                     colLabels=['Name', 'Amount'],
                     loc='center',
                     cellLoc='left',
                     colColours=['#f0f0f0', '#f0f0f0'])
    
    # Style table
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1, 1.5)
    
    # Save to bytes buffer
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    plt.close()
    buf.seek(0)
    
    return buf