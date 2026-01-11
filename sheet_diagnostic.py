# sheet_diagnostic.py
import pandas as pd
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.google_sheets_service import google_sheets_service
from flask import Flask

def diagnose_all_sheets():
    app = Flask(__name__)
    app.config['GOOGLE_CREDENTIALS_PATH'] = 'credentials/mzugoss-welfare-5dab294def1f.json'
    
    sheet_url = "https://docs.google.com/spreadsheets/d/1N0QM7n-TbmLPhPSBFmE2rJB4GTKfyyQi88yXIYjgNyc/edit?usp=drive_link"
    
    with app.app_context():
        google_sheets_service.init_app(app)
        
        print("🔍 DIAGNOSING ALL SHEETS")
        print("="*80)
        
        # Test connection first
        result = google_sheets_service.test_connection(sheet_url)
        print(f"Connection: {'✅' if result['success'] else '❌'}")
        
        if result['success']:
            worksheets = result['worksheet_names']
            print(f"\nWorksheets: {worksheets}")
            
            for sheet_name in worksheets:
                print(f"\n{'='*40}")
                print(f"SHEET: {sheet_name}")
                print(f"{'='*40}")
                
                df = google_sheets_service.get_sheet_data(sheet_url, sheet_name)
                
                if df is not None:
                    print(f"Shape: {df.shape}")
                    print(f"Columns: {list(df.columns)}")
                    
                    # Check for issues
                    empty_cols = [col for col in df.columns if str(col).strip() == '']
                    if empty_cols:
                        print(f"⚠️  Empty column names: {len(empty_cols)}")
                    
                    # Show first 3 rows
                    print("\nFirst 3 rows:")
                    print(df.head(3).to_string())
                else:
                    print("❌ Failed to fetch data")

if __name__ == "__main__":
    diagnose_all_sheets()