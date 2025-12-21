# app/utils/helpers.py
from datetime import datetime, timedelta
import os
import hashlib
import pandas as pd

from flask import current_app, logging
from werkzeug.utils import secure_filename

from app.models.setting import Setting
from app.services.google_sheets_service import google_sheets_service

class FileProcessor:
    @staticmethod
    def process_upload(request, use_cache=True):
        """Process file upload from request with enhanced Google Sheets support"""
        use_google_sheets = request.form.get('use_google_sheets') == 'on'
        
        if use_google_sheets:
            return FileProcessor._process_google_sheets(request, use_cache)
        else:
            return FileProcessor._process_file_upload(request)
    
    @staticmethod
    def _process_google_sheets(request, use_cache=True):
        """Process Google Sheets upload with enhanced features"""
        sheet_url = request.form.get('sheet_url', '')
        year = request.form.get('year', type=int)
        month = request.form.get('month', '')
        sheet_name = request.form.get('sheet_name', '')
        force_refresh = request.form.get('force_refresh', 'off') == 'on'
        
        if not sheet_url:
            raise ValueError("Google Sheets URL is required")
        
        # Validate URL
        if not google_sheets_service._validate_sheet_url(sheet_url):
            raise ValueError("Invalid Google Sheets URL format")
        
        # Save Google Sheets URL for future use
        Setting.set_value('google_sheets_url', sheet_url)
        
        # Determine which sheet to use
        target_sheet_name = None
        if sheet_name:
            target_sheet_name = sheet_name
        elif year and month:
            # Try to find sheet with year/month pattern
            target_sheet_name = f"{year}_{month}"
        elif year:
            target_sheet_name = str(year)
        
        # Check if we should get latest data
        if not target_sheet_name or force_refresh:
            logger.info(f"Getting latest sheet data for {sheet_url}")
            df = google_sheets_service.get_latest_sheet_data(sheet_url, year)
        else:
            # Get specific sheet
            df = google_sheets_service.get_sheet_data(
                sheet_url, 
                target_sheet_name,
                force_refresh=force_refresh
            )
        
        if df is None or df.empty:
            # Try alternative approach
            logger.warning(f"No data found with sheet name '{target_sheet_name}', trying all sheets")
            df = FileProcessor._try_all_sheets(sheet_url, year, month)
        
        if df is None or df.empty:
            raise ValueError("No valid data found in Google Sheets")
        
        # Generate unique filename with hash
        data_hash = hashlib.md5(pd.util.hash_pandas_object(df).values.tobytes()).hexdigest()[:8]
        filename = f"google_sheet_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{data_hash}.xlsx"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # Save as Excel
        FileProcessor._save_dataframe_to_excel(df, filepath)
        
        # Log metadata
        logger.info(f"Saved Google Sheets data: {len(df)} rows, {len(df.columns)} columns")
        
        return filepath
    
    @staticmethod
    def _try_all_sheets(sheet_url, year=None, month=None):
        """Try to find the right sheet by checking all available sheets"""
        client = google_sheets_service.get_client()
        if not client:
            return None
        
        try:
            spreadsheet = client.open_by_url(sheet_url)
            worksheets = spreadsheet.worksheets()
            
            # Try different matching strategies
            patterns_to_try = []
            if year and month:
                patterns_to_try.extend([
                    f"{year}_{month:02d}",
                    f"{month}_{year}",
                    f"{year}-{month:02d}",
                    f"{month} {year}"
                ])
            if year:
                patterns_to_try.append(str(year))
            
            # Also try common sheet names
            common_names = ["Data", "Contributions", "Members", "Sheet1", "Sheet2", "Sheet3"]
            patterns_to_try.extend(common_names)
            
            for pattern in patterns_to_try:
                for ws in worksheets:
                    if pattern.lower() in ws.title.lower():
                        logger.info(f"Found matching sheet: {ws.title} for pattern: {pattern}")
                        return google_sheets_service.get_sheet_data(sheet_url, ws.title)
            
            for ws in worksheets:
                try:
                    data = ws.get_all_values()
                    if len(data) > 1: 
                        logger.info(f"Using first sheet with data: {ws.title}")
                        return google_sheets_service.get_sheet_data(sheet_url, ws.title)
                except:
                    continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error trying all sheets: {str(e)}")
            return None
    
    @staticmethod
    def _save_dataframe_to_excel(df, filepath):
        """Save DataFrame to Excel with proper formatting"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save to Excel with multiple sheets if needed
            with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
                # Main data
                df.to_excel(writer, sheet_name='Data', index=False)
                
                # Add metadata sheet
                metadata_df = pd.DataFrame({
                    'Property': ['Export Time', 'Rows', 'Columns', 'Source'],
                    'Value': [
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        len(df),
                        len(df.columns),
                        'Google Sheets'
                    ]
                })
                metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
                
                # Auto-adjust column widths
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    for idx, col in enumerate(writer.sheets[sheet_name]._worksheet.columns):
                        max_length = 0
                        column = col[0].column_letter  # Get the column name
                        for cell in col:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)  # Max width 50
                        worksheet.set_column(f'{column}:{column}', adjusted_width)
            
            return True
        except Exception as e:
            logger.error(f"Error saving DataFrame to Excel: {str(e)}")
            raise
    
    @staticmethod
    def _process_file_upload(request):
        """Process file upload from form with validation"""
        if 'file' not in request.files:
            raise ValueError("No file selected")
        
        file = request.files['file']
        if file.filename == '':
            raise ValueError("No file selected")
        
        # Validate file extension
        filename = secure_filename(file.filename)
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'xlsx', 'xls', 'csv'})
        
        if '.' not in filename:
            raise ValueError("Invalid file: no extension")
        
        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext not in allowed_extensions:
            raise ValueError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")
        
        # Validate file size
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset pointer
        
        if file_size > max_size:
            raise ValueError(f"File too large. Maximum size: {max_size / (1024*1024):.1f}MB")
        
        # Generate unique filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{timestamp}_{filename}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Ensure upload directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save file
        file.save(filepath)
        
        logger.info(f"File uploaded: {filename} ({file_size} bytes)")
        
        return filepath
    
    @staticmethod
    def cleanup_file(filepath):
        """Clean up temporary file if needed"""
        if not filepath or not os.path.exists(filepath):
            return
        
        try:
            # Only delete temporary Google Sheets files or old files
            filename = os.path.basename(filepath)
            
            # Delete if it's a temporary Google Sheets file
            if 'google_sheet_' in filename and filepath.endswith('.xlsx'):
                os.remove(filepath)
                logger.info(f"Cleaned up temporary file: {filename}")
            
            cleanup_days = current_app.config.get('AUTO_CLEANUP_DAYS', 3)
            if current_app.config.get('ENABLE_AUTO_CLEANUP', False):
                FileProcessor._cleanup_old_files(filepath, cleanup_days)
                
        except Exception as e:
            logger.warning(f"Could not cleanup file {filepath}: {str(e)}")
    
    @staticmethod
    def _cleanup_old_files(filepath, days_old):
        """Clean up files older than specified days"""
        try:
            upload_dir = os.path.dirname(filepath)
            cutoff_time = datetime.now() - timedelta(days=days_old)
            
            for filename in os.listdir(upload_dir):
                file_path = os.path.join(upload_dir, filename)
                if os.path.isfile(file_path):
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_mtime < cutoff_time:
                        os.remove(file_path)
                        logger.debug(f"Cleaned up old file: {filename}")
        except Exception as e:
            logger.warning(f"Error cleaning up old files: {str(e)}")


class ReportDataSerializer:
    @staticmethod
    def serialize(data, report_path, include_raw_data=False):
        """Serialize report data for session storage with enhanced metadata"""
        
        # Extract DataFrame
        df = data.get('data')
        
        # Ensure data is serializable
        serialized_data = []
        if df is not None and not df.empty:
            # Convert NaN to None for JSON serialization
            df_clean = df.where(pd.notnull(df), None)
            serialized_data = df_clean.to_dict('records')
        
        # Calculate additional statistics
        total_contributions = float(data.get('total_contributions', 0))
        num_contributors = int(data.get('num_contributors', 0))
        num_missing = int(data.get('num_missing', 0))
        
        # Calculate average contribution
        avg_contribution = 0
        if num_contributors > 0:
            avg_contribution = total_contributions / num_contributors
        
        # Build serialization dictionary
        serialized = {
            'report_data': {
                # Core data
                'data': serialized_data,
                'month_col': data.get('month_col'),
                'name_col': data.get('name_col'),
                'month': data.get('month'),
                'year': data.get('year'),
                
                # Statistics
                'total_contributions': total_contributions,
                'num_contributors': num_contributors,
                'num_missing': num_missing,
                'avg_contribution': round(avg_contribution, 2),
                'completion_rate': round((num_contributors / (num_contributors + num_missing) * 100), 2) if (num_contributors + num_missing) > 0 else 0,
                
                # Financial data
                'money_dispensed': float(data.get('money_dispensed', 0)) if data.get('money_dispensed') else None,
                'total_book_balance': float(data.get('total_book_balance', 0)) if data.get('total_book_balance') else None,
                
                # Metadata
                'report_filename': f"contributions_report_{data.get('year', '')}_{data.get('month', '')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                'generated_at': datetime.now().isoformat(),
                'data_source': data.get('data_source', 'unknown'),
                
                # Column metadata (if available)
                'columns': list(df.columns) if df is not None else [],
                'column_types': {col: str(df[col].dtype) for col in df.columns} if df is not None and not df.empty else {},
                
                # Summary statistics by column (for numeric columns)
                'column_stats': ReportDataSerializer._get_column_stats(df) if df is not None else {}
            },
            'report_path': report_path,
            'metadata': {
                'serialized_at': datetime.now().isoformat(),
                'data_hash': hashlib.md5(str(serialized_data).encode()).hexdigest()[:16] if serialized_data else None,
                'row_count': len(serialized_data)
            }
        }
        
        if include_raw_data and df is not None:
            # Convert to base64 encoded CSV for compact storage
            import base64
            import io
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_string = csv_buffer.getvalue()
            serialized['raw_data_encoded'] = base64.b64encode(csv_string.encode()).decode()
        
        return serialized
    
    @staticmethod
    def _get_column_stats(df):
        """Generate statistics for numeric columns"""
        if df is None or df.empty:
            return {}
        
        stats = {}
        for col in df.columns:
            # Try to convert to numeric
            numeric_series = pd.to_numeric(df[col], errors='coerce')
            
            # Only include if we have numeric data
            if numeric_series.notna().any():
                valid_values = numeric_series.dropna()
                if len(valid_values) > 0:
                    stats[col] = {
                        'min': float(valid_values.min()),
                        'max': float(valid_values.max()),
                        'mean': float(valid_values.mean()),
                        'median': float(valid_values.median()),
                        'std': float(valid_values.std()),
                        'count': int(valid_values.count()),
                        'null_count': int(numeric_series.isna().sum())
                    }
        
        return stats
    
    @staticmethod
    def deserialize(serialized_data):
        """Deserialize data from session storage"""
        if not serialized_data:
            return None
        
        try:
            report_data = serialized_data.get('report_data', {})
            
            # Reconstruct DataFrame
            data_records = report_data.get('data', [])
            df = pd.DataFrame(data_records) if data_records else pd.DataFrame()
            
            # Handle raw data if present
            if 'raw_data_encoded' in serialized_data:
                import base64
                import io
                csv_string = base64.b64decode(serialized_data['raw_data_encoded']).decode()
                df = pd.read_csv(io.StringIO(csv_string))
            
            # Reconstruct original data structure
            result = {
                'data': df,
                'month_col': report_data.get('month_col'),
                'name_col': report_data.get('name_col'),
                'month': report_data.get('month'),
                'year': report_data.get('year'),
                'total_contributions': report_data.get('total_contributions', 0),
                'num_contributors': report_data.get('num_contributors', 0),
                'num_missing': report_data.get('num_missing', 0),
                'money_dispensed': report_data.get('money_dispensed'),
                'total_book_balance': report_data.get('total_book_balance'),
                'data_source': report_data.get('data_source', 'session'),
                'generated_at': report_data.get('generated_at')
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error deserializing report data: {str(e)}")
            return None


class GoogleSheetsManager:
    """Helper class for managing Google Sheets integration"""
    
    @staticmethod
    def test_connection(sheet_url=None):
        """Test Google Sheets connection"""
        if not sheet_url:
            sheet_url = Setting.get_value('google_sheets_url')
        
        if not sheet_url:
            return {'status': 'error', 'message': 'No Google Sheets URL configured'}
        
        try:
            # Validate URL
            if not google_sheets_service._validate_sheet_url(sheet_url):
                return {'status': 'error', 'message': 'Invalid Google Sheets URL format'}
            
            # Test connection
            client = google_sheets_service.get_client()
            if not client:
                return {'status': 'error', 'message': 'Failed to authenticate with Google Sheets'}
            
            # Try to access the sheet
            spreadsheet = client.open_by_url(sheet_url)
            worksheets = spreadsheet.worksheets()
            
            return {
                'status': 'success',
                'message': f'Successfully connected to Google Sheets',
                'sheet_title': spreadsheet.title,
                'worksheet_count': len(worksheets),
                'worksheet_names': [ws.title for ws in worksheets]
            }
            
        except Exception as e:
            logger.error(f"Google Sheets connection test failed: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @staticmethod
    def get_sheet_info(sheet_url):
        """Get detailed information about a Google Sheet"""
        try:
            client = google_sheets_service.get_client()
            if not client:
                return None
            
            spreadsheet = client.open_by_url(sheet_url)
            
            info = {
                'title': spreadsheet.title,
                'url': sheet_url,
                'id': spreadsheet.id,
                'worksheets': [],
                'last_modified': None,  
                'created_time': None    
            }
            
            for ws in spreadsheet.worksheets():
                try:
                    row_count = ws.row_count
                    col_count = ws.col_count
                    values = ws.get_all_values()
                    data_row_count = len(values) - 1 if len(values) > 1 else 0  
                    
                    info['worksheets'].append({
                        'title': ws.title,
                        'index': ws.index,
                        'row_count': row_count,
                        'col_count': col_count,
                        'data_rows': data_row_count,
                        'has_data': data_row_count > 0,
                        'sample_headers': values[0] if len(values) > 0 else []
                    })
                except Exception as e:
                    logger.warning(f"Could not get info for worksheet {ws.title}: {str(e)}")
                    info['worksheets'].append({
                        'title': ws.title,
                        'error': str(e)
                    })
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting sheet info: {str(e)}")
            return None


# Initialize logger
logger = current_app.logger if current_app else logging.getLogger(__name__)