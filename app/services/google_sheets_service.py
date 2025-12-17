# app/services/google_sheets_service.py
import os
import gspread
from google.oauth2.service_account import Credentials
from flask import current_app
import pandas as pd
from io import BytesIO
import logging

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def init_app(self, app):
        """Initialize service with Flask app context"""
        self.credentials_path = app.config.get('GOOGLE_CREDENTIALS_PATH')
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    
    def get_client(self):
        """Authenticate and return a Google Sheets client"""
        try:
            if self.credentials_path and os.path.exists(self.credentials_path):
                current_app.logger.info(f"Using credentials from file: {self.credentials_path}")
                creds = Credentials.from_service_account_file(
                    self.credentials_path, scopes=self.scopes
                )
            else:
                # Try to use environment variable
                creds_info = current_app.config.get('GOOGLE_CREDENTIALS_JSON')
                if creds_info:
                    current_app.logger.info("Using credentials from environment variable")
                    import json
                    creds_dict = json.loads(creds_info)
                    creds = Credentials.from_service_account_info(creds_dict, scopes=self.scopes)
                else:
                    current_app.logger.error("Google Sheets credentials not configured")
                    return None
            
            client = gspread.authorize(creds)
            return client
        except Exception as e:
            current_app.logger.error(f"Google Sheets authentication failed: {str(e)}")
            return None
    
    def get_sheet_data(self, sheet_url, sheet_name=None):
        """Get data from Google Sheets as a pandas DataFrame"""
        client = self.get_client()
        if not client:
            current_app.logger.error("No Google Sheets client available")
            return None
        
        try:
            # Open the spreadsheet
            spreadsheet = client.open_by_url(sheet_url)
            
            # Get the worksheet
            if sheet_name:
                worksheet = spreadsheet.worksheet(sheet_name)
            else:
                worksheet = spreadsheet.sheet1
            
            # Get all values
            data = worksheet.get_all_values()
            
            # Convert to DataFrame
            if data:
                df = pd.DataFrame(data[1:], columns=data[0])
                return df
            else:
                current_app.logger.warning("No data found in Google Sheet")
                return None
                
        except Exception as e:
            current_app.logger.error(f"Error accessing Google Sheet: {str(e)}")
            return None
    
    def get_sheet_as_excel(self, sheet_url, sheet_name=None):
        """Get Google Sheets data as Excel file bytes"""
        df = self.get_sheet_data(sheet_url, sheet_name)
        if df is None:
            current_app.logger.error("Failed to get data from Google Sheet")
            return None
        
        try:
            # Convert DataFrame to Excel bytes
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            output.seek(0)
            
            current_app.logger.info("Successfully converted Google Sheet to Excel format")
            return output
            
        except Exception as e:
            current_app.logger.error(f"Error converting Google Sheet to Excel: {str(e)}")
            return None

# Singleton instance
google_sheets_service = GoogleSheetsService()