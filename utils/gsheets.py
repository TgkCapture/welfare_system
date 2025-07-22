import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import current_app

def init_gsheets(app):
    scope = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        app.config['GSHEETS_CREDENTIALS'], scope)
    
    app.gc = gspread.authorize(creds)

def get_sheet_data(sheet_id, worksheet_name=None):
    try:
        sh = current_app.gc.open_by_key(sheet_id)
        worksheet = sh.worksheet(worksheet_name) if worksheet_name else sh.sheet1
        return worksheet.get_all_records()
    except Exception as e:
        current_app.logger.error(f"Google Sheets error: {e}")
        return None