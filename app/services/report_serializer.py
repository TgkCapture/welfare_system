# app/services/report_serializer.py
import pandas as pd

class ReportDataSerializer:
    """Utility class for serializing report data"""
    
    @staticmethod
    def serialize(data, report_path):
        """Serialize report data for session storage"""
        # Ensure data['data'] is a DataFrame
        if isinstance(data['data'], pd.DataFrame):
            data_dict = data['data'].to_dict('records')
        else:
            data_dict = data['data']
        
        # Convert numeric values
        money_dispensed = data.get('money_dispensed')
        total_book_balance = data.get('total_book_balance')
        
        # Handle None values for numeric fields
        if money_dispensed is not None:
            try:
                money_dispensed = float(money_dispensed)
            except (ValueError, TypeError):
                money_dispensed = None
        
        if total_book_balance is not None:
            try:
                total_book_balance = float(total_book_balance)
            except (ValueError, TypeError):
                total_book_balance = None
        
        return {
            'report_data': {
                'data': data_dict,
                'month_col': data['month_col'],
                'name_col': data['name_col'],
                'month': data['month'],
                'year': data['year'],
                'total_contributions': float(data['total_contributions']),
                'num_contributors': int(data['num_contributors']),
                'num_missing': int(data['num_missing']),
                'money_dispensed': money_dispensed,
                'total_book_balance': total_book_balance,
                'report_filename': f"contributions_report_{data['year']}_{data['month']}.pdf"
            },
            'report_path': report_path
        }