import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from app.common.config import CREDS_JSON, SCOPE, HOLDINGS_WEB_APP_URL
import requests

class GoogleSheetConnector:
    def __init__(self):
        creds = ServiceAccountCredentials.from_json_keyfile_dict(CREDS_JSON, SCOPE)
        self.gc = gspread.authorize(creds)

    def read_sheet(self, sheet_name):
        # Open the sheet
        sheet = self.gc.open(sheet_name).sheet1

        # Read all values
        values = sheet.get_all_values()
        df = pd.DataFrame(values[1:], columns=values[0])
        try:
            df = df.astype({'Beginning_Market_Value':'float',
                            'Quantity':'float',
                            'Price_Per_Unit':'float',
                            'Ending_Market_Value':'float',
                            'Total_Cost_Basis':'float',
                            'Unrealized_Gain/Loss': 'float',
                            'Day_Gain': 'float'})
        except:
            return df
        return df
        #for row in values:
        #    print(row)

    def read(self):

        # worksheet.format("C:C", { "numberFormat": { "type": "DATE", "pattern": "mm/dd/yyyy" } })
        # worksheet.append_rows(rowEntry)

        entry_list = self.worksheet.get_all_values()
        columns = entry_list[0]
        entry_list.pop(0)
        df = pd.DataFrame(entry_list, columns=columns)
        return df.drop(['Timestamp'], axis=1)

    def trigger_recalculation(self):
        response = requests.get(HOLDINGS_WEB_APP_URL)
        if response.status_code == 200:
            print("Recalculation triggered successfully.")
        else:
            print(f"Failed to trigger recalculation: {response.status_code}")

    def append(self, worksheet, df):
        gsheet = self.gc.open('Statements')
        sheet = gsheet.worksheet(worksheet)
        values = sheet.get_all_values()
        last_non_empty_row = len(values)

        data_list = df.values.tolist()
        data_list = [[item.strftime('%Y-%m-%d') if isinstance(item, pd.Timestamp) else item.replace(',','').replace('$','') if not (isinstance(item, float) or isinstance(item, int)) else round(item, 2) for item in row] for row in data_list]
        data_list = df.round(2).astype(str).values.tolist()

        #sheet.insert_rows(data_list, last_non_empty_row + 1)
        sheet.update(f'A{last_non_empty_row + 1}', data_list, value_input_option="USER_ENTERED")

        for i in range(len(data_list)+1):
            j = last_non_empty_row + i
            sheet.update(f"M{j}", f'=IF(K{j} = "",0,GOOGLEFINANCE(D{j}))', raw=False)

        #if len(df.columns)>0 and df.iloc[:,0].dtype == 'float64':
        #    sheet.format("A3:A", {"numberFormat": {"type": "CURRENCY"}})
        #if len(df.columns)>1 and df.iloc[:,1].dtype == 'float64':
        #    sheet.format("B3:B", {"numberFormat": {"type": "CURRENCY"}})
        #if len(df.columns)>2 and df.iloc[:,2].dtype == 'float64':
        #    sheet.format("C3:C", {"numberFormat": {"type": "CURRENCY"}})
        #if len(df.columns)>3 and df.iloc[:,3].dtype == 'float64':
        #    sheet.format("D3:D", {"numberFormat": {"type": "CURRENCY"}})
        #if len(df.columns)>4 and df.iloc[:,4].dtype == 'float64':
        #    sheet.format("E3:E", {"numberFormat": {"type": "CURRENCY"}})
        #if len(df.columns)>5 and df.iloc[:,5].dtype == 'float64':
        #    sheet.format("F3:F", {"numberFormat": {"type": "CURRENCY"}})
        #if len(df.columns)>6 and df.iloc[:,6].dtype == 'float64':
        #    sheet.format("G3:G", {"numberFormat": {"type": "CURRENCY"}})
        #if len(df.columns)>7 and df.iloc[:,7].dtype == 'float64':
        #    sheet.format("H3:H", {"numberFormat": {"type": "CURRENCY"}})

    def set_price_per_unit_formula(self, df):
        df['Price_Per_Unit'] = pd.to_numeric(df['Price_Per_Unit'], errors='coerce')
        df['Price_Per_Unit'] = df['Price_Per_Unit'].astype(str)
        for i in range(len(df)):
            if df.iloc[i, 9] != '':
                ticker_loc = f"J{i+2}"
                df.iloc[i, 3] = f'=GOOGLEFINANCE({ticker_loc})'
        return df

    def set_ending_market_value_formula(self, df):
        df['Ending_Market_Value'] = df['Ending_Market_Value'].astype(str)
        for i in range(len(df)):
            df.iloc[i, 4] = f'=C{i+2}*D{i+2}'
        return df

    def set_unrealized_gain_loss_formula(self, df):
        df['Unrealized_Gain/Loss'] = df['Unrealized_Gain/Loss'].astype(str)
        for i in range(len(df)):
            df.iloc[i, 6] = f'=E{i+2}-F{i+2}'
        return df
    
    def set_day_change_formula(self, df):
        df['Day_Change'] = ''
        for i in range(len(df)):
            df.iloc[i, 10] = f'=GOOGLEFINANCE(J{i+2},"change")'
        return df

    def set_day_gain_formula(self, df):
        df['Day_Gain'] = ''
        for i in range(len(df)):
            df.iloc[i, 11] = f'=C{i+2}*K{i+2}'
        return df

    def write_df_to_sheet(self, df):
        gsheet = self.gc.open('Holdings')
        #sheet = gsheet.worksheet(worksheet)
        sheet = gsheet.sheet1
        sheet.clear()

        #data_list = df.values.tolist()
        #data_list = [[item.strftime('%Y-%m-%d') if isinstance(item, pd.Timestamp) else item.replace(',','').replace('$','') if not (isinstance(item, float) or isinstance(item, int)) else round(item, 2) for item in row] for row in data_list]
        #data_list = df.round(2).astype(str).values.tolist()

        #data_list.insert(0, df.columns.tolist())
        #gsheet.values_clear(f"{sheet}!A3:Z10000")

        data = [df.columns.tolist()] + df.values.tolist()

        data_df = pd.DataFrame(data[1:], columns=data[0])

        # Column J
        data_df['Ticker'] = data_df['Description'].apply(lambda x: x.split('(')[-1].split(')')[0])
        data_df = self.set_price_per_unit_formula(data_df)
        data_df = self.set_ending_market_value_formula(data_df)
        data_df = self.set_unrealized_gain_loss_formula(data_df)
        data_df = self.set_day_change_formula(data_df)
        data_df = self.set_day_gain_formula(data_df)

        data = [data_df.columns.tolist()] + data_df.values.tolist()
        sheet.update(data, value_input_option="USER_ENTERED")
    
    def read_sheet_to_df(self, sheet_name):
        # Open the sheet
        sheet = self.gc.open(sheet_name).sheet1

        # Read all values
        values = sheet.get_all_values()
        df = pd.DataFrame(values[1:], columns=values[0])
        df = df.dropna(how='all')
        df.reset_index(drop=True, inplace=True)
        return df
        
    def create_holdings_map(self, account):
        holdings_map_df = pd.DataFrame()
        df = self.holdings_df.copy()
        holdings_map_df['Ticker'] = df['Description'].apply(lambda x: x.split('(')[-1].split(')')[0])
        holdings_map_df['Account'] = df['Account']
        holdings_map_df['Weight'] = ''
        df.reset_index(inplace=True)
        for i in range(len(holdings_map_df)):
            holdings_map_df.iloc[i, 2] = f'=D{i+3}/SUM(D:D)'
        holdings_map_df['Ending_Market_Value'] = df['Ending_Market_Value']
        holdings_map_df = holdings_map_df[df['Account'] == account]
        self.write(f'{account}Map', holdings_map_df)
            
    def write(self, worksheet, df):
        gsheet = self.gc.open('Statements')
        sheet = gsheet.worksheet(worksheet)
        data_list = df.values.tolist()
        data_list = [[item.strftime('%Y-%m-%d') if isinstance(item, pd.Timestamp) else item.replace(',','').replace('$','') if not isinstance(item, float) else round(item, 2) for item in row] for row in data_list]
        data_list = df.round(2).astype(str).values.tolist()
        #data_list.insert(0, df.columns.tolist())
        gsheet.values_clear(f"{worksheet}!A3:Z10000")
        sheet.update('A3', data_list, value_input_option="USER_ENTERED")
        # sort by date
        sheet.sort((5, 'asc'))
        if len(df.columns)>0 and df.iloc[:,0].dtype == 'float64':
            sheet.format("A3:A", {"numberFormat": {"type": "CURRENCY"}})
        if len(df.columns)>1 and df.iloc[:,1].dtype == 'float64':
            sheet.format("B3:B", {"numberFormat": {"type": "CURRENCY"}})
        if len(df.columns)>2 and df.iloc[:,2].dtype == 'float64':
            sheet.format("C3:C", {"numberFormat": {"type": "CURRENCY"}})
        if len(df.columns)>3 and df.iloc[:,3].dtype == 'float64':
            sheet.format("D3:D", {"numberFormat": {"type": "CURRENCY"}})
        if len(df.columns)>4 and df.iloc[:,4].dtype == 'float64':
            sheet.format("E3:E", {"numberFormat": {"type": "CURRENCY"}})
        if len(df.columns)>5 and df.iloc[:,5].dtype == 'float64':
            sheet.format("F3:F", {"numberFormat": {"type": "CURRENCY"}})
        if len(df.columns)>6 and df.iloc[:,6].dtype == 'float64':
            sheet.format("G3:G", {"numberFormat": {"type": "CURRENCY"}})
        if len(df.columns)>7 and df.iloc[:,7].dtype == 'float64':
            sheet.format("H3:H", {"numberFormat": {"type": "CURRENCY"}})

    def write_stats(self, stats):
        sheet = self.gc.open('Statements').worksheet('Stats')
        table_list = []
        for account in stats.keys():
            table_list.append(list(stats[account].to_dict().values()))
        #table_list.insert(0, list(stats['all'].to_dict().keys()))

        # calculate sum of column 'Ending Balance' and append it to the column header
        #table_df = pd.DataFrame(table_list)
        #ending_balance_sum = table_df['Ending Balance'].sum()

        sheet.update('A3', table_list)

if __name__ == '__main__':
    gc = GoogleSheetConnector()
    df = gc.read_sheet('Holdings')
    df.to_csv('/finance/processed/holdings.csv', index=False)
    exit()

    holdings_df = pd.read_csv('/finance/processed/holdings.csv')
    gc.write_df_to_sheet(holdings_df)
    exit()

    gc.trigger_recalculation()
    values = gc.read_sheet('Holdings')
    df = pd.DataFrame(values[1:], columns=values[0])
    Ending_Market_Value = df['Ending_Market_Value'].astype(float).sum()
    print(f"Ending Market Value: {Ending_Market_Value}")
