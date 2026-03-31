import tabula
from app.common.config import *

# Deprecated as of 10/1/2023 - Cashflow section is no longer in the PDF
class CashFlow:
    def __init__(self, pages, year, month):
        self.pages = pages
        self.year = year
        self.month = month
        self.read()

    def read(self):
        tabula_pages = [x + 1 for x in self.pages] # tabula is not 0 indexed
        self.p_df = tabula.read_pdf(f'{PDF_PATH}/{self.year}/{self.month}/{PDF_FILE_TAXABLE}', 
                           pages=tabula_pages, 
                           area=[0,0,100,100], 
                           relative_area=True, 
                           multiple_tables=True, 
                           columns=CASHFLOW_INDICES
                           )
    
    def get_total_core_fund_activity(self, account_pages):
        tabula_pages = [x + 1 for x in account_pages] # tabula is not 0 indexed
        p_df = tabula.read_pdf(f'{PDF_PATH}/{self.year}/{self.month}/{PDF_FILE_TAXABLE}', 
                    pages=tabula_pages, 
                    area=[0,0,100,100], 
                    relative_area=True, 
                    multiple_tables=True, 
                    columns=[400]
                    )
        for df in p_df:
            df = df[df.iloc[:, 0] == 'Total Core Fund Activity']
            if df.index.size > 0:
                return round(float(df.iloc[0,1].replace('$','').replace(',','')), 2)
        return 0.0
            
    def get_key_value(self, key):
        cashflow_section_found = False
        for i in range(0,2):
            if not 'Core Account and Credit Balance C' in self.p_df[i].iloc[:,0].values:
                continue
            else:
                cashflow_section_found = True
            filt = (self.p_df[i].fillna('').iloc[:,0].str.startswith(key))
            if not self.p_df[i].loc[filt].empty: 
                key_found = True
                value = self.p_df[i].loc[filt].iloc[0,1].replace('$','').replace(',','')
                if value == '-':
                    return 0.0
                else:
                    return float(value)
            else:
                continue
        if not cashflow_section_found:
            return None
        else:
            return 0.0
        
if __name__ == '__main__':
    print('Hello')