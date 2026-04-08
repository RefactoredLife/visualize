import pandas as pd
from typing import Any, Dict, Optional, Iterable
import io
from app.common.config import HOLDINGS_CSV, HOLDINGS_HEADER, FASTAPI_BASE_URL, MERCHANT_CATEGORY_CSV, MARIADB_DATABASE, MARIADB_PASSWORD, MARIADB_PORT, MARIADB_USER, MARIADB_HOST
from app.modules.GoogleSheets import GoogleSheetConnector
import requests
import time
import logging
import os
from datetime import datetime, timezone
from app.common.config import get_secret, STATEMENT_START_DATE, BALANCES_CSV, BALANCES_HEADER
from fuzzywuzzy import process
import re
import hashlib
import numpy as np
from pymongo.errors import BulkWriteError
from cachetools import TTLCache, cached
import yfinance as yf
import streamlit as st
from sqlalchemy import create_engine, text
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s [%(levelname)s] %(message)s")
#SECRET_CACHE_BASE_URL = os.getenv("SECRET_CACHE_BASE_URL")

def use_modern_fonts():
    st.markdown("""
    <style>
      /* Import Google Fonts */
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Work+Sans:wght@600;700&display=swap');

      /* Global font stack */
      html, body, [class*="css"] {
        font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, 'Noto Sans', 'Liberation Sans', sans-serif !important;
      }

      /* Headings use Work Sans */
      h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Work Sans', 'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, sans-serif !important;
        font-weight: 700;
        letter-spacing: -0.015em;
      }

      /* Tighten subheadings slightly */
      h4, h5, h6 {
        font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, sans-serif !important;
        font-weight: 600;
      }

      /* Inputs/buttons/tabs (just to be explicit) */
      .stButton > button,
      .stTextInput input,
      .stSelectbox div,
      .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, sans-serif !important;
      }
    </style>
    """, unsafe_allow_html=True)

def clean_numeric(x):
    if pd.isna(x) or x == 'unavailable' or x == '-':
        return 0.0
    return_value = float(
        str(x).replace('$', '')
              .replace('%', '')
              .replace(',', '')
              .replace('f','')
              .strip()
    )
    return round(return_value, 3)

def make_dedup_key(record):
    # Convert Date to YYYY-MM-DD string for consistency
    if isinstance(record['Date'], str):
        date_str = record['Date']
    elif hasattr(record['Date'], 'strftime'):
        date_str = record['Date'].strftime('%Y-%m-%d')
    else:
        date_str = str(record['Date'])  # fallback

    # Normalize description
    description = record.get('Description', '').strip().lower()

    # Format amount consistently
    amount = float(record.get('Amount', 0.0))

    key_str = f"{date_str}_{description}_{amount:.2f}"
    return hashlib.sha256(key_str.encode('utf-8')).hexdigest()

def backfil_dedup_key(collection):
    batch_size = 500
    cursor = collection.find({"dedup_key": {"$exists": False}})

    count = 0
    for doc in cursor:
        try:
            dedup_key = make_dedup_key(doc)
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"dedup_key": dedup_key}}
            )
            count += 1
            if count % batch_size == 0:
                print(f"Updated {count} documents...")
        except Exception as e:
            print(f"Error updating _id={doc['_id']}: {e}")

    print(f"✅ Finished updating {count} documents.")

def create_index(collection):
    collection.create_index("dedup_key", unique=True)

def save_to_mongo(df, collection):
    df = df.fillna("")

    # Convert DataFrame to list of dicts
    data = df.to_dict(orient='records')

    # Add dedup_key to each record
    df['Amount'] = -df['Amount']
    for record in data:
        record['dedup_key'] = make_dedup_key(record)
    df['Amount'] = -df['Amount']

    # Insert all records
    try:
        collection.insert_many(data, ordered=False)
    except BulkWriteError as bwe:
        for error in bwe.details['writeErrors']:
            logging.debug(f"Skipped duplicate: {error['keyValue']}")
        logging.info(f"Inserted {bwe.details['nInserted']} documents. Skipped {len(bwe.details['writeErrors'])} duplicates.")
    except Exception as e:
        print(f"Insert error (likely due to duplicates): {e}")
                
def deduplicate(collection):
    # Step 1: Group by fields to find duplicates
    pipeline = [
        {
            "$addFields": {
                "_normalizedDate": {
                    "$cond": [
                        { "$eq": [{ "$type": "$Date" }, "date"] },
                        { "$dateToString": { "format": "%Y-%m-%d", "date": "$Date" } },
                        "$Date"  # leave as-is if already a string
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": {
                    "Date": "$_normalizedDate",
                    "Description": "$Description",
                    "Amount": "$Amount"
                },
                "ids": {"$addToSet": "$_id"},
                "count": {"$sum": 1}
            }
        },
        {
            "$match": {
                "count": {"$gt": 1}
            }
        }
    ]

    duplicates = list(collection.aggregate(pipeline))

    # Step 2: Remove all but one document from each group
    to_delete = []

    for group in duplicates:
        ids = group['ids']
        ids_to_remove = ids[1:]  # Keep the first, remove the rest
        to_delete.extend(ids_to_remove)

    if to_delete:
        result = collection.delete_many({"_id": {"$in": to_delete}})
        print(f"Deleted {result.deleted_count} duplicate documents.")
    else:
        print("No duplicates found.")

def normalize_date(collection):
    cursor = collection.find({"Date": {"$type": "string"}})

    updated_count = 0

    for doc in cursor:
        date_str = doc['Date']
        try:
            # Convert string to datetime object
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Update the document with the normalized date
            collection.update_one(
                {"_id": doc["_id"]},
                {"$set": {"Date": date_obj}}
            )
            updated_count += 1
        except ValueError:
            print(f"Skipping invalid date string: {date_str}")

    print(f"Normalized {updated_count} Date fields to ISODate format.")
            
def get_category(merchant):
    cat_df = pd.read_csv(MERCHANT_CATEGORY_CSV)
    cat_df = cat_df.set_index('merchant')
    sub_merchant_list = merchant.split(' ')
    if len(sub_merchant_list) > 1:
        sub_merchant = '{} {}'.format(sub_merchant_list[0], sub_merchant_list[1])
    else:
        sub_merchant = sub_merchant_list[0]
    merchant_list = cat_df.index.values.tolist()
    choice = process.extractOne(sub_merchant, merchant_list)
    # print(self.cat_df['category'][choice[0]])
    return cat_df['category'][choice[0]]

def call_api(
    endpoint: str,
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    Generic helper to call your own FastAPI endpoints.

    Args:
        endpoint: API path (e.g. /process)
        method: HTTP method (GET, POST, PUT, DELETE)
        params: Query parameters (for GET)
        json: JSON body (for POST/PUT)
        headers: Optional headers (e.g. auth tokens)
        timeout: Request timeout in seconds

    Returns:
        JSON-decoded response as a dict
    """
    url = f"{FASTAPI_BASE_URL}/{endpoint.lstrip('/')}"
    method = method.upper()
    headers = headers or {}
    #api_key = requests.get(f"{SECRET_CACHE_BASE_URL}/visualize/MY_API_KEY")
    api_key = get_secret("/visualize/MY_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    try:
        response = requests.request(
            method,
            url,
            params=params,
            json=json,
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        logging.info(f"API call to {url} Here is what I'm sending out: {response.request.headers}, {response.request.method}, {response.request.url}")
        return response.json() if response.content else {}
    except requests.exceptions.JSONDecodeError:
        logging.error(f"API call to {url} returned non-JSON response. Status: {response.status_code}. Body: {response.text[:200]}")
        return {"error": "Invalid JSON response from server", "status_code": response.status_code}
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', None)
        logging.error(f"API call to {url} failed with status {status_code}: {e}")
        return {"error": str(e), "status_code": status_code}
    
def log_runtime(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        logging.info(f"Method {func.__name__} took {end_time - start_time:.4f} seconds")
        return result
    return wrapper

class LazyDataFrame:
    def __init__(self, csv_file, csv_header):
        self.csv_file = csv_file
        self.csv_header = csv_header
        self._df = None

    def get(self):
        if self._df is None or self._df.empty:
            logging.info(f"{self.csv_file} is not initialized, initializing...")
            self._df = read_csv(self.csv_file, self.csv_header)
        elif self.csv_file == HOLDINGS_CSV:
            logging.info(f"Holdings file {self.csv_file}, therefore reinitializing...")
            self._df = read_csv(self.csv_file, self.csv_header)
        else:
            logging.info(f"Loading CSV file {self.csv_file} from memory...")
        return self._df
    
    def set(self, df):
        self._df = df

@st.cache_data(ttl=600)  # cache for 10 minutes
def load_google_holdings(sheet_name):
    gc = GoogleSheetConnector()
    return gc.read_sheet(sheet_name)

# Memory caching
cache = TTLCache(maxsize=32, ttl=1200)  # 20 minutes
@cached(cache)
def fetch_day_gains_from_yahoo(tickers: Iterable[str]):
    # Ensure tickers is a tuple for caching
    if isinstance(tickers, list):
        tickers = tuple(tickers)
    if not tickers:
        return pd.DataFrame(columns=["prev_close", "last_close", "change", "pct_change"])        

    logging.info('Downloading quotes from yahoo...')
    df = yf.download(tickers, period="2d")
    closes = df["Close"]   # <--- pick only the "Close" slice
    
    # Previous vs Last
    prev = closes.iloc[0]
    last = closes.iloc[1]
    change = last - prev
    pct_change = (change / prev) * 100

    # Assemble results
    day_gains = pd.DataFrame({
        "prev_close": prev.round(2),
        "last_close": last.round(2),
        "change": change.round(2),
        "pct_change": pct_change.round(2)
    })
    day_gains.index.name = "Ticker"
    return day_gains


def _to_stooq_symbol(ticker: str) -> str:
    """Map a US ticker to Stooq symbol format.

    Examples:
    - AAPL -> aapl.us
    - BRK.B -> brk-b.us
    - GOOG -> goog.us
    """
    sym = ticker.strip().lower()
    sym = sym.replace(".", "-")
    if not sym.endswith(".us"):
        sym = f"{sym}.us"
    return sym


@st.cache_data(ttl=86400)  # cache for 24 hours (once per day)
def fetch_day_gains_from_stooq(tickers: Iterable[str]) -> pd.DataFrame:
    """Fetch last two daily closes from Stooq and compute day change.

    Uses one request per symbol to https://stooq.com historical daily CSV.
    Returns a DataFrame indexed by original ticker with columns:
    prev_close, last_close, change, pct_change
    """
    if isinstance(tickers, (list, tuple, set)):
        tickers = list(tickers)
    else:
        tickers = [tickers]

    rows = {}
    for t in tickers:
        sym = _to_stooq_symbol(str(t))
        url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            if df.empty or len(df) < 2:
                continue
            prev = float(df.iloc[-2]["Close"])  # previous trading day close
            last = float(df.iloc[-1]["Close"])  # most recent trading day close
            change = last - prev
            pct_change = (change / prev) * 100 if prev else 0.0
            rows[str(t)] = {
                "prev_close": round(prev, 2),
                "last_close": round(last, 2),
                "change": round(change, 2),
                "pct_change": round(pct_change, 2),
            }
        except Exception as e:
            logging.debug(f"Stooq fetch failed for {t}: {e}")
            continue

    if not rows:
        return pd.DataFrame(columns=["prev_close", "last_close", "change", "pct_change"]).astype({})
    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "Ticker"
    return df


def fetch_day_gains(tickers: Iterable[str]) -> pd.DataFrame:
    """Provider-agnostic daily change with caching.

    - First tries Stooq (free, no key), cached for 24h via Streamlit.
    - Falls back to Yahoo if needed (short TTL cache above).
    """
    stooq_df = fetch_day_gains_from_stooq(tickers)
    try:
        if stooq_df is not None and not stooq_df.empty:
            return stooq_df
    except Exception:
        pass
    # Fallback to Yahoo
    return fetch_day_gains_from_yahoo(tuple(tickers if isinstance(tickers, (list, tuple, set)) else [tickers]))

def load_yahoo_holdings(csv_file):
    logging.info(f"Loading holdings from Yahoo CSV file: {csv_file}")
    df = pd.read_csv(csv_file)
    df['Ticker'] = df['Description'].apply(lambda x: x.split('(')[-1].split(')')[0])
    tickers = df['Ticker'].tolist()
    quotes_df = fetch_day_gains(tuple(tickers))
    df = df.merge(
        quotes_df[["change"]].reset_index(),  # bring Ticker out of index
        on="Ticker",
        how="left"
    ).rename(columns={"change": "Day_Change"})
    df['Day_Gain'] = df['Quantity'] * df['Day_Change']
    return df

def prep_month_df(df: pd.DataFrame, user_id: str) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out["user_id"] = user_id

    # Normalize dates and amounts
    if 'Date' in out.columns:
        out["Date"] = pd.to_datetime(out["Date"]).dt.date
        # Derive month key as *first day of month* (DATE)
        period = pd.to_datetime(out["Date"]).dt.to_period("M").dt.to_timestamp("D", "start").dt.date
        out["period_ym"] = period
    #if 'Amount' in out.columns:
    #    out["Amount"] = out["Amount"].apply(clean_numeric)
    #if 'Beginning_Market_Value' in out.columns:
    #    out["Beginning_Market_Value"] = out["Beginning_Market_Value"].apply(clean_numeric)
    #if 'Quantity' in out.columns:
    #    out["Quantity"] = out["Quantity"].apply(clean_numeric)
    #if 'Unrealized_Gain/Loss' in out.columns:
    #    out["Unrealized_Gain/Loss"] = out["Unrealized_Gain/Loss"].apply(clean_numeric)
    #if 'Price_Per_Unit' in out.columns:
    #    out["Price_Per_Unit"] = out["Price_Per_Unit"].apply(clean_numeric)
    #if 'Ending_Market_Value' in out.columns:
    #    out["Ending_Market_Value"] = out["Ending_Market_Value"].apply(clean_numeric)
    #if 'Total_Cost_Basis' in out.columns:
    #    out["Total_Cost_Basis"] = out["Total_Cost_Basis"].apply(clean_numeric)
    
    for header in HOLDINGS_HEADER: 
        if header not in ["Description","Account"] and header in out.columns:
            out[header] = out[header].apply(clean_numeric)
    if 'Day_Gain' in out.columns:
        out['Day_Gain'] = out['Day_Gain'].apply(clean_numeric)
    if 'Day_Change' in out.columns:
        out['Day_Change'] = out['Day_Change'].apply(clean_numeric)

    return out
        
def load_holdings_sql(user_id):
    engine = create_engine(f"mysql+pymysql://{MARIADB_USER}:{MARIADB_PASSWORD}@{MARIADB_HOST}:{MARIADB_PORT}/{MARIADB_DATABASE}")
    logging.info(f"Loading holdings from SQL database...")
    with engine.begin() as conn:
        last_updated = conn.execute(
            text(
                """
                SELECT UPDATE_TIME
                FROM information_schema.tables
                WHERE `TABLE_SCHEMA`=:schema AND `TABLE_NAME`=:table
                """
            ),
            {"schema": MARIADB_DATABASE, "table": "holdings"}
        ).scalar()
        logging.info(f"Last updated: {last_updated}")
        # read_sql_table reflects columns and can mis-handle % in column names
        df = pd.read_sql_query("SELECT * FROM holdings_view", conn)

    if last_updated is not None:
        if not isinstance(last_updated, datetime):
            last_updated = pd.to_datetime(last_updated)
            if hasattr(last_updated, "to_pydatetime"):
                last_updated = last_updated.to_pydatetime()

        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now(tz=last_updated.tzinfo)

        elapsed_minutes = (now - last_updated).total_seconds() / 60
        logging.info(f"Minutes since last update: {elapsed_minutes}")

        # Following will not work because holdings table is updated in two steps. 
        # Second step to update Day Gain which will always be done in less than 20 min 
        if (not df.empty) and 'Day_Gain' in df.columns and elapsed_minutes < 1:
            logging.info(
                "Holdings table updated %.2f minutes ago; skipping refresh.",
                elapsed_minutes
            )
            return

    tickers = df['Ticker'].tolist()
    if len(tickers) > 0:
        # Ensure we don't end up with duplicate column labels after merge
        # (pandas raises ValueError: cannot reindex on an axis with duplicate labels)
        for col in ["Day_Change", "Day_Gain"]:
            if col in df.columns:
                df = df.drop(columns=[col])

        try:
            logging.info("Loading holdings from Google Sheets...")
            df = load_google_holdings("Holdings")
            df = prep_month_df(df, user_id)
        except Exception as e:
            quotes_df = fetch_day_gains(tuple(tickers))
            quotes_df_reset = (
                quotes_df[["change"]]
                .reset_index()  # bring Ticker out of index
                .rename(columns={"change": "Day_Change"})
            )
            df = df.merge(
                quotes_df_reset,
                on="Ticker",
                how="left"
            )
            df['Day_Gain'] = df['Quantity'] * df['Day_Change']
            df['Day_Gain'] = df['Day_Gain'].apply(clean_numeric)
        if not df.empty:
            logging.info("Writing holdings to SQL database...")
            with engine.begin() as conn:
                conn.execute(text("DROP TABLE IF EXISTS holdings"))
            df.to_sql("holdings", engine, if_exists="append", index=False)
    else:
        logging.error("No holdings found in holdings table")

def read_csv(csv_file, csv_header):
    logging.info(f"Reading {csv_file}")
    try:
        if csv_file == HOLDINGS_CSV:
            try:
                df = load_google_holdings('Holdings')
            except Exception as e:
                df = load_yahoo_holdings(csv_file)
            df['Beginning_Market_Value'] = df['Beginning_Market_Value'].apply(clean_numeric)
            df['Quantity'] = df['Quantity'].apply(clean_numeric)
            df['Price_Per_Unit'] = df['Price_Per_Unit'].apply(clean_numeric)
            df['Ending_Market_Value'] = df['Ending_Market_Value'].apply(clean_numeric)
            df['Unrealized_Gain/Loss'] = df['Unrealized_Gain/Loss'].apply(clean_numeric)
            df['Day_Gain'] = df['Day_Gain'].apply(clean_numeric)
            df['Total_Cost_Basis'] = df["Total_Cost_Basis"].apply(clean_numeric)
        elif 'Volume' in csv_header:
            #df = pd.read_csv(csv_file, parse_dates=['Date']).set_index('Date') 
            df = pd.read_csv(csv_file, parse_dates=['Date'])
            if df.empty:
                return pd.DataFrame(columns=csv_header)
            df['Date'] = df['Date'].dt.normalize()
        elif 'Date' in csv_header:
            df = pd.read_csv(csv_file, parse_dates=['Date'])
            df.sort_values(by=['Date'], inplace=True)
        elif 'EAI_($)_/_EY_(%)' in csv_header:
            df = pd.read_csv(csv_file, dtype={'EAI_($)_/_EY_(%)': float})
            df['Quantity'] = df['Quantity'].apply(clean_numeric)
            df['Ending_Market_Value'] = df['Ending_Market_Value'].apply(clean_numeric)
            df = df.replace("not applicable", np.nan)
            df = df.fillna(0.0)
        else:
            df = pd.read_csv(csv_file)
    except (FileNotFoundError, ValueError):
        df = pd.DataFrame(columns=csv_header)
        df.to_csv(csv_file, index=False, mode='w', header=True)
    return df

def safe_concat(df1, df2, ignore_index=False):
    if df1.empty and df2.empty:
        return df1
    elif df1.empty:
        return df2
    elif df2.empty:
        return df1
    else:
        #dfs = [df1, df2]  # List of DataFrames to concatenate
        #dfs_cleaned = [df.dropna(axis=1, how='all') for df in dfs] # Removes columns with all NaN
        #result = pd.concat(dfs_cleaned)
        #return result
        return pd.concat([df1, df2], ignore_index=ignore_index)

def next_update_on(account_list):
    balances = read_csv(BALANCES_CSV, BALANCES_HEADER)
    balances = balances[balances["Account"].isin(account_list)]
    if balances.empty:
        etd = pd.Timestamp(STATEMENT_START_DATE)
        return etd
    else:
        last_txn_month = balances['Date'].max().month
        last_txn_year = balances['Date'].max().year
        if last_txn_month == 12:
            last_txn_month = 1 # If last txn was 1/13/2025, next update will be in 2/2025 statement
            last_txn_year += 1
        else:
            last_txn_month += 1
        stmt_dt = datetime.strptime(f'{last_txn_year}-{last_txn_month}-01', '%Y-%m-%d')
        return stmt_dt
                
if __name__ == "__main__":
    #Load .env variables from file
    #from dotenv import load_dotenv
    #load_dotenv()
    MARIADB_HOST = "127.0.0.1"
    #from app.common.config import HOLDINGS_CSV, HOLDINGS_HEADER
    #df = read_csv(HOLDINGS_CSV, HOLDINGS_HEADER)
    #print(df)