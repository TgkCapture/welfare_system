from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
import os

def generate_pdf_report(data, title, output_path=None):
    buffer = BytesIO() if not output_path else output_path
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Add title
    story.append(Paragraph(title, styles['Title']))
    story.append(Spacer(1, 12))
    
    # Add data table
    table_data = [['Name', 'Amount']] + data
    table = Table(table_data)
    story.append(table)
    
    doc.build(story)
    return buffer