from app.common.config import *
from app.common.utils import read_csv, log_runtime
import pandas as pd
import datetime
import scipy.optimize
import re
from scipy.optimize import curve_fit
import numpy as np
import requests


class Financials():
    @log_runtime
    def __init__(self):
        self.cashflow = read_csv(CASHFLOW_CSV, CASHFLOW_HEADER)
        self.sbs_dioi = read_csv(SBS_DIOI_CSV, SBS_DIOI_HEADER)
        self.spy_max_from_perplexity_df = read_csv(SPY_MAX_FROM_PERPLEXITY_CSV, SPY_MAX_FROM_PERPLEXITY_HEADER)
        self.holdings_df = read_csv(HOLDINGS_CSV, HOLDINGS_HEADER)
        self.holdings_history_df = read_csv(HOLDINGS_HISTORY_CSV, HOLDINGS_HEADER)
        self.balances = read_csv(BALANCES_CSV, BALANCES_HEADER)
        self.current_balances = read_csv(CURRENT_BALANCES_CSV, BALANCES_HEADER)
        self.cash_df = read_csv(CASH_CSV, CASH_HEADER)
        
    def train_model(self,months_to_project):
        df = self.balances.copy()

        # Add current balances to the DataFrame
        accounts = df['Account'].unique()
        df2 = self.get_current_balances([key.lower() for key in accounts])

        external_accounts = df[(df['Account'].isin(['external_asset_1', 'external_asset_2', 'external_ira'])) & (df['Date'] == df['Date'].max())]
        external_accounts = external_accounts.copy()
        external_accounts['Date'] = pd.to_datetime('today').normalize()
        df2['Date'] = pd.to_datetime('today').normalize()
        df2 = pd.concat([df2, external_accounts], ignore_index=True)
        df = pd.concat([df, df2], ignore_index=True)
        df['Date'] = pd.to_datetime(df['Date'])
        df_total = df.groupby('Date')['Balance'].sum().reset_index()
        df_total = df_total.sort_values('Date')
        current_balances = df_total.copy()
        df_total['Months'] = ((df_total['Date'] - df_total['Date'].min()) / np.timedelta64(30, 'D')).astype(int)

        # Define exponential growth model
        def exponential_model(x, a, b, c):
            return a * np.exp(b * x) + c

        # Fit the exponential model
        x_data = df_total['Months'].values
        y_data = df_total['Balance'].values
        params, _ = curve_fit(exponential_model, x_data, y_data, p0=(1, 0.01, 1), maxfev=5000)

        # Generate future months and dates
        last_month = df_total['Months'].max()
        future_months = np.arange(last_month + 1, last_month + 1 + months_to_project)
        future_dates = pd.date_range(start=df_total['Date'].max() + pd.DateOffset(months=1),
                                    periods=months_to_project, freq='ME')
        

        # Make predictions
        exp_predictions = exponential_model(future_months, *params)

        # Combine into a DataFrame
        projection_df = pd.DataFrame({
            'Date': future_dates,
            'Balance': exp_predictions
        })
        projection_df = pd.concat([current_balances, projection_df])
        return projection_df

    def get_holdings_by_ticker(self):
        holdings_df = self.holdings_df.copy()
        holdings_by_ticker_df = holdings_df.groupby('Description').agg({
            'Beginning_Market_Value': 'sum',
            'Quantity': 'sum',
            'Price_Per_Unit': 'mean',
            'Ending_Market_Value': 'sum',
            'Total_Cost_Basis': 'sum',
            'Unrealized_Gain/Loss': 'sum',
            #'Account': 'sum'
        }).reset_index()
        return holdings_by_ticker_df
    
    def get_current_balances(self, accounts):
        holdings_df = self.holdings_df.groupby('Account')['Ending_Market_Value'].sum().reset_index()
        cash_df = self.cash_df.groupby('Account')['Ending_Market_Value'].sum().reset_index()
        merged_df = pd.merge(holdings_df, cash_df, on='Account', how='outer')
        merged_df.fillna(0, inplace=True)
        merged_df['Balance'] = merged_df['Ending_Market_Value_x'] + merged_df['Ending_Market_Value_y']
        return merged_df[['Account', 'Balance']]

        #balances = self.balances.copy()
        #latest_balances = balances.groupby('Account')['Date'].max().reset_index()
        #current_balances = balances[balances['Date'] == latest_balances['Date'].max()]
        #current_balances.drop(columns=['Date'], inplace=True)
        #current_balances = current_balances[current_balances['Account'].isin(accounts)]
        #return current_balances

    def calculate_gain_loss(self):
        holdings_df = self.holdings_df.copy()

        # Calculate gain/loss for each account
        holdings_df['Unrealized_Gain/Loss'] = holdings_df['Ending_Market_Value'] - holdings_df['Total_Cost_Basis']

        # Group by account and sum the gain/loss
        gain_loss_df = holdings_df.groupby('Account')['Unrealized_Gain/Loss'].sum().reset_index()
        gain_loss_df.columns = ['Account', 'Amount']

        gain_loss_df.to_csv(GAIN_LOSS_CSV, index=False)

        return gain_loss_df

    #def calculate_net_worth(self):
    #    current_balances = self.current_balances.copy()
    #    net_worth = current_balances['Balance'].sum()
    #    return net_worth

    #@log_runtime
    #def get_net_worth_in(self, year):
    #    df = self.balances.copy()
    #    df['Date'] = pd.to_datetime(df['Date'])
    #    df_year = df[df['Date'].dt.year == year]
    #    if df_year.empty:
    #        return 0
    #    latest_date = df_year['Date'].max()
    #    latest_df = df_year[df_year['Date'] == latest_date]
    #    total_balance = latest_df['Balance'].sum()
    #    return total_balance

    #@log_runtime
    #def get_current_net_worth(self):
    #    print("Triggering recalculation of networth/Holdings sheet...")
    #    gc = GoogleSheetConnector()
    #    gc.trigger_recalculation()
    #    df = gc.read_sheet('Holdings')
    #    Ending_Market_Value = df['Ending_Market_Value'].astype(float).sum()

    #    external_accounts_sum = self.balances[(self.balances['Date'] == self.balances['Date'].max()) & (self.balances['Account'].isin(['external_asset_0', 'external_asset_1', 'external_ira']))]['Balance'].sum()

    #    ethers = self.get_crypto('ethereum', 1)
    #    net_worth = Ending_Market_Value + self.cash_df['Ending_Market_Value'].astype(float).sum() + external_accounts_sum + (5/ethers) # 5 ethereum tokens
    #    return net_worth

    def trigger_recalculation():
        response = requests.get(HOLDINGS_WEB_APP_URL)
        if response.status_code == 200:
            print("Recalculation triggered successfully.")
        else:
            print(f"Failed to trigger recalculation: {response.status_code}")

    def get_crypto(self, name, amound_usd):
        try:
            url = f'https://api.coingecko.com/api/v3/simple/price?ids={name}&vs_currencies=usd'
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return amound_usd / data[f'{name}']['usd']
        except Exception as e:
            print(f"Error fetching crypto/{name} price: {e}")
            return 1.0

    def get_kg_of_gold(self, amount_usd):
        price_per_ounce = 3256.0  # Example price per ounce in USD
        grams_per_ounce = 31.1035
        grams_per_kilogram = 1000
        price_per_gram = price_per_ounce / grams_per_ounce
        price_per_kilogram = price_per_gram * grams_per_kilogram
        kilograms = amount_usd / price_per_kilogram
        return kilograms
    
    def calculate_monthly_cash_flow(self):
        cashflow = self.cashflow.copy()
        cashflow['Month'] = cashflow['Date'].dt.to_period('M')
        monthly_cash_flow = cashflow.groupby('Month')['Amount'].sum().reset_index()
        monthly_cash_flow.columns = ['Month', 'Cash Flow']
        return monthly_cash_flow

    def calculate_investment_performance(self):
        holdings_df = self.holdings_df.copy()
        holdings_df['Performance'] = (holdings_df['Ending_Market_Value'] - holdings_df['Total_Cost_Basis']) / holdings_df['Total_Cost_Basis']
        investment_performance = holdings_df.groupby('Account')['Performance'].mean().reset_index()
        investment_performance.columns = ['Account', 'Performance']
        return investment_performance


    def calculate_amount_invested(self):
        holdings_df = self.holdings_df.copy()
        amount_invested_df = holdings_df.groupby('Account')['Ending_Market_Value'].sum().reset_index()
        amount_invested_df.columns = ['Account', 'Amount']
        return amount_invested_df


    def calculate_dividends_and_interest(self):
        sbs_dioi = self.sbs_dioi.copy()
        # Filter rows with 'Dividends' or 'Interest' in Description
        df = sbs_dioi[sbs_dioi['Description'].str.contains('Dividend|Interest', case=False, na=False)]
        df['Year'] = df['Date'].dt.year
        df.to_csv(DIVIDENDS_INTEREST_CSV, index=False, mode='w', header=True)
        df = df.groupby('Year').agg({
            "Amount": "sum"
        })
        df['Year'] = df.index
        return df

    def calculate_capital_gain_loss(self):
        sbs_dioi = self.sbs_dioi.copy()
        df = sbs_dioi[sbs_dioi['Description'].str.contains('Bought|Sold', case=False, na=False)]
        df['Year'] = df['Date'].dt.year
        df.to_csv(STOCK_TRANSACTIONS_CSV, index=False, mode='w', header=True)
        df = df.groupby('Year').agg({
            "Amount": "sum"
        })
        df['Year'] = df.index
        return df

    def get_realized_gain(self, account, year):
        df = self.sbs_dioi.copy()
        # Filter the DataFrame
        df['Gain/Loss'] = df['Amount'] - df['Total_Cost_Basis']
        filtered_df = df[(df['Account'].str.lower() == account) & 
                        (df['Description'].str.contains('Sold', case=False, na=False)) &
                        (df['Date'].dt.year == year)]

        # Calculate the sum of the 'Amount' column
        total_sum = filtered_df['Gain/Loss'].sum()
        return total_sum

    def xnpv(self, rate, values, dates):
        '''Equivalent of Excel's XNPV function.

        >>> from datetime import date
        >>> dates = [date(2010, 12, 29), date(2012, 1, 25), date(2012, 3, 8)]
        >>> values = [-10000, 20, 10100]
        >>> xnpv(0.1, values, dates)
        -966.4345...
        '''
        if rate <= -1.0:
            return float('inf')
        d0 = datetime.datetime.strptime(dates[0], '%Y-%m-%d')  # or min(dates)
        x = zip(values, dates)
        return sum([vi / (1.0 + rate) ** ((datetime.datetime.strptime(di, '%Y-%m-%d') - d0 ).days / 365.0) for vi, di in x ])

    def xirr(self, values, dates):
        '''Equivalent of Excel's XIRR function.

        >>> from datetime import date
        >>> dates = [date(2010, 12, 29), date(2012, 1, 25), date(2012, 3, 8)]
        >>> values = [-10000, 20, 10100]
        >>> xirr(values, dates)
        0.0100612...
        '''
        try:
            return scipy.optimize.newton(lambda r: self.xnpv(r, values, dates), 0.0)
        except RuntimeError:  # Failed to converge?
            return scipy.optimize.brentq(lambda r: self.xnpv(r, values, dates), -1.0, 1e10)
        
    def calculate_xirr(self, account):
        cashflow = self.cashflow.copy()
        cashflow = cashflow[cashflow['Account'] == account.lower()]
        cashflow = cashflow.drop(columns=['Account'])

        balances = self.balances.copy()
        balances = balances[balances['Account'] == account.lower()]
        balances = balances.drop(columns=['Account'])
        balances = balances.rename(columns={'Balance': 'Amount'})

        # Get the first row of the balances dataframe
        etd_balances = balances.iloc[0:1]
        # Get the last row of the cashflow dataframe
        latest_balance = balances.iloc[-1:]

        # So that we don't get a SettingsWithCopyWarning
        latest_balance = latest_balance.copy()

        latest_balance['Amount'] = -latest_balance['Amount']

        df = pd.concat([etd_balances, cashflow, latest_balance], ignore_index=True)

        # sort by date
        df['Date'] = pd.to_datetime(df['Date'])
        # return date column as a list
        dates, values = df['Date'].tolist(), df['Amount'].tolist()
        # Convert date to a string
        dates = [datetime.datetime.strftime(date, '%Y-%m-%d') for date in dates]
        irr = self.xirr(values, dates) * 100
        return irr

if __name__ == '__main__':
    financials = Financials()
    x = financials.get_crypto('ethereum', 1000000)
    print(1000000 / x)
    exit()
    nw = financials.get_current_net_worth()
    df = financials.holdings_df["Unrealized_Gain/Loss"].sum()
    print(df)
    #print(financials.get_crypto('bitcoin',1000))

    holdings_dict = financials.get_holdings_by('all')
    #holdings_dict = financials.get_holdings_by('Growth')
    holdings_dict.sort_values(by=['Value'], ascending=False, inplace=True)
    print(holdings_dict)
    exit()

    print(financials.calculate_dividends_and_interest())

    current_balances = financials.get_current_balances()
    current_balances.to_csv(CURRENT_BALANCES_CSV, index=False, mode='w', header=True)
    
    gain_loss_df = financials.calculate_gain_loss()
    print(gain_loss_df)

    #net_worth = financials.calculate_net_worth()
    #print(f'Net Worth: {net_worth}')

    monthly_cash_flow = financials.calculate_monthly_cash_flow()
    print(monthly_cash_flow)

    investment_performance = financials.calculate_investment_performance()
    print(investment_performance)

    amount_invested_df = financials.calculate_amount_invested()
    print(amount_invested_df)
