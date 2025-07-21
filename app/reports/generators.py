# app/reports/generators.py
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import matplotlib.pyplot as plt
from io import BytesIO
import os
from datetime import datetime
from config import Config

def generate_monthly_report(year, month):
    # Load data from Excel/Google Sheets
    df = load_contribution_data(year)
    
    # Filter for the specific month
    month_col = month.capitalize()
    monthly_data = df[['Name', month_col]].dropna()
    
    # Calculate totals
    total_contributions = monthly_data[month_col].sum()
    total_members = len(monthly_data)
    
    # Create PDF
    filename = f"monthly_report_{month}_{year}.pdf"
    filepath = os.path.join(Config.REPORT_FOLDER, filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title = Paragraph(f"Mzugoss Welfare {month} {year} Contribution Report", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Summary
    summary = Paragraph(f"""
        Total Contributors: {total_members}<br/>
        Total Contributions: {total_contributions:.2f}
    """, styles['Normal'])
    story.append(summary)
    story.append(Spacer(1, 12))
    
    # Contributors table
    data = [['Name', 'Amount']] + monthly_data.values.tolist()
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    
    doc.build(story)
    
    # Generate PNG version
    generate_monthly_png(monthly_data, year, month)
    
    return filepath

def generate_yearly_report(year):
    # Similar structure but for yearly data
    pass

def generate_monthly_png(data, year, month):
    # Create a simple bar chart
    plt.figure(figsize=(10, len(data)*0.5))
    plt.barh(data['Name'], data[month.capitalize()])
    plt.title(f"Mzugoss Welfare {month} {year} Contributions")
    plt.xlabel('Amount')
    plt.tight_layout()
    
    filename = f"monthly_report_{month}_{year}.png"
    filepath = os.path.join(Config.REPORT_FOLDER, filename)
    plt.savefig(filepath)
    plt.close()

def load_contribution_data(year):
    # This would be customized to load from your specific Excel structure
    # For now, we'll use a dummy function
    filepath = f"data/contributions_{year}.xlsx"
    return pd.read_excel(filepath)