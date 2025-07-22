# === app/main/utils.py ===
import pandas as pd
import os
from fpdf import FPDF
from datetime import datetime

def parse_excel(filepath):
    df = pd.read_excel(filepath)
    return df  # TODO: Add real parsing logic

def generate_report(df, original_name):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Monthly Contributions Report", ln=True, align='C')
    for i, row in df.iterrows():
        line = f"{row[0]} - {row[1]}"
        pdf.cell(200, 10, txt=line, ln=True)
    filename = f"report_{original_name.replace('.xlsx', '')}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    report_path = os.path.join('reports', filename)
    pdf.output(report_path)
    return report_path