import pandas as pd
from app.common.config import ACTIVE_ACCOUNTS
from datetime import datetime
import os

class Retirement():
    def __init__(self):
        csv_path = '/finance/processed/retirement.csv'
        if os.path.exists(csv_path):
            self.df = pd.read_csv(csv_path)
            self.df['date'] = pd.to_datetime(self.df['date'])
            return
        columns=['date', 'age','traditional_ira','roth_ira','brokerage','rmd','social_security_income','roth_income','brokerage_withdrawal','total_income','standard_deduction','tax','medicare_part_a','medicare_part_b','non_housing_expenses','rent','property_tax','total_expenses','surplus_deficit','home_equity','net_worth']
        self.df = pd.DataFrame(columns=columns)

        self.current_balances = get_current_balances()
        set_dates()
        self.df['age'] = self.df['date'].dt.year - 1971
        set_initial_balances()
        set_ssa()
        set_traditional_ira()
        set_roth_ira()
        set_brokerage()
        set_total_income()
        set_standard_deduction()
        set_tax()
        self.df['medicare_part_a'] = 0.00
        set_medicare_part_b()
        set_non_housing_expenses()
        set_rent()
        self.df['property_tax'] = 0.00
        set_total_expenses()
        set_surplus_deficit()
        self.df['home_equity'] = 0.00
        set_net_worth()

        # Based on surplus_deficit, go back and adjust brokerage_withdrawal
        for i in range(1, len(self.df)):
            self.df.loc[i, 'brokerage_withdrawal'] = self.df.loc[i, 'brokerage_withdrawal'] - self.df.loc[i, 'surplus_deficit']

        # recalculate I, J, L, Total_expenses, S, Networth
        set_total_income()
        set_tax()
        set_total_expenses()
        set_surplus_deficit()
        set_net_worth()

        # Format selected columns as currency in millions
        columns_to_format =['traditional_ira','roth_ira','brokerage','rmd','social_security_income','roth_income','brokerage_withdrawal','total_income','standard_deduction','tax','medicare_part_a','medicare_part_b','non_housing_expenses','rent','property_tax','total_expenses','surplus_deficit','home_equity','net_worth']
        for col in columns_to_format:
            self.df[col] = self.df[col].apply(lambda x: f"${x / 1_000_000:.2f}M")

        # Save to CSV
        self.df.to_csv(csv_path, index=False)

def get_current_balance(self, account_name):
    return self.current_balances[self.current_balances['Account'] == account_name]['Balance'].values[0]

def get_current_balances(self):
    balances = pd.read_csv('/finance/processed/balances.csv')
    latest_balances = balances.groupby('Account')['Date'].max().reset_index()
    current_balances = balances[balances['Date'] == latest_balances['Date'].max()]
    current_balances.drop(columns=['Date'], inplace=True)
    current_balances['Account'] = current_balances['Account'].str.lower()
    accounts = [account.lower() for account in ACTIVE_ACCOUNTS]
    current_balances = current_balances[current_balances['Account'].isin(accounts + ['external_ira','cash'])]
    return current_balances

def set_dates(self):
    current_year = datetime.today().year
    years = range(current_year, 2072)
    dates = [f"{year}-01-01" for year in years]
    #self.df = pd.DataFrame({'date': pd.to_datetime(dates)},columns=columns)
    self.df['date'] = pd.to_datetime(dates)
    
# Initialize '401K' column
def set_initial_balances(self):
    self.df.loc[0, 'traditional_ira'] = get_current_balance('rolloverira')+get_current_balance('hsa')+get_current_balance('external_ira')
    self.df.loc[0, 'roth_ira'] = get_current_balance('roth')
    self.df.loc[0, 'brokerage'] = get_current_balance('growth')+ get_current_balance('utma')+ get_current_balance('cash')+17000.00 # crypto

def set_traditional_ira(self):
    self.df['rmd'] = 0.00
    for i in range(1, len(self.df)):
        prev_401k = self.df.loc[i - 1, 'traditional_ira']
        prev_rmd = self.df.loc[i - 1, 'rmd']
        self.df.loc[i, 'traditional_ira'] = prev_401k * 1.13 - prev_rmd
        if self.df.loc[i, 'age'] > 72:
            self.df.loc[i, 'rmd'] = self.df.loc[i - 1, 'traditional_ira'] * 0.0365
    self.df['traditional_ira'] = self.df['traditional_ira'].round(2)

def set_roth_ira(self):
    self.df['roth_income'] = 0.00
    for i in range(1, len(self.df)):
        prev_roth = self.df.loc[i - 1, 'roth_ira']
        prev_rmd = self.df.loc[i - 1, 'roth_income']
        self.df.loc[i, 'roth_ira'] = prev_roth * 1.13 - prev_rmd
    self.df['roth_ira'] = self.df['roth_ira'].round(2)
    
def set_brokerage(self):
    self.df['brokerage_withdrawal'] = 0.00
    self.df.loc[0, 'brokerage_withdrawal'] = 130000.00
    for i in range(1, len(self.df)):
        prev_brokerage = self.df.loc[i - 1, 'brokerage']
        prev_withdrawal = self.df.loc[i - 1, 'brokerage_withdrawal']
        self.df.loc[i, 'brokerage'] = prev_brokerage * 1.14 - prev_withdrawal
        if self.df.loc[i, 'age'] < 73:
            self.df.loc[i, 'brokerage_withdrawal'] = self.df.loc[i - 1, 'brokerage_withdrawal'] * 1.04
    self.df['brokerage'] = self.df['brokerage'].round(2)
    
def set_ssa(self):
    self.df['social_security_income'] = 0.00
    self.df.loc[self.df['date'].dt.year > 2040, 'social_security_income'] = 51132.00

def set_total_income(self):    
    self.df['total_income'] = self.df.iloc[:, 5:9].sum(axis=1)

def set_standard_deduction(self):
    self.df['standard_deduction'] = 0  # Initialize column with zeros or starting value
    self.df.at[0, 'standard_deduction'] = 30368.00  # Replace `initial_value` with your starting amount
    for i in range(1, len(self.df)):
        self.df.at[i, 'standard_deduction'] = self.df.at[i - 1, 'standard_deduction'] * 1.04

def set_tax(self):
    #=(J3-K3-(1+REGEXEXTRACT($L$2, "\d+"))*1.05)*0.1
    for i in range(len(self.df)):
        self.df.at[i, 'tax'] = (self.df.at[i, 'total_income'] - self.df.at[i, 'standard_deduction'] - 89300*1.05) * 0.1

def set_medicare_part_b(self):
    # Set initial value for Medicare Part B
    self.df.at[0, 'medicare_part_b'] = 18000.00
    # Apply 4% annual increase until Age 65
    for i in range(1, len(self.df)):
        if self.df.at[i, 'age'] != 65:
            self.df.at[i, 'medicare_part_b'] = self.df.at[i-1, 'medicare_part_b'] * 1.04
        else:
            self.df.at[i, 'medicare_part_b'] = 500.00

def set_non_housing_expenses(self):
    self.df.at[0, 'non_housing_expenses'] = 40000.00
    for i in range(1, len(self.df)):
        self.df.at[i, 'non_housing_expenses'] = self.df.at[i - 1, 'non_housing_expenses'] * 1.04

def set_rent(self):
    self.df.at[0, 'rent'] = 72000.00
    for i in range(1, len(self.df)):
        self.df.at[i, 'rent'] = self.df.at[i - 1, 'rent'] * 1.04

def set_total_expenses(self):
    self.df['total_expenses'] = self.df.iloc[:, 11:17].sum(axis=1)
    self.df['total_expenses'] = self.df['total_expenses'].round(2)

def set_surplus_deficit(self):
    self.df['surplus_deficit'] = self.df['total_income'] - self.df['total_expenses']
    self.df['surplus_deficit'] = self.df['surplus_deficit'].round(2)
     
def set_net_worth(self):
    self.df['net_worth'] = self.df['traditional_ira'] + self.df['roth_ira'] + self.df['brokerage'] + self.df['home_equity'] - self.df['total_expenses'] + self.df['surplus_deficit']
    self.df['net_worth'] = self.df['net_worth'].round(2)
