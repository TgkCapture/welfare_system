# app/services/excel_parser.py
"""
Reads one month from a workbook that isn't in the standard layout.

Where things are is set by the group's SheetMapping (sheet_mapping.py);
anything left automatic is found the way the original Mzugoss layout is
read. Problems say which sheet, row or column is wrong. Cells that hold
text instead of an amount are counted as unpaid and reported as warnings.

Output: the month's member rows as a DataFrame (``data``, ``name_col``,
``month_col``), totals, defaulters, the sheet's own financial figures,
and ``warnings``.
"""
import calendar
from datetime import datetime

import pandas as pd
from flask import current_app

from app.services.sheet_mapping import SheetMapping, cell_position, column_index, column_letter


class ExcelParser:

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_col(value) -> str:
        """Strip non-ASCII characters from column names for error messages."""
        return str(value).encode('ascii', errors='replace').decode('ascii')

    @staticmethod
    def parse_excel(filepath: str, year: int = None, month: int = None, mapping: SheetMapping = None) -> dict:
        """Parse *filepath* and return contribution data for *year*/*month*."""
        year  = year  or datetime.now().year
        month = month or datetime.now().month
        month_name = calendar.month_name[month]
        mapping = mapping or SheetMapping()

        all_sheets = pd.read_excel(filepath, sheet_name=None, header=None)

        year_sheet = ExcelParser._select_sheet(all_sheets, year, mapping)
        current_app.logger.info(f"ExcelParser: using sheet '{year_sheet}' for {year}")

        raw_df = all_sheets[year_sheet]
        financial_info = ExcelParser._financials(raw_df, mapping, year_sheet)

        if mapping.header_row is not None:
            month_row_idx = mapping.header_row - 1
            if month_row_idx >= len(raw_df):
                raise ValueError(f"Sheet '{year_sheet}' has no row {mapping.header_row} "
                                 f"(it ends at row {len(raw_df)}). Check the header row setting.")
        else:
            month_row_idx = ExcelParser._find_month_row(raw_df, month_name)
            if month_row_idx is None:
                raise ValueError(
                    f"Could not find a row containing '{month_name}' "
                    f"in sheet '{year_sheet}'."
                )

        # Re-read using the located row as the header
        df = pd.read_excel(filepath, sheet_name=year_sheet, header=month_row_idx)
        where = f"sheet '{year_sheet}', header row {month_row_idx + 1}"

        if mapping.january_column:
            month_col = ExcelParser._column_at(df, column_index(mapping.january_column) + month - 1,
                                               f'{month_name} (from January in column {mapping.january_column})', where)
        else:
            month_col = ExcelParser._find_month_column(df, month_name, where)
        if mapping.name_column:
            name_col = ExcelParser._column_at(df, column_index(mapping.name_column), 'the name column', where)
        else:
            name_col = ExcelParser._find_name_column(df)

        warnings = ExcelParser._text_amounts(df, name_col, month_col, month_row_idx, year_sheet)
        df = ExcelParser._clean_member_rows(df, name_col, month_col)

        summary = ExcelParser._calculate_summary(df, month_col, name_col)

        return {
            'data':      df,
            'month':     month_name,
            'year':      year,
            'name_col':  name_col,
            'month_col': month_col,
            'sheet':     year_sheet,
            'warnings':  warnings,
            **summary,
            **financial_info,
        }

    # ------------------------------------------------------------------
    # Sheet discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _select_sheet(all_sheets: dict, year: int, mapping: SheetMapping):
        """The sheet to read for *year*, following the mapping."""
        names = list(all_sheets)
        if mapping.sheet_mode == 'first':
            if not names:
                raise ValueError('The workbook has no sheets.')
            return names[0]
        if mapping.sheet_mode == 'named':
            wanted = mapping.sheet_name.strip().casefold()
            match = next((n for n in names if str(n).strip().casefold() == wanted), None)
            if match is None:
                raise ValueError(f"No sheet named '{mapping.sheet_name}'. Sheets in the file: {names}")
            return match
        if mapping.sheet_pattern:
            wanted = mapping.sheet_pattern.replace('{year}', str(year)).strip().casefold()
            match = next((n for n in names if str(n).strip().casefold() == wanted), None)
            if match is None:
                raise ValueError(f"No sheet named '{mapping.sheet_pattern.replace('{year}', str(year))}' "
                                 f"for {year}. Sheets in the file: {names}")
            return match

        year_sheet = ExcelParser._find_year_sheet(all_sheets, year)
        if not year_sheet:
            raise ValueError(
                f"No sheet found for year {year}. "
                f"Available sheets: {names}"
            )
        return year_sheet

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
        """Return the POSITIONAL row index containing month_name, for use as header=N."""
        for positional_idx, (label_idx, row) in enumerate(df.iterrows()):
            for cell in row:
                if pd.notna(cell) and month_name.lower() in str(cell).lower():
                    return positional_idx   # ← positional, not label
        return None

    # ------------------------------------------------------------------
    # Column detection
    # ------------------------------------------------------------------

    @staticmethod
    def _find_month_column(df: pd.DataFrame, month_name: str, where: str = '') -> str:
        """Return the column label whose header contains *month_name* (or its first three letters)."""
        for col in df.columns:
            if pd.notna(col) and month_name.lower() in str(col).lower():
                return col
        # Short headers such as "Mar" or "Mar-25"
        for col in df.columns:
            if pd.notna(col) and str(col).strip().lower().startswith(month_name[:3].lower()):
                return col
        raise ValueError(
            f"No column found for month '{month_name}'"
            f"{f' in {where}' if where else ''}. "
            f"Available columns: {[ExcelParser._safe_col(c) for c in df.columns]}"
        )

    @staticmethod
    def _column_at(df: pd.DataFrame, index: int, what: str, where: str):
        """The column label at a 0-based position, or an error naming the column."""
        if index >= len(df.columns):
            raise ValueError(f"Column {column_letter(index)} ({what}) is past the last column with data "
                             f"({column_letter(len(df.columns) - 1)}) in {where}.")
        return df.columns[index]

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

    @staticmethod
    def _text_amounts(df, name_col, month_col, header_idx, sheet) -> list:
        """Warnings for member rows whose amount cell holds text rather than a number."""
        warnings = []
        col_letter = column_letter(list(df.columns).index(month_col))
        for idx, row in df.iterrows():
            name, value = row[name_col], row[month_col]
            if pd.isna(name) or not str(name).strip() or not isinstance(value, str) or not value.strip():
                continue
            if pd.isna(pd.to_numeric(value, errors='coerce')):
                warnings.append({
                    'where': f"Sheet '{sheet}' cell {col_letter}{header_idx + 2 + idx}",
                    'message': f'{str(name).strip()}: {value.strip()!r} is not an amount, so it counts as unpaid.',
                })
        return warnings

    # ------------------------------------------------------------------
    # Financial summary rows
    # ------------------------------------------------------------------

    @staticmethod
    def _financials(raw_df: pd.DataFrame, mapping: SheetMapping, sheet) -> dict:
        if mapping.financials == 'none':
            return {'money_dispensed': None, 'total_book_balance': None}
        if mapping.financials == 'cells':
            return {
                'money_dispensed':    ExcelParser._cell_number(raw_df, mapping.money_dispensed_cell, sheet),
                'total_book_balance': ExcelParser._cell_number(raw_df, mapping.book_balance_cell, sheet),
            }
        return ExcelParser._extract_financial_info(raw_df)

    @staticmethod
    def _cell_number(raw_df, ref, sheet):
        if not ref:
            return None
        row, col = cell_position(ref)
        value = raw_df.iloc[row, col] if row < len(raw_df) and col < len(raw_df.columns) else None
        if value is None or pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Cell {ref} on sheet '{sheet}' should hold an amount but holds {value!r}.")

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
