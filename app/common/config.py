import os, json
from dotenv import load_dotenv
import socket
import requests

#TODO: Move non private keys from .env to config.py

# Load environment variables from .env file
#load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'), override=True)
load_dotenv(override=True)

SECRET_CACHE_BASE_URL = os.getenv("SECRET_CACHE_BASE_URL")

def get_secret(path):
    url = SECRET_CACHE_BASE_URL + path
    response = requests.get(url)
    try:
        return response.json()["value"]
    except ValueError:
        return response.text

# Helper function to parse comma-separated strings into lists
def get_list(env_var, default=""):
    return os.getenv(env_var, default).split(",") if os.getenv(env_var) else []
FINANCE_PATH = get_secret("/visualize/VM_FINANCE_PATH") if socket.gethostname() == get_secret("/visualize/SERVER_HOSTNAME") else os.getenv('DOCKER_FINANCE_PATH')
MONGO_URI = get_secret("/mongodb/MONGO_DB_URL")
FASTAPI_BASE_URL=get_secret("/visualize/FASTAPI_BASE_URL")
# File paths
PDF_PATH=f"{FINANCE_PATH}/statements"
TAX_PATH=f"{FINANCE_PATH}/taxes"
LOG_PATH="app/logs"
WATCHLIST_PATH=f"{FINANCE_PATH}/watchlists"
CACHE_PATH=f"{FINANCE_PATH}/cache"

# File Names

PDF_FILE_TAXABLE=get_secret("/visualize/PDF_FILE_TAXABLE")
PDF_FILE_RETIREMENT=get_secret("/visualize/PDF_FILE_RETIREMENT")
PDF_FILE_SPOUSE=get_secret("/visualize/PDF_FILE_SPOUSE")
PDF_WELLS_FARGO=get_secret("/visualize/PDF_WELLS_FARGO")

BALANCES_CSV = f"{FINANCE_PATH}/processed/balances.csv"
CASH_CSV = f"{FINANCE_PATH}/processed/cash.csv"
CASHFLOW_CSV = f"{FINANCE_PATH}/processed/cashflow.csv"
HOLDINGS_CSV = f"{FINANCE_PATH}/processed/holdings.csv"
HOLDINGS_BY_TICKER_CSV = f"{FINANCE_PATH}/processed/holdings_by_ticker.csv"
SBS_DIOI_CSV = f"{FINANCE_PATH}/processed/sbs_dioi.csv"
SPY_MAX_FROM_PERPLEXITY_CSV = f"{FINANCE_PATH}/SPY_MAX_FROM_PERPLEXITY.csv"
SPY_CSV = f"{FINANCE_PATH}/SPY.csv"
SPY_HEADER = ["Date","Open","High","Low","Close","Adj Close","Volume"]
BENCHMARK_CSV = f"{FINANCE_PATH}/processed/benchmark.csv"
CURRENT_BALANCES_CSV = f"{FINANCE_PATH}/processed/current_balances.csv"

FIDELITY_ACCOUNTS=get_secret("/visualize/FIDELITY_ACCOUNTS").split(",")
FIDELITY_RETIREMENT_ACCOUNTS=["brokeragelink"]

GAIN_LOSS_CSV = f"{FINANCE_PATH}/processed/gain_loss.csv"
DIVIDENDS_INTEREST_CSV = f"{FINANCE_PATH}/processed/dividends_interest.csv"
STOCK_TRANSACTIONS_CSV = f"{FINANCE_PATH}/processed/stock_transactions.csv"
HOLDINGS_HISTORY_CSV = f"{FINANCE_PATH}/processed/holdings_history.csv"
MERCHANT_CATEGORY_CSV = f"{FINANCE_PATH}/processed/merchant_category.csv"

# Dates
PDF_FORMAT_CHANGE_DATE="07/01/2017"
STATEMENT_START_DATE="2016-12-31"

# Third Party Connections
db_connection_string = get_secret("/visualize/db_connection_string")
#db_connection_string = get_secret("/visualize/db_connection_string")
OPEN_API_KEY = get_secret("/visualize/OPEN_API_KEY")
GOOGLE_API_KEY = get_secret("/google/GOOGLE_API_KEY")

# Cash
CASHFLOW_PARENT=""
#CASHFLOW_HEADER="Core Account and Credit Balance"
SPY_MAX_FROM_PERPLEXITY_HEADER = ['Date','Open','High','Low','Close','Volume']
CASHFLOW_FOOTER="Holdings"
CASHFLOW_INDICES=205,296,372
# Account Types
TAXABLE_ACCOUNTS=["Growth","Dividends","UTMA"]
RETIREMENT_ACCOUNTS=["brokeragelink"]

# Accounts for up until 2023
ALL_ACCOUNTS_2023=["cash","growth","dividends","roth","traditional","utma","hsa"]

# Accounts for 2024 and beyond
ALL_ACCOUNTS_2024=["cash","growth","dividends","roth","rolloverira","utma","hsa"]

ACTIVE_ACCOUNTS=["Growth","UTMA","RolloverIRA","Roth","HSA"]

# Mapping of account numbers to account names
ACCOUNT_NAME_MAPPING = json.loads(get_secret("/visualize/ACCOUNT_NAME_MAPPING"))
ACCOUNT_NUMBER_MAPPING = json.loads(get_secret("/visualize/ACCOUNT_NUMBER_MAPPING").encode('utf-8').decode('unicode_escape'))
EXTERNAL_ACCOUNTS = json.loads(get_secret("/visualize/EXTERNAL_ACCOUNTS").encode('utf-8').decode('unicode_escape'))

BALANCES_HEADER=["Date","Account","Balance"]
CASHFLOW_HEADER=["Date","Description","Amount","Account"]
SBS_DIOI_HEADER=["Date",'Security_Name','CUSIP',"Description",'Quantity','Price',"Amount","Account","Total_Cost_Basis"]

CASH_HEADER=["Description","Beginning_Market_Value","Quantity","Price_Per_Unit","Ending_Market_Value","Total_Cost_Basis","Unrealized_Gain/Loss","EAI_($)_/_EY_(%)","Account"]
HOLDINGS_HEADER=["Description","Beginning_Market_Value","Quantity","Price_Per_Unit","Ending_Market_Value","Total_Cost_Basis","Unrealized_Gain/Loss","EAI_($)_/_EY_(%)","Account"]
HOLDINGS_HISTORY_HEADER=["Date","Description","Beginning_Market_Value","Quantity","Price_Per_Unit","Ending_Market_Value","Total_Cost_Basis","Unrealized_Gain/Loss","EAI_($)_/_EY_(%)","Account"]
HOLDINGS_BY_TICKER_HEADER=["Description","Beginning_Market_Value","Quantity","Price_Per_Unit","Ending_Market_Value","Total_Cost_Basis","Unrealized_Gain/Loss","EAI_($)_/_EY_(%)","account"]


CREDS_JSON = {
    "type": "service_account",
    "project_id": get_secret("/google/GOOGLE_PROJECT_ID"),
    "private_key_id": get_secret("/google/GOOGLE_PRIVATE_KEY_ID"),
    "private_key": get_secret("/google/GOOGLE_PRIVATE_KEY").replace("\\n", "\n"),  # Handle newline characters
    "client_email": get_secret("/google/GOOGLE_CLIENT_EMAIL"),
    "client_id": get_secret("/google/GOOGLE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": get_secret("/google/GOOGLE_CLIENT_CERT_URL"),
    "universe_domain": "googleapis.com",
}

SCOPE = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
#creds = ServiceAccountCredentials.from_json_keyfile_dict(CREDS_JSON, SCOPE)

HOLDINGS_WEB_APP_URL = get_secret("/google/HOLDINGS_WEB_APP_URL")
HOLDINGS_SHEET_URL = get_secret("/google/HOLDINGS_SHEET_URL")

# Exception cases for accounts
# start_date: Ignore transactions before this date
# end_date: Ignore transactions after this date
# Note: The date format is MM/DD/YYYY
# Example: "start_date": "07/01/2024" means ignore transactions before July 1, 2024, perhaps account was opened on this date
# Example: "end_date": "12/31/2024" means ignore transactions after December 31, 2024, perhaps account was closed on this date
IGNORE_ACCOUNTS={"rolloverira":{"start_date":"07/01/2024"},"dividends":{"end_date":"12/31/2024"},"hsa":{"start_date":"10/01/2022"},"brokeragelink":{"end_date":"09/24/2024"}}

# Taxable account-specific rules
TAXABLE_IGNORE_RULES=[{"accounts":["growth","cash"],"start_date":"01/01/2017"},{"accounts":["cash","growth","dividends"],"start_date":"04/01/2017"}]


GMAIL_USER=get_secret("/google/GMAIL_USER")
GMAIL_PASSWORD=get_secret("/google/GMAIL_PASSWORD")
GMAIL_IMAP_SERVER=get_secret("/google/GMAIL_IMAP_SERVER")
GOOGLE_PORTFOLIO_WORKSHEET=get_secret("/google/GOOGLE_PORTFOLIO_WORKSHEET")

MAP_1040={
    "2017": {
        "PAGE1_AREA": [250,460,770,600],
        "FIRST_LINE": "7",
        "W2_WAGES":"7",
        "TAXABLE_INTEREST":"8a",
        "ORDINARY_DIVIDEND":"9a",
        "TOTAL_INCOME":"22",
        "AGI":"37",
        "TOTAL_PAYMENTS":"74",
        "TAXABLE_INCOME":"43",
        "CHILD_TAX_CREDIT":"12",
        "CAPITAL_GAIN":"13",
        "TOTAL_TAX":"63",
        "FEDERAL_W2_WITHHELD":"64",
        "REFUND":"75",
        "OWE":"78"
    },
    "2018": {
        "PAGE1_AREA": [250,460,770,600],
        "FIRST_LINE": "1",
        "W2_WAGES":"1",
        "TAXABLE_INTEREST":"2b",
        "ORDINARY_DIVIDEND":"3b",
        "TOTAL_INCOME":"6",
        "AGI":"7",
        "TOTAL_PAYMENTS":"18",
        "TAXABLE_INCOME":"10",
        "CHILD_TAX_CREDIT":"12",
        "TOTAL_TAX":"15",
        "FEDERAL_W2_WITHHELD":"16",
        "REFUND":"19",
        "OWE":"22"
    },
    "2019": {
        "PAGE1_AREA": [250,477,770,600],
        "FIRST_LINE": "1",
        "W2_WAGES":"1",
        "TAXABLE_INTEREST":"2b",
        "ORDINARY_DIVIDEND":"3b",
        "CAPITAL_GAIN":"6",
        "TOTAL_INCOME":"7b",
        "AGI":"8b",
        "TOTAL_PAYMENTS":"19",
        "TAXABLE_INCOME":"11b",
        "CHILD_TAX_CREDIT":"13b",
        "TOTAL_TAX":"16",
        "FEDERAL_W2_WITHHELD":"17",
        "REFUND":"20",
        "OWE":"23"
    },
    "2020": {
        "PAGE1_AREA": [250,477,770,600],
        "FIRST_LINE": "1",
        "W2_WAGES":"1",
        "TAXABLE_INTEREST":"2b",
        "ORDINARY_DIVIDEND":"3b",
        "CAPITAL_GAIN":"7",
        "TOTAL_INCOME":"9",
        "AGI":"11",
        "TOTAL_PAYMENTS":"33",
        "TAXABLE_INCOME":"15",
        "CHILD_TAX_CREDIT":"19",
        "TOTAL_TAX":"24",
        "FEDERAL_W2_WITHHELD":"25d",
        "REFUND":"34",
        "OWE":"37"
    },
    "2021": {
        "PAGE1_AREA": [250,477,770,600],
        "FIRST_LINE": "1",
        "W2_WAGES":"1",
        "TAXABLE_INTEREST":"2b",
        "ORDINARY_DIVIDEND":"3b",
        "CAPITAL_GAIN":"7",
        "TOTAL_INCOME":"9",
        "AGI":"11",
        "TOTAL_PAYMENTS":"33",
        "TAXABLE_INCOME":"15",
        "CHILD_TAX_CREDIT":"19",
        "TOTAL_TAX":"24",
        "FEDERAL_W2_WITHHELD":"25d",
        "REFUND":"34",
        "OWE":"37"
    },
    "2022": {
        "PAGE1_AREA": [250,477,770,600],
        "FIRST_LINE": "1a",
        "W2_WAGES":"1a",
        "TAXABLE_INTEREST":"2b",
        "ORDINARY_DIVIDEND":"3b",
        "CAPITAL_GAIN":"7",
        "TOTAL_INCOME":"9",
        "AGI":"11",
        "TOTAL_PAYMENTS":"33",
        "TAXABLE_INCOME":"15",
        "CHILD_TAX_CREDIT":"19",
        "TOTAL_TAX":"24",
        "FEDERAL_W2_WITHHELD":"25d",
        "REFUND":"34",
        "OWE":"37"
    },
    "2023": {
        "PAGE1_AREA": [250,477,770,600],
        "FIRST_LINE": "1a",
    },
    "2024": {
        "PAGE1_AREA": [250,477,770,600],
        "FIRST_LINE": "1a",
        "W2_WAGES":"1a",
        "TAXABLE_INTEREST":"2b",
        "ORDINARY_DIVIDEND":"3b",
        "CAPITAL_GAIN":"7",
        "TOTAL_INCOME":"9",
        "AGI":"11",
        "TOTAL_PAYMENTS":"33",
        "TAXABLE_INCOME":"15",
        "CHILD_TAX_CREDIT":"19",
        "TOTAL_TAX":"24",
        "FEDERAL_W2_WITHHELD":"25d",
        "REFUND":"34",
        "OWE":"37"
    }
}

WELLS_FARGO_COLUMNS  = [90,100,375,450,520]
WELLS_FARGO_AREA = [10,9,95,100]

MARIADB_DATABASE=get_secret("/mariadb/MARIADB_DATABASE")
MARIADB_HOST=get_secret("/mariadb/MARIADB_HOST")
MARIADB_USER=get_secret("/mariadb/MARIADB_USER")
MARIADB_PASSWORD=get_secret("/mariadb/MARIADB_PASSWORD")
MARIADB_PORT=get_secret("/mariadb/MARIADB_PORT")