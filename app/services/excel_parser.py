# app/services/excel_parser.py
import pandas as pd
import calendar
from datetime import datetime
from flask import current_app

class ExcelParser:
    @staticmethod
    def find_month_row(df, month_name):
        """Scan through the dataframe to find the row containing month names"""
        for i, row in df.iterrows():
            for cell in row:
                if pd.notna(cell) and month_name.lower() in str(cell).lower():
                    return i
        return None

    @staticmethod
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
        
        # Find the right sheet
        year_sheet = ExcelParser._find_year_sheet(all_sheets, year)
        
        if not year_sheet:
            available_sheets = list(all_sheets.keys())
            raise ValueError(f"No sheet found for year {year}. Available sheets: {available_sheets}")
        
        current_app.logger.info(f"Using sheet: {year_sheet} for year {year}")
        
        # Get the raw sheet data
        raw_df = all_sheets[year_sheet]
        
        # Extract financial info
        financial_info = ExcelParser._extract_financial_info(raw_df)
        
        # Find the row containing month names
        month_row = ExcelParser.find_month_row(raw_df, month_name)
        if month_row is None:
            raise ValueError(f"No row found containing month {month_name}")
        
        # Read with proper header
        df = pd.read_excel(filepath, sheet_name=year_sheet, header=month_row)
        
        # Find month column
        month_col = ExcelParser._find_month_column(df, month_name)
        
        # Find name column
        name_col = ExcelParser._find_name_column(df)
        
        # Clean and process data
        df = df[[name_col, month_col]].dropna(subset=[name_col])
        df = df[df[name_col].astype(str).str.strip() != '']
        df = df[~df[name_col].str.lower().str.contains('total')]
        
        # Convert amounts to numeric
        df[month_col] = pd.to_numeric(df[month_col], errors='coerce')
        
        # Calculate summary stats
        summary_stats = ExcelParser._calculate_summary_stats(df, month_col, name_col)
        
        return {
            'data': df,
            'month': month_name,
            'year': year,
            'name_col': name_col,
            'month_col': month_col,
            **summary_stats,
            **financial_info
        }
    
    @staticmethod
    def _find_year_sheet(all_sheets, year):
        """Find the appropriate sheet for the given year"""
        possible_sheet_names = [
            str(year),
            f"{year} Data",
            f"Data {year}",
            f"Contributions {year}",
            f"{year} Contributions",
        ]
        
        for sheet_name in all_sheets:
            if str(year) in sheet_name:
                return sheet_name
        
        # Check for common patterns
        for sheet_name in all_sheets:
            sheet_lower = sheet_name.lower()
            if any(pattern.lower() in sheet_lower for pattern in ['data', 'contributions']):
                return sheet_name
        
        # Return first sheet if none found
        if all_sheets:
            return list(all_sheets.keys())[0]
        
        return None
    
    @staticmethod
    def _extract_financial_info(raw_df):
        """Extract money dispensed and total book balance from raw dataframe"""
        money_dispensed = None
        total_book_balance = None
        
        for i, row in raw_df.iterrows():
            for cell in row:
                if pd.notna(cell) and isinstance(cell, str):
                    cell_lower = cell.lower()
                    if "money dispensed" in cell_lower:
                        money_dispensed = ExcelParser._extract_numeric_value(raw_df, i, 1)
                    elif "total book balance" in cell_lower:
                        total_book_balance = ExcelParser._extract_numeric_value(raw_df, i, 1)
        
        return {
            'money_dispensed': money_dispensed,
            'total_book_balance': total_book_balance
        }
    
    @staticmethod
    def _extract_numeric_value(df, row_index, col_index):
        """Extract numeric value from specific cell"""
        try:
            value = df.iloc[row_index, col_index]
            if pd.notna(value):
                return float(value)
        except (ValueError, TypeError):
            value = df.iloc[row_index, col_index]
            return value if pd.notna(value) else None
        return None
    
    @staticmethod
    def _find_month_column(df, month_name):
        """Find column containing the specified month"""
        for col in df.columns:
            if pd.notna(col) and month_name.lower() in str(col).lower():
                return col
        raise ValueError(f"No column found for month {month_name}")
    
    @staticmethod
    def _find_name_column(df):
        """Find column containing member names"""
        for col in df.columns:
            if df[col].dropna().apply(lambda x: isinstance(x, str) and "name" in x.lower()).any():
                return col
        return df.columns[0]
    
    @staticmethod
    def _calculate_summary_stats(df, month_col, name_col):
        """Calculate summary statistics from the dataframe"""
        total_contributions = float(df[month_col].sum()) if not df[month_col].empty else 0.0
        num_contributors = int(df[month_col].count()) if not df[month_col].empty else 0
        num_missing = int(len(df) - num_contributors)
        
        return {
            'total_contributions': total_contributions,
            'num_contributors': num_contributors,
            'num_missing': num_missing,
            'defaulters': df[df[month_col].isna()][name_col].tolist()
        }