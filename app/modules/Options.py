import yfinance as yf
import numpy as np
import pandas as pd
import datetime
from scipy.stats import norm

def get_option_chain(ticker):
    stock = yf.Ticker(ticker)
    exp_dates = stock.options  # Get expiration dates
    option_data = []

    for exp in exp_dates[:3]:  # Limit to first 3 expirations
        opt_chain = stock.option_chain(exp)
        calls = opt_chain.calls
        puts = opt_chain.puts
        calls['Type'] = 'Call'
        puts['Type'] = 'Put'
        calls['Expiration'] = exp
        puts['Expiration'] = exp
        option_data.append(calls)
        option_data.append(puts)
    
    options_df = pd.concat(option_data)
    return options_df, exp_dates

def black_scholes_delta(S, K, T, r, sigma, option_type="call"):
    """Calculate Delta using Black-Scholes"""
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    if option_type == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1

def analyze_risk(ticker):
    stock = yf.Ticker(ticker)
    S = stock.history(period="1d")["Close"].iloc[-1]  # Get last closing price
    options_df, exp_dates = get_option_chain(ticker)
    
    r = 0.05  # Assume 5% risk-free rate
    options_df = options_df[['strike', 'lastPrice', 'impliedVolatility', 'Type', 'Expiration','inTheMoney']].dropna()
    
    options_df['impliedVolatility'] = options_df['impliedVolatility'].astype(float)
    
    today = datetime.date.today()
    options_df['daysToExp'] = options_df['Expiration'].apply(lambda x: (datetime.datetime.strptime(x, "%Y-%m-%d").date() - today).days)
    
    # Calculate Greeks
    options_df['delta'] = options_df.apply(lambda row: black_scholes_delta(
        S, row['strike'], row['daysToExp'] / 365, r, row['impliedVolatility'], row['Type'].lower()), axis=1)
    
    # Define Risk Scenarios
    scenarios = {
        "Market Up 5%": S * 1.05,
        "Market Down 5%": S * 0.95,
        "Volatility Up 10%": options_df['impliedVolatility'] * 1.1,
        "Volatility Down 10%": options_df['impliedVolatility'] * 0.9
    }
    
    risk_analysis = []
    for scenario, new_S in scenarios.items():
        temp_df = options_df.copy()
        temp_df['new_delta'] = temp_df.apply(lambda row: black_scholes_delta(
            new_S, row['strike'], row['daysToExp'] / 365, r, row['impliedVolatility'], row['Type'].lower()), axis=1)
        temp_df['scenario'] = scenario
        risk_analysis.append(temp_df)

    final_df = pd.concat(risk_analysis)
    # Filter out columns where expiration date is the last day of the week
    final_df = final_df[final_df['daysToExp'] % 7 != 0]
    # Filter out columns where type is Put
    final_df = final_df[final_df['Type'] == 'Put']
    # Filter out columns where delta is between -0.5 and -0.7
    final_df = final_df[(final_df['delta'] < -0.5)]
    final_df = final_df[(final_df['delta'] > -0.7)]

    # Ensure full dataframe is displayed
    pd.set_option('display.max_rows', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', None)

    import ace_tools_open as tools; tools.display_dataframe_to_user(name="Market Risk Analysis", dataframe=final_df)

# Example Usage
#ticker = input("Enter the stock ticker: ").upper()
ticker = "QQQ"
analyze_risk(ticker)