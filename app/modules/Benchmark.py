from app.common.config import *
from app.common.utils import read_csv
import pandas as pd

class Benchmark():
    def get_df(self):
        # Read and sort the SPY data
        spy = read_csv(SPY_CSV, SPY_HEADER)
        spy.sort_values(by=['Date'], inplace=True)

        # Read and sort the cashflow data
        cf = read_csv(CASHFLOW_CSV, CASHFLOW_HEADER)
        cf.sort_values(by=['Date'], inplace=True)

        bal = read_csv(BALANCES_CSV, BALANCES_HEADER)
        bal.sort_values(by=['Date'], inplace=True)
        self.bal = bal.groupby('Date').agg({
            'Balance': 'sum'
        })

        # Merge the two DataFrames based on the Date field
        merged_df = pd.merge(cf, spy, on='Date', how='inner')

        # Calculate SPY Shares
        merged_df['SPY Shares'] = merged_df['Amount'] / merged_df['Close']

        # Calculate cumulative SPY Shares
        merged_df['Cumulative SPY Shares'] = merged_df['SPY Shares'].cumsum()

        merged_df['SPY Market Value'] = merged_df['Close'] * merged_df['Cumulative SPY Shares']

        merged_df = pd.merge(merged_df, self.bal, on='Date', how='inner')

        # Save the merged DataFrame to a new CSV file (optional)
        merged_df.to_csv(BENCHMARK_CSV, index=False)
        return merged_df

if __name__ == '__main__':
    benchmark = Benchmark()
    print(benchmark.get_df())
