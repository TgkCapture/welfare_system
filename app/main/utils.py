import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime
from flask import current_app
import calendar
import numpy as np

def find_month_row(df, month_name):
    """Scan through the dataframe to find the row containing month names"""
    for i, row in df.iterrows():
        for cell in row:
            if pd.notna(cell) and month_name.lower() in str(cell).lower():
                return i
    return None

def parse_excel(filepath):
    """Parse the Excel file and return data for current month"""
    current_year = datetime.now().year
    current_month = datetime.now().month
    month_name = calendar.month_name[current_month]
    
    # Read all sheets
    all_sheets = pd.read_excel(filepath, sheet_name=None, header=None)
    
    # Find the sheet for current year
    year_sheet = None
    for sheet_name in all_sheets:
        if str(current_year) in sheet_name:
            year_sheet = sheet_name
            break
    
    if not year_sheet:
        raise ValueError(f"No sheet found for current year {current_year}")
    
    # Get the raw sheet data 
    raw_df = all_sheets[year_sheet]
    
    # Find the row containing month names
    month_row = find_month_row(raw_df, month_name)
    if month_row is None:
        raise ValueError(f"No row found containing month {month_name}")
    
    # Re-read the sheet with proper headers
    df = pd.read_excel(filepath, sheet_name=year_sheet, header=month_row)
    
    # Find the column for current month
    month_col = None
    for col in df.columns:
        if pd.notna(col) and month_name.lower() in str(col).lower():
            month_col = col
            break
    
    if not month_col:
        raise ValueError(f"No column found for current month {month_name}")
    
    # Find the name column 
    name_col = None
    for col in df.columns:
        if any(isinstance(val, str) and "name" in val.lower() for val in df[col].dropna()):
            name_col = col
            break
    if not name_col:
        name_col = df.columns[0]  # Fallback to first column
    
    # Clean and process the data - exclude rows with "Total" in name column
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
        'year': current_year,
        'total_contributions': total_contributions,
        'num_contributors': num_contributors,
        'num_missing': num_missing,
        'defaulters': df[df[month_col].isna()][name_col].tolist(),
        'name_col': name_col,
        'month_col': month_col
    }

def generate_report(data, original_name):
    """Generate a PDF report from the parsed data"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Header
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="MZUGOSS CLASS OF 2018 MONTHLY CONTRIBUTIONS REPORT", ln=True, align='C')
    pdf.ln(5)
    
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Month: {data['month']} {data['year']}", ln=True, align='L')
    pdf.ln(5)
    
    # Summary section
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="SUMMARY STATISTICS", ln=True)
    pdf.set_font("Arial", size=12)
    
    pdf.cell(200, 10, txt=f"Total Contributions: {data['total_contributions']:.2f}", ln=True)
    pdf.cell(200, 10, txt=f"Number of Contributors: {data['num_contributors']}", ln=True)
    pdf.cell(200, 10, txt=f"Number of Defaulters: {data['num_missing']}", ln=True)
    pdf.ln(10)
    
    # Contributions list
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="CONTRIBUTIONS LIST", ln=True)
    pdf.set_font("Arial", size=12)
    
    for _, row in data['data'].iterrows():
        name = row[data['name_col']]
        amount = row[data['month_col']] if not pd.isna(row[data['month_col']]) else "Not Paid"
        line = f"{name}: {amount}"
        pdf.cell(200, 10, txt=line, ln=True)
    
    # Defaulters list
    if data['num_missing'] > 0:
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="MEMBERS WHO HAVEN'T PAID", ln=True)
        pdf.set_font("Arial", size=12)
        
        for name in data['defaulters']:
            pdf.cell(200, 10, txt=name, ln=True)
    
    # Footer
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    
    # Save the file
    filename = f"contributions_report_{data['month']}_{data['year']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    report_path = os.path.join(current_app.config['REPORT_FOLDER'], filename)
    pdf.output(report_path)
    
    return report_path