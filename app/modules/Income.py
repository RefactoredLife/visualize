import tabula
import pandas as pd
import os
from app.common.config import TAX_PATH, MAP_1040
from app.common.utils import *

def find_tax_returns():
    matching_files = []
    for root, dirs, files in os.walk(TAX_PATH):
        for file in files:
            if file.startswith('1040_2019'):
                matching_files.append(os.path.join(root, file))
    return matching_files
    
def truncate_header(page, year):
    df = pd.DataFrame(columns=['line', 'amount'])
    page.columns = ['line','amount']
    #mask = page.iloc[:, 0].str.startswith(MAP_1040.get(year).get("FIRST_LINE"), na=False)
    mask = page.iloc[:, 0] == MAP_1040.get(year).get("FIRST_LINE")
    if mask.any():
        iIncome = page.index[mask][0]
        page = page.iloc[iIncome:]
        #page.columns = ['line','amount']
        df = safe_concat(df, page) 
    return df

def truncate_footer(page):
    df = pd.DataFrame(columns=['line', 'amount'])
    page.columns = ['line','amount']
    mask = page.iloc[:, 0].str.startswith('37', na=False)
    if mask.any():
        iIncome = page.index[mask][0]
        page = page.iloc[:iIncome+1]
    return page

def page1(pdf_file, year):
    pages = tabula.read_pdf(pdf_file, pages=[1], area=MAP_1040.get(year).get("PAGE1_AREA"), relative_area=False, multiple_tables=False, columns=[497])
    df = pd.DataFrame(columns=['line', 'amount'])
    for page in pages:
        df = truncate_header(page, year)
    df.dropna(axis=0, inplace=True)
    df.reset_index(inplace=True, drop=True)
    df['amount'] = df['amount'].str.replace(',','').astype(float, errors="ignore")
    return df

def print_data(df, year):
    income_dict = dict(zip(df['line'], df['amount']))
    total_w2_income = income_dict.get('1a',0.0)
    if total_w2_income == 0.0:
        total_w2_income = income_dict.get('1',0.0)
    print(f'Total income from W2 box 1 \t{income_dict.get(MAP_1040.get(year).get("W2_WAGES"), 0.0)}')
    print(f'Taxable Interest \t\t{income_dict.get(MAP_1040.get(year).get("TAXABLE_INTEREST"),0.0)}')
    print(f'Ordinary Dividends \t\t{income_dict.get(MAP_1040.get(year).get("ORDINARY_DIVIDEND"),0.0)}')
    print(f'Capital Gains (Claimed) \t{income_dict.get(MAP_1040.get(year).get("CAPITAL_GAIN"),0.0)}')
    print(f'Total Income \t\t\t{income_dict.get(MAP_1040.get(year).get("TOTAL_INCOME"),0.0)}')
    print(f'Adjusted Gross Income (AGI) \t{income_dict.get(MAP_1040.get(year).get("AGI"),0.0)}')
    #print(f'Standard Deduction \t\t{income_dict.get('12',0.0)}')
    print(f'Taxable Income \t\t\t{income_dict.get(MAP_1040.get(year).get("TAXABLE_INCOME"),0.0)}')
    if year == "2018":
        print(f'Child Tax Credit \t\t{income_dict.get(MAP_1040.get(year).get("CHILD_TAX_CREDIT"),0.0)}')
        print(f'Total Tax \t\t\t{income_dict.get(MAP_1040.get(year).get("TOTAL_TAX"),0.0)}')
        print(f'Total Payments \t\t\t{income_dict.get(MAP_1040.get(year).get("TOTAL_PAYMENTS"),0.0)}')
        amount_due = income_dict.get(MAP_1040.get(year).get("OWE"), 0.0)
        if amount_due == 0.0:
            print(f'Tax Refund \t\t\t{income_dict.get(MAP_1040.get(year).get("REFUND"),0.0)}')
        else:
            print(f'Tax Owed \t\t\t{amount_due}')
    #income_dict = dict(zip(df['line'], df['amount']))
    else:
        print(f'Child Tax Credit \t\t{income_dict.get(MAP_1040.get(year).get("CHILD_TAX_CREDIT"),0.0)}')
        print(f'Total Tax \t\t\t{income_dict.get(MAP_1040.get(year).get("TOTAL_TAX"),0.0)}')
        print(f'Total Payments \t\t\t{income_dict.get(MAP_1040.get(year).get("TOTAL_PAYMENTS"),0.0)}')
        amount_due = income_dict.get(MAP_1040.get(year).get("OWE"), 0.0)
        if amount_due == 0.0:
            print(f'Tax Refund \t\t\t{income_dict.get(MAP_1040.get(year).get("REFUND"),0.0)}')
        else:
            print(f'Tax Owed \t\t\t{amount_due}')
        

def page2(pdf_file, year):
    pages = tabula.read_pdf(pdf_file, pages=[2], area=[10,477,430,600], relative_area=False, multiple_tables=False, columns=[497])
    df = pd.DataFrame(columns=['line', 'amount'])
    for page in pages:
        page.columns = ['line','amount']
        df = pd.concat([df, page])        
    df = truncate_footer(df)
    df['amount'] = pd.to_numeric(df['amount'].str.replace(',', ''), errors='coerce')
    df = df[df['amount'].notna()]

    df.dropna(axis=0, inplace=True)
    df.reset_index(inplace=True, drop=True)
    return df

pdf_files = find_tax_returns()
for year in range(2017, 2025):
    try:
        pdf_file = f"{TAX_PATH}/1040_{year}.pdf"
        print(f'\n{pdf_file}\n')
        df = page1(pdf_file, str(year))
        if year != 2018:
            df = pd.concat([df, page2(pdf_file, str(year))])
        print(df)
        print_data(df, str(year))
    except FileNotFoundError as e:
        print(e)
