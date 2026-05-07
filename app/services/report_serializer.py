# app/services/report_serializer.py
"""
Serialise parsed Excel data into a Flask session-safe dict.
"""
import pandas as pd


class ReportDataSerializer:
    """Convert ExcelParser output into a session-storable dict."""

    @staticmethod
    def serialize(data: dict, report_path: str) -> dict:
        """Return a session-safe dict containing report data and file path.
        """
        # Serialise the DataFrame — records format is a plain list of dicts
        raw = data.get('data')
        if isinstance(raw, pd.DataFrame):
            data_records = ReportDataSerializer._df_to_records(raw)
        else:
            data_records = raw or []

        return {
            'report_data': {
                'data':               data_records,
                'month_col':          data['month_col'],
                'name_col':           data['name_col'],
                'month':              data['month'],
                'year':               int(data['year']),
                'total_contributions': float(data.get('total_contributions', 0)),
                'num_contributors':   int(data.get('num_contributors', 0)),
                'num_missing':        int(data.get('num_missing', 0)),
                'money_dispensed':    ReportDataSerializer._safe_float(
                    data.get('money_dispensed')
                ),
                'total_book_balance': ReportDataSerializer._safe_float(
                    data.get('total_book_balance')
                ),
                'report_filename': (
                    f"contributions_report"
                    f"_{data['year']}_{data['month']}.pdf"
                ),
            },
            'report_path': report_path,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _df_to_records(df: pd.DataFrame) -> list:
        """Convert a DataFrame to a list of JSON-safe dicts.
        """
        records = []
        for row in df.to_dict('records'):
            clean = {}
            for k, v in row.items():
                if hasattr(v, 'item'):
                    # numpy scalar → Python scalar
                    v = v.item()
                elif v != v:
                    # NaN check (NaN != NaN is True)
                    v = None
                clean[k] = v
            records.append(clean)
        return records

    @staticmethod
    def _safe_float(value) -> float | None:
        """Return a Python float, or None if value is absent / unconvertible."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None