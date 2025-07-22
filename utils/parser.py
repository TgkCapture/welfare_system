import pandas as pd
from utils.gsheets import get_sheet_data

def parse_contributions(source, source_type='file', year=None):
    if source_type == 'gsheet':
        data = get_sheet_data(source)
        df = pd.DataFrame(data)
    else:  # file upload
        df = pd.read_excel(source)
    
    # Clean and transform data
    df = df.rename(columns={'Unnamed: 0': 'Name'})
    df = df.dropna(subset=['Name'])
    
    if year:
        # Filter for specific year 
        pass
        
    return df