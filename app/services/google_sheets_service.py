# app/services/google_sheets_service.py
import os
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError
from google.api_core.exceptions import PermissionDenied, NotFound
from flask import current_app
import logging
from io import BytesIO
from typing import Optional, Dict, Any
from urllib.parse import urlparse
import re
import time
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.cache = {}
            self.cache_timeout = 300  # 5 minutes cache
            self._last_update_times = {}
            self._sheet_hashes = {}
            self._initialized = True
    
    def init_app(self, app):
        """Initialize service with Flask app context"""
        self.credentials_path = app.config.get('GOOGLE_CREDENTIALS_PATH')
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
    
    def _validate_sheet_url(self, sheet_url: str) -> bool:
        """Validate Google Sheets URL format"""
        pattern = r'^https://docs\.google\.com/spreadsheets/d/[a-zA-Z0-9-_]+(/.*)?$'
        return bool(re.match(pattern, sheet_url))
    
    def _extract_sheet_id(self, sheet_url: str) -> Optional[str]:
        """Extract sheet ID from URL"""
        try:
            if '/d/' in sheet_url:
                parts = sheet_url.split('/d/')[1].split('/')
                return parts[0]
            elif 'key=' in sheet_url:
                parsed = urlparse(sheet_url)
                params = dict(pair.split('=') for pair in parsed.query.split('&'))
                return params.get('key')
        except:
            return None
        return None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((gspread.exceptions.APIError,))
    )
    def get_client(self):
        """Authenticate and return a Google Sheets client with retry logic"""
        try:
            creds = None
            
            creds_info = current_app.config.get('GOOGLE_CREDENTIALS_JSON')
            if creds_info:
                import json
                try:
                    creds_dict = json.loads(creds_info)
                    creds = Credentials.from_service_account_info(
                        creds_dict, 
                        scopes=self.scopes
                    )
                    logger.info("Using credentials from environment variable")
                except json.JSONDecodeError:
                    logger.error("Invalid JSON in GOOGLE_CREDENTIALS_JSON")
            
            # Fallback to file
            if not creds and self.credentials_path and os.path.exists(self.credentials_path):
                creds = Credentials.from_service_account_file(
                    self.credentials_path, 
                    scopes=self.scopes
                )
                logger.info(f"Using credentials from file: {self.credentials_path}")
            
            if not creds:
                logger.error("Google Sheets credentials not configured")
                return None
            
            client = gspread.authorize(creds)
            return client
            
        except GoogleAuthError as e:
            logger.error(f"Google authentication error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting Google Sheets client: {str(e)}")
            return None
    
    def get_sheet_data(self, sheet_url: str, sheet_name: Optional[str] = None, 
                      force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """Get data from Google Sheets with caching"""
        
        # Validate URL
        if not self._validate_sheet_url(sheet_url):
            logger.error(f"Invalid Google Sheets URL: {sheet_url}")
            return None
        
        # Check cache if not forcing refresh
        cache_key = f"{sheet_url}:{sheet_name}"
        if not force_refresh and cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_timeout:
                logger.debug(f"Returning cached data for {cache_key}")
                return cached_data
        
        client = self.get_client()
        if not client:
            return None
        
        try:
            # Open the spreadsheet
            spreadsheet = client.open_by_url(sheet_url)
            
            # Get available worksheets
            worksheets = spreadsheet.worksheets()
            logger.info(f"Available worksheets: {[ws.title for ws in worksheets]}")
            
            # Get the worksheet
            worksheet = None
            if sheet_name:
                try:
                    worksheet = spreadsheet.worksheet(sheet_name)
                except gspread.exceptions.WorksheetNotFound:
                    logger.warning(f"Worksheet '{sheet_name}' not found, trying case-insensitive match")
                    # Try case-insensitive match
                    for ws in worksheets:
                        if sheet_name.lower() in ws.title.lower():
                            worksheet = ws
                            logger.info(f"Using worksheet with similar name: {ws.title}")
                            break
            
            # If still no worksheet, use first sheet or sheet1
            if not worksheet:
                try:
                    worksheet = spreadsheet.sheet1
                    logger.info(f"Using default worksheet: {worksheet.title}")
                except:
                    if worksheets:
                        worksheet = worksheets[0]
                        logger.info(f"Using first worksheet: {worksheet.title}")
                    else:
                        logger.error("No worksheets found in spreadsheet")
                        return None
            
            # Get all values
            data = worksheet.get_all_values()
            
            # Convert to DataFrame
            if data and len(data) > 1:  # Has header and at least one row
                # Use first row as headers
                headers = data[0]
                # Clean header names
                headers = [str(h).strip() for h in headers]
                df = pd.DataFrame(data[1:], columns=headers)
                
                # Clean data
                df = self._clean_dataframe(df)
                
                # Update cache
                self.cache[cache_key] = (df, time.time())
                self._last_update_times[cache_key] = time.time()
                
                logger.info(f"Successfully fetched {len(df)} rows from Google Sheet")
                return df
            else:
                logger.warning("No data found in Google Sheet")
                return pd.DataFrame()
                
        except PermissionDenied as e:
            logger.error(f"Permission denied accessing Google Sheet: {sheet_url}")
            logger.error(f"Permission error details: {str(e)}")
            return None
        except NotFound as e:
            logger.error(f"Google Sheet not found: {sheet_url}")
            return None
        except gspread.exceptions.APIError as e:
            logger.error(f"Google Sheets API error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error accessing Google Sheet: {str(e)}", exc_info=True)
            return None
    
    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and validate the DataFrame"""
        if df.empty:
            return df
        
        # Remove completely empty rows/columns
        df = df.dropna(how='all')
        if df.empty:
            return df
        
        # Remove unnamed columns
        df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
        
        # Convert numeric columns
        for col in df.columns:
            try:
                # Skip if column is all NaN
                if df[col].isna().all():
                    continue
                    
                # Try to convert to numeric
                df[col] = pd.to_numeric(df[col], errors='coerce')
            except Exception as e:
                logger.debug(f"Could not convert column '{col}' to numeric: {str(e)}")
                continue
        
        # Reset index
        df = df.reset_index(drop=True)
        
        return df
    
    def get_latest_sheet_data(self, sheet_url: str, 
                             year: Optional[int] = None) -> Optional[pd.DataFrame]:
        """Get the latest relevant sheet data based on naming patterns"""
        client = self.get_client()
        if not client:
            return None
        
        try:
            spreadsheet = client.open_by_url(sheet_url)
            worksheets = spreadsheet.worksheets()
            
            # Sort worksheets by title to find latest (reverse alphabetical)
            sorted_worksheets = sorted(worksheets, key=lambda x: x.title, reverse=True)
            
            # Try to find by year
            if year:
                year_patterns = [str(year), f"_{year}", f"{year}_", f"{year}-", f"{year} "]
                for pattern in year_patterns:
                    for ws in sorted_worksheets:
                        if pattern in ws.title:
                            logger.info(f"Found worksheet by year pattern '{pattern}': {ws.title}")
                            return self.get_sheet_data(sheet_url, ws.title)
            
            # Try common sheet names
            common_names = ["Data", "Sheet1", "Contributions", "Members", "2024", "2023"]
            for name in common_names:
                for ws in sorted_worksheets:
                    if name.lower() in ws.title.lower():
                        logger.info(f"Found worksheet by common name '{name}': {ws.title}")
                        return self.get_sheet_data(sheet_url, ws.title)
            
            # Fallback to most recent worksheet
            if sorted_worksheets:
                latest = sorted_worksheets[0]
                logger.info(f"Using latest worksheet: {latest.title}")
                return self.get_sheet_data(sheet_url, latest.title)
            
            logger.error("No worksheets found in spreadsheet")
            return None
            
        except Exception as e:
            logger.error(f"Error finding latest sheet: {str(e)}")
            return None
    
    def get_sheet_as_excel(self, sheet_url: str, sheet_name: Optional[str] = None) -> Optional[BytesIO]:
        """Get Google Sheets data as Excel file bytes"""
        try:
            # Get data from Google Sheets
            df = self.get_sheet_data(sheet_url, sheet_name)
            
            if df is None:
                logger.error("Failed to get data from Google Sheet")
                return None
            
            if df.empty:
                logger.warning("Google Sheet is empty")
                # Return empty Excel file
                df = pd.DataFrame({'Message': ['No data found in Google Sheet']})
            
            # Convert DataFrame to Excel bytes
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Write main data
                sheet_title = sheet_name or 'Sheet1'
                df.to_excel(writer, index=False, sheet_name=sheet_title[:31])  # Excel sheet name max 31 chars
                
                # Get workbook and worksheet objects for formatting
                workbook = writer.book
                worksheet = writer.sheets[sheet_title[:31]]
                
                # Add header formatting
                header_format = workbook.add_format({
                    'bold': True,
                    'text_wrap': True,
                    'valign': 'top',
                    'fg_color': '#D7E4BC',
                    'border': 1
                })
                
                # Apply header formatting
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)
                
                # Auto-adjust column widths
                for i, col in enumerate(df.columns):
                    # Calculate max width
                    max_len = max(
                        df[col].astype(str).apply(len).max() if not df[col].empty else 0,
                        len(str(col))
                    )
                    # Set column width (max 50 characters)
                    worksheet.set_column(i, i, min(max_len + 2, 50))
                
                # Add metadata sheet
                metadata_df = pd.DataFrame({
                    'Property': ['Source URL', 'Export Time', 'Total Rows', 'Total Columns', 'Sheet Name', 'Generated By'],
                    'Value': [
                        sheet_url,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        len(df),
                        len(df.columns),
                        sheet_name or 'Default',
                        'Welfare Management System'
                    ]
                })
                metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
            
            output.seek(0)
            
            logger.info(f"Successfully converted Google Sheet to Excel format: {len(df)} rows")
            return output
            
        except Exception as e:
            logger.error(f"Error converting Google Sheet to Excel: {str(e)}", exc_info=True)
            return None
    
    def check_sheet_updated(self, sheet_url: str, sheet_name: str) -> bool:
        """Check if sheet has been updated since last fetch"""
        cache_key = f"{sheet_url}:{sheet_name}"
        if cache_key not in self._last_update_times:
            return True
        
        client = self.get_client()
        if not client:
            return False
        
        try:
            spreadsheet = client.open_by_url(sheet_url)
            worksheet = spreadsheet.worksheet(sheet_name)
            
            # Get a sample of data (first 10 rows) to check for changes
            data = worksheet.get_all_records(head=1)
            if not data:
                return True
            
            # Create hash of the data
            import json
            data_str = json.dumps(data, sort_keys=True)
            current_hash = hash(data_str)
            
            # Initialize _sheet_hashes if needed
            if not hasattr(self, '_sheet_hashes'):
                self._sheet_hashes = {}
            
            # Store and compare hash
            last_hash = self._sheet_hashes.get(cache_key)
            self._sheet_hashes[cache_key] = current_hash
            return last_hash != current_hash
                
        except Exception as e:
            logger.error(f"Error checking sheet update: {str(e)}")
            return True  # Assume updated on error
    
    def clear_cache(self, sheet_url: str = None, sheet_name: str = None):
        """Clear cache for specific sheet or all sheets"""
        if sheet_url and sheet_name:
            cache_key = f"{sheet_url}:{sheet_name}"
            if cache_key in self.cache:
                del self.cache[cache_key]
            if cache_key in self._last_update_times:
                del self._last_update_times[cache_key]
            if hasattr(self, '_sheet_hashes') and cache_key in self._sheet_hashes:
                del self._sheet_hashes[cache_key]
            logger.info(f"Cleared cache for {cache_key}")
        elif sheet_url:
            # Clear all caches for this URL
            keys_to_delete = [k for k in self.cache.keys() if k.startswith(sheet_url)]
            for key in keys_to_delete:
                del self.cache[key]
                if key in self._last_update_times:
                    del self._last_update_times[key]
                if hasattr(self, '_sheet_hashes') and key in self._sheet_hashes:
                    del self._sheet_hashes[key]
            logger.info(f"Cleared cache for all sheets in {sheet_url}")
        else:
            # Clear all caches
            self.cache.clear()
            self._last_update_times.clear()
            if hasattr(self, '_sheet_hashes'):
                self._sheet_hashes.clear()
            logger.info("Cleared all Google Sheets cache")
    
    def test_connection(self, sheet_url: str = None) -> Dict[str, Any]:
        """Test connection to Google Sheets API"""
        try:
            client = self.get_client()
            if not client:
                return {
                    'success': False,
                    'error': 'Failed to authenticate with Google Sheets API'
                }
            
            # If a URL is provided, try to access it
            if sheet_url:
                if not self._validate_sheet_url(sheet_url):
                    return {
                        'success': False,
                        'error': 'Invalid Google Sheets URL format'
                    }
                
                try:
                    spreadsheet = client.open_by_url(sheet_url)
                    worksheets = spreadsheet.worksheets()
                    
                    return {
                        'success': True,
                        'sheet_title': spreadsheet.title,
                        'worksheet_count': len(worksheets),
                        'worksheet_names': [ws.title for ws in worksheets],
                        'message': f'Successfully connected to "{spreadsheet.title}"'
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Failed to access sheet: {str(e)}'
                    }
            else:
                # Just test authentication
                return {
                    'success': True,
                    'message': 'Successfully authenticated with Google Sheets API'
                }
                
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

# Singleton instance
google_sheets_service = GoogleSheetsService()