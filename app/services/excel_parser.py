# app/services/excel_parser.py
"""
Excel file parser for contribution data.
"""
import calendar
from datetime import datetime

import pandas as pd
from flask import current_app


class ExcelParser:

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def parse_excel(filepath: str, year: int = None, month: int = None) -> dict:
        """Parse *filepath* and return contribution data for *year*/*month*.
        """
        year  = year  or datetime.now().year
        month = month or datetime.now().month
        month_name = calendar.month_name[month]

        all_sheets = pd.read_excel(filepath, sheet_name=None, header=None)

        year_sheet = ExcelParser._find_year_sheet(all_sheets, year)
        if not year_sheet:
            available = list(all_sheets.keys())
            raise ValueError(
                f"No sheet found for year {year}. "
                f"Available sheets: {available}"
            )

        current_app.logger.info(f"ExcelParser: using sheet '{year_sheet}' for {year}")

        raw_df = all_sheets[year_sheet]
        financial_info = ExcelParser._extract_financial_info(raw_df)

        month_row_idx = ExcelParser._find_month_row(raw_df, month_name)
        if month_row_idx is None:
            raise ValueError(
                f"Could not find a row containing '{month_name}' "
                f"in sheet '{year_sheet}'."
            )

        # Re-read using the located row as the header
        df = pd.read_excel(filepath, sheet_name=year_sheet, header=month_row_idx)

        month_col = ExcelParser._find_month_column(df, month_name)
        name_col  = ExcelParser._find_name_column(df)

        df = ExcelParser._clean_member_rows(df, name_col, month_col)

        summary = ExcelParser._calculate_summary(df, month_col, name_col)

        return {
            'data':      df,
            'month':     month_name,
            'year':      year,
            'name_col':  name_col,
            'month_col': month_col,
            **summary,
            **financial_info,
        }

    # ------------------------------------------------------------------
    # Sheet discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _find_year_sheet(all_sheets: dict, year: int):
        """Return the sheet name that best represents *year*, or None."""
        year_str = str(year)

        # Exact or partial match on year string (most reliable)
        for name in all_sheets:
            if year_str in str(name):
                return name

        # Fall back to sheets labelled with common data keywords
        for name in all_sheets:
            if any(kw in str(name).lower() for kw in ('data', 'contributions', 'members')):
                return name

        # Last resort: first sheet
        if all_sheets:
            first = list(all_sheets.keys())[0]
            current_app.logger.warning(
                f"ExcelParser: could not find sheet for year {year}, "
                f"falling back to first sheet '{first}'"
            )
            return first

        return None

    # ------------------------------------------------------------------
    # Header row detection
    # ------------------------------------------------------------------

    @staticmethod
    def _find_month_row(df: pd.DataFrame, month_name: str):
        """Scan every cell to find the row index that contains *month_name*."""
        for i, row in df.iterrows():
            for cell in row:
                if pd.notna(cell) and month_name.lower() in str(cell).lower():
                    return i
        return None

    # ------------------------------------------------------------------
    # Column detection
    # ------------------------------------------------------------------

    @staticmethod
    def _find_month_column(df: pd.DataFrame, month_name: str) -> str:
        """Return the column label whose header contains *month_name*.
        """
        for col in df.columns:
            if pd.notna(col) and month_name.lower() in str(col).lower():
                return col
        raise ValueError(
            f"No column found for month '{month_name}'. "
            f"Available columns: {list(df.columns)}"
        )

    @staticmethod
    def _find_name_column(df: pd.DataFrame) -> str:
        """Heuristically locate the member-name column.
        """
        # Check header labels first
        for col in df.columns:
            if pd.notna(col) and 'name' in str(col).lower():
                return col

        # Check cell content
        for col in df.columns:
            has_name_cells = (
                df[col].dropna()
                .apply(lambda x: isinstance(x, str) and 'name' in x.lower())
                .any()
            )
            if has_name_cells:
                return col

        # Fall back to first column
        first = df.columns[0]
        current_app.logger.warning(
            f"ExcelParser: could not identify name column, "
            f"falling back to first column '{first}'"
        )
        return first

    # ------------------------------------------------------------------
    # Data cleaning
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_member_rows(
        df: pd.DataFrame, name_col: str, month_col: str
    ) -> pd.DataFrame:
        """Return a clean DataFrame with only valid member rows."""
        df = df[[name_col, month_col]].copy()

        # Drop rows with no name
        df = df.dropna(subset=[name_col])
        df = df[df[name_col].astype(str).str.strip() != '']

        # Drop summary / total rows — these are not members
        mask = ~df[name_col].astype(str).str.lower().str.contains(
            r'\btotal\b|\bmoney\b|\bbalance\b|\bdispensed\b',
            regex=True,
        )
        df = df[mask]

        # Coerce amounts — non-numeric becomes NaN (= defaulter)
        df[month_col] = pd.to_numeric(df[month_col], errors='coerce')

        return df.reset_index(drop=True)

    # ------------------------------------------------------------------
    # Financial summary rows
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_financial_info(raw_df: pd.DataFrame) -> dict:
        """Scan the raw sheet for Money Dispensed and Total Book Balance rows."""
        money_dispensed    = None
        total_book_balance = None

        for i, row in raw_df.iterrows():
            for cell in row:
                if not (pd.notna(cell) and isinstance(cell, str)):
                    continue
                cell_lower = cell.lower()
                if 'money dispensed' in cell_lower and money_dispensed is None:
                    money_dispensed = ExcelParser._numeric_from_row(raw_df, i)
                elif 'total book balance' in cell_lower and total_book_balance is None:
                    total_book_balance = ExcelParser._numeric_from_row(raw_df, i)

        return {
            'money_dispensed':    money_dispensed,
            'total_book_balance': total_book_balance,
        }

    @staticmethod
    def _numeric_from_row(df: pd.DataFrame, row_idx: int):
        """Return the first numeric value found in *row_idx* after column 0."""
        for col_idx in range(1, len(df.columns)):
            try:
                val = df.iloc[row_idx, col_idx]
                if pd.notna(val):
                    return float(val)
            except (ValueError, TypeError):
                continue
        return None

    # ------------------------------------------------------------------
    # Summary statistics
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_summary(
        df: pd.DataFrame, month_col: str, name_col: str
    ) -> dict:
        """Return contribution totals and the defaulter name list."""
        paid_mask = df[month_col].notna() & (df[month_col] > 0)

        total_contributions = float(df.loc[paid_mask, month_col].sum())
        num_contributors    = int(paid_mask.sum())
        num_missing         = int((~paid_mask).sum())
        defaulters          = df.loc[~paid_mask, name_col].tolist()

        return {
            'total_contributions': total_contributions,
            'num_contributors':    num_contributors,
            'num_missing':         num_missing,
            'defaulters':          defaulters,
        }