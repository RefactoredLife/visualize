import pandas as pd
import os

csv_file = 'app/data/transactions.csv'
df = pd.DataFrame()
if not os.path.exists(csv_file):
    exit(1)

df = pd.read_csv(csv_file, parse_dates=['Date'])
df['Running Balance'] = df['Running Balance'].str.replace('$','').str.replace(',','').str.replace('"','')
df['Account'] = df['Account'].fillna('cash').replace('', 'cash')
df['Account'] = df['Account'].str.lower()
# Sort the dataframe
df = df.sort_values(['Account', 'Date'])

# Group by Account and month, and pick the last record in each group
df['YearMonth'] = df['Date'].dt.to_period('M')

#result_df = df.groupby(['Account', 'YearMonth']).tail(1).copy()
result_df = df.groupby(['YearMonth']).tail(1).copy()

result_df = result_df[['Date', 'Account', 'Running Balance']]
result_df.columns = ['Date','Account','Balance']
result_df = result_df.sort_values(['Date']).reset_index(drop=True)
result_df = result_df[result_df['Date'].dt.year <= 2016]


balances_df = pd.read_csv('/finance/processed/balances.csv', parse_dates=['Date'])

result_df = pd.concat([result_df, balances_df], ignore_index=True)
result_df = result_df.sort_values(['Date']).reset_index(drop=True)

result_df.to_csv('/finance/processed/all_balances.csv', index=False)
