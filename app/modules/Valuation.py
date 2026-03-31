import configparser
import pandas as pd
from datetime import datetime
import os
import pickle
import yfinance as yf
from fuzzywuzzy import process
from app.common.config import WATCHLIST_PATH


class Valuation:
    def __init__(self, ticker, stock_data, stock_info):
        # Read properties file
        self.config = configparser.ConfigParser()
        self.config.read('config.properties')

        self.ticker = ticker
        self.stock_data = stock_data
        self.stock_info = stock_info
        self.valuation = None
        self.valuation_methods = [
            self.pe_ratio,
            self.ps_ratio,
            self.pb_ratio,
            self.pfcf_ratio,
            self.peg_ratio,
            self.dcf_ratio,
            self.graham_number,
            self.earnings_yield,
            self.dividend_yield,
            self.book_value,
            self.net_asset_value,
            self.intrinsic_value,
            self.enterprise_value
        ]
        
    def load_from_disk(self, file_path):
        with open(file_path, 'rb') as f:
            return pickle.load(f)
        
    def save_to_disk(self, data, file_path):
        with open(file_path, 'wb') as f:
            pickle.dump(data, f)
    
    def pe_ratio(self):
        pe_ratio = self.stock_info.get('forwardPE', None)
        if pe_ratio is None:
            pe_ratio = self.stock_info.get('trailingPE', None)
        return {"name": self.pe_ratio.__name__, "value": round(pe_ratio, 2)} if pe_ratio is not None else None
    
    def ps_ratio(self):
        ps_ratio = self.stock_info.get('priceToSalesTrailing12Months', None)
        return {"name": self.ps_ratio.__name__, "value": round(ps_ratio, 2)} if ps_ratio is not None else None
    
    def pb_ratio(self):
        pb_ratio = self.stock_info.get('priceToBook', None)
        return {"name": self.pb_ratio.__name__, "value": round(pb_ratio, 2)} if pb_ratio is not None else None
    
    def pfcf_ratio(self):
        pfcf_ratio = self.stock_info.get('priceToFreeCashFlows', None)
        return {"name": self.pfcf_ratio.__name__, "value": round(pfcf_ratio, 2)} if pfcf_ratio is not None else None
    
    def peg_ratio(self):
        pe_ratio = self.pe_ratio()
        growth_rate = self.stock_info.get('earningsGrowth', None)
        peg_ratio = pe_ratio / (growth_rate * 100) if pe_ratio and growth_rate else None
        return {"name": self.peg_ratio.__name__, "value": round(peg_ratio, 2)} if peg_ratio is not None else None
    
    def dcf_ratio(self):
        return None
    
    def graham_number(self):
        return None
    
    def earnings_yield(self):
        return None
    
    def dividend_yield(self):
        dividend_yield = self.stock_info.get('dividendYield', 0)
        return {"name": self.dividend_yield.__name__, "value": round(dividend_yield, 2)} if dividend_yield is not None else None
    
    def book_value(self):
        book_value = self.stock_info.get('bookValue', None)
        return {"name": self.book_value.__name__, "value": round(book_value, 2)} if book_value is not None else None
    
    def net_asset_value(self):
        return None
    
    def intrinsic_value(self):
        return None
    
    def enterprise_value(self):
        return None
    
    def calculate_valuation(self):
        for method in self.valuation_methods:
            self.valuation = method()
            if self.valuation is not None:
                break
        return
    
    def get_valuation(self):
        return self.valuation
    
    def valuate(self, pe, sector, industry):
        sec, avg_pe, std_dev = self.find_sector_match(sector, industry)
        if pe >= (avg_pe + std_dev):
            return "Overvalued, consider selling. If guidance is poor, stock price will drop big"
        elif pe <= (avg_pe - std_dev):
            return "Undervalued, consider buying"
        else:
            return "Fairly valued"

    def find_sector_match(self, sector, industry):
        # Read the sector PE stats CSV file
        sector_stats = pd.read_csv(f'{WATCHLIST_PATH}/sector_pe_stats.csv')

        # Combine sector and industry for matching
        sector_industry = f"{sector} {industry}"

        # Find the best match using fuzzy string matching
        best_match = process.extractOne(sector_industry, sector_stats['sector'])

        if best_match:
            matched_sector = best_match[0]
            matched_row = sector_stats[sector_stats['sector'] == matched_sector].iloc[0]
            #print(f"{sector} {industry} ==> {matched_row['sector']}")
            return matched_row['sector'], matched_row['average_pe'], matched_row['std_deviation']
        else:
            return None, None, None

if __name__ == "__main__":
    # Example usage
    # Load stock data
    ticker = 'WDAY'
    stock_data = yf.download(ticker, start="2025-03-10", end=datetime.now().strftime("%Y-%m-%d"), progress=False)
    stock_info = yf.Ticker(ticker).info
    v = Valuation(ticker, stock_data, stock_info)

    print(v.find_sector_match(v.stock_info.get('sector'), v.stock_info.get('industry')))

    v.calculate_valuation()

    print(f"{v.get_valuation().get('name')} = {v.get_valuation().get('value')}")
    print(v.stock_info.get('sector'))
    print(v.stock_info.get('industry'))

    if v.get_valuation().get('name') == 'pe_ratio':
        print(v.valuate(v.get_valuation().get('value'), v.stock_info.get('sector').lower(), v.stock_info.get('industry').lower()))

    