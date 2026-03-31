import pandas as pd
import os
import yfinance as yf
from yfinance.exceptions import YFPricesMissingError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pickle
from app.modules.Valuation import Valuation
import pandas as pd
from datetime import datetime, timedelta, date
from app.common.config import WATCHLIST_PATH, CACHE_PATH

def is_before_today_excluding_weekends(ts: pd.Timestamp) -> bool:
    ts1 = ts.replace(hour=13, minute=00, second=0)
    ts2 = pd.Timestamp.now()

    # If today is Saturday or Sunday, roll back to the last Friday
    if ts2.weekday() == 5:  # Saturday
        ts2 -= pd.Timedelta(days=1)
    elif ts2.weekday() == 6:  # Sunday
        ts2 -= pd.Timedelta(days=2)
    
    # Check if the difference is at least 24 hours
    if ts2 - ts1 >= pd.Timedelta(hours=24):
        return True
    else:
        return False

def merge_tickers_to_csv():
    all_tickers = set()
    output_file = f"{WATCHLIST_PATH}/tickers.csv"
    
    # Iterate over all files in the root directory
    for file_name in os.listdir(WATCHLIST_PATH):
        if file_name.endswith('.csv'):
            file_path = os.path.join(WATCHLIST_PATH, file_name)
            df = pd.read_csv(file_path)
            if 'ticker' in df.columns:
                tickers = df['ticker'].tolist()
                all_tickers.update(tickers)
    
    # Convert the set of tickers to a DataFrame
    merged_df = pd.DataFrame(list(all_tickers), columns=['ticker'])
    
    # Write the merged DataFrame to a new CSV file
    merged_df.to_csv(output_file, index=False)
    print(f"Merged tickers saved to {output_file}")

def save_to_disk(data, filename):
    with open(filename, 'wb') as f:
        pickle.dump(data, f)

def load_from_disk(filename):
    with open(filename, 'rb') as f:
        return pickle.load(f)

def days_in_previous_month():
    today = datetime.today()
    first_day_this_month = today.replace(day=1)
    last_day_last_month = first_day_this_month - relativedelta(days=1)
    return last_day_last_month.day - 1

def get_tickers_from_csv(file_path):
    df = pd.read_csv(file_path)
    return df['ticker'].tolist()

def is_metadata_stale(file_path, days=7):
    if not os.path.exists(file_path):
        return True
    last_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
    return (datetime.now() - last_modified_time).days > days

# To match the Yahoo stock quotes for last 1M
def get_start_date(end_date):
    try:
        start_date = date(end_date.year, end_date.month -1, end_date.day)
    except:
        try:
            start_date = date(end_date.year, end_date.month -1, end_date.day-1)
        except:
            try:
                start_date = date(end_date.year, end_date.month -1, end_date.day-2)
            except:
                start_date = date(end_date.year, end_date.month -1, end_date.day-3)
    return start_date

def check_price_drop(tickers, drop_percentage): #, delta):
    end_date = datetime.today() + timedelta(days=1)
    start_date = get_start_date(end_date)
    invalid_tickers = get_tickers_from_csv(f'{WATCHLIST_PATH}/invalid.csv')
    
    print(f"Checking price drop for tickers from {start_date} to {end_date}")

    tickers_dropped = []

    # Loop through tickers and download data incrementally
    for ticker in tickers: 
        if ticker in invalid_tickers:
            continue
        stock_data_file = f"{CACHE_PATH}/{ticker}_stock_data.pkl"
        stock_info_file = f"{CACHE_PATH}/{ticker}_stock_info.pkl"
        
        # Check if cached data exists
        if os.path.exists(stock_data_file):
            stock_data = load_from_disk(stock_data_file)
            last_date = pd.to_datetime(stock_data.index).max()
            incremental_update = is_before_today_excluding_weekends(last_date)
            if incremental_update:  # Only fetch if there's new data to download
                print(f'Downloading incremental data for {ticker}')
                new_start_date = last_date + timedelta(days=1)
                try:
                    new_stock_data = yf.download(ticker, start=new_start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
                    stock_data = pd.concat([stock_data, new_stock_data])
                    save_to_disk(stock_data, stock_data_file)
                except YFPricesMissingError as yfpme:
                    print(yfpme)
                    invalid_tickers.append(ticker)
                except Exception as e:
                    print(f"Error downloading incremental data for {ticker}: {e}")
        else:
            try:
                print(f'Downloading initial data for {ticker}')
                stock_data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
                save_to_disk(stock_data, stock_data_file)
            except Exception as e:
                print(f"Error downloading data for {ticker}: {e}")

        # Download stock info (refresh if stale or missing)
        if not os.path.exists(stock_info_file) or is_metadata_stale(stock_info_file, days=7):
            try:
                print(f'Downloading info for {ticker}')
                stock_info = yf.Ticker(ticker).info
                save_to_disk(stock_info, stock_info_file)
                print(f"Metadata for {ticker} updated.")
            except Exception as e:
                print(f"Error downloading stock info for {ticker}: {e}")
        else:
            stock_info = load_from_disk(stock_info_file)
            
            
        if stock_data.empty or len(stock_data['Close']) < 2:
            print(f"Not enough data for {ticker}")
            continue

        initial_price = stock_data['Close'].iloc[0]
        latest_price = stock_data['Close'].iloc[-1]

        if initial_price.empty or latest_price.empty:
            print(f"Missing price data for {ticker}")
            continue

        price_change = ((latest_price.iloc[0] - initial_price.iloc[0]) / initial_price.iloc[0]) * 100

        if price_change <= drop_percentage:
            dividend_yield = stock_info.get('dividendYield', 0)

            pe_ratio = stock_info.get('forwardPE', None)
            pe_ratio = round(pe_ratio, 2) if pe_ratio is not None else None

            growth_rate = stock_info.get('earningsGrowth', None)
            growth_rate = round(growth_rate, 2) if growth_rate is not None else 0.0

            margin = stock_info.get('profitMargins', None)
            margin = round(margin * 100, 2) if margin is not None else 0.0

            price_to_sales = stock_info.get('priceToSalesTrailing12Months', None)
            price_to_sales = round(price_to_sales, 2) if price_to_sales is not None else 0.0

            # Get sector and industry
            sector = stock_info.get('sector', None)
            industry = stock_info.get('industry', None)

            revenue_growth = None
            if 'revenueGrowth' in stock_info:
                revenue_growth = stock_info['revenueGrowth'] * 100  # Convert to percentage
                revenue_growth = round(revenue_growth, 2) if revenue_growth is not None else None

            peg_ratio = None
            if pe_ratio and growth_rate:
                peg_ratio = pe_ratio / (growth_rate * 100)  # Convert growth rate to percentage
                peg_ratio = round(peg_ratio, 2) if peg_ratio is not None else None

            v = Valuation(ticker, stock_data, stock_info)
            v.calculate_valuation()
            valuation = ""
            if v.get_valuation().get('name') == 'pe_ratio':
                if v.stock_info.get('sector') and v.stock_info.get('industry'):
                    valuation = v.valuate(v.get_valuation().get('value'), v.stock_info.get('sector').lower(), v.stock_info.get('industry').lower())
            tickers_dropped.append((ticker, round(price_change, 2), round(dividend_yield, 2), peg_ratio, pe_ratio, growth_rate, price_to_sales, round(margin, 2), revenue_growth, sector, industry, valuation))  
    fresh_invalid_tickers = pd.DataFrame(invalid_tickers, columns=['ticker'])
    fresh_invalid_tickers.to_csv(f'{WATCHLIST_PATH}/invalid.csv')
    return pd.DataFrame(tickers_dropped, columns=['ticker', 'change', 'dividend', 'peg', 'pe', 'earningsGrowth', 'priceToSales', 'margin', 'revenueGrowth', 'sector', 'industry', 'valuation'])


if __name__ == "__main__":
    #tickers = ['SPYG']
    #dropped_tickers = check_price_drop(tickers, 10)
    #exit()

    merge_tickers_to_csv()
    watchlists = ["tickers"]
    for watchlist in watchlists:
        tickers = get_tickers_from_csv(f"{WATCHLIST_PATH}/{watchlist}.csv")
        
        drop_percentage = 10
        #delta = days_in_previous_month()
        delta = 30

        dropped_tickers = check_price_drop(tickers, drop_percentage) #, delta)

        dropped_tickers.to_csv(f"{WATCHLIST_PATH}/screen_{watchlist}.csv", index=False)

        #if dropped_tickers:
            #print(f"\nTickers in {watchlist} dropped {drop_percentage}% or more in the past {delta} days")
            #dropped_tickers.sort(key=lambda x: x[6])
            #for ticker, change, dividend, peg, pe, growth, pts, margin in dropped_tickers:
            #    print(f"{ticker}::\t G/L:\t {change}%,\t Dividend Yield: {dividend}%,\t PEG: {peg},\t PE: {pe},\t Growth Rate: {growth}% \t Price to Sales: {pts}\t Profit Margin: {margin}")
        #else:
        #    print(f"No tickers in {watchlist} dropped {drop_percentage}% or more in the past {delta} days")