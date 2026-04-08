import pandas as pd
import streamlit as st
import pickle
from datetime import datetime
import time
import logging
#from pymongo import MongoClient, ASCENDING, DESCENDING
import re
import numpy as np
from typing import Dict, Any, Optional, Callable
import requests
from common.dbcache import clear_cache

from app.common.config import *
from app.common.utils import use_modern_fonts, call_api,  load_holdings_sql
from modules.Plot import plot_scatter_chart,plot_day_gain,plot_balance_history,plot_balance_history_animated, plot_account_value,plot_holdings,plot_performance,plot_investment,plot_returns,plot_unrealized_gain_loss,plot_realized_gain_loss,plot_income,plot_current_month_category,plot_merchant_growth,plot_past_month_category,plot_category_by_year,plot_category_growth,plot_annual_expenses,plot_monthly_expenses,plot_total_expenses
from app.modules.AdminMariaDB import AdminMariaDB
from modules.Welcome import render_landing
from sqlalchemy import create_engine
from common.config import MARIADB_DATABASE, MARIADB_PASSWORD, MARIADB_PORT, MARIADB_USER, MARIADB_HOST
from common.dbcache import get_df

# OpenTelemetry imports
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import set_tracer_provider
from opentelemetry.instrumentation.requests import RequestsInstrumentor
#from opentelemetry import trace

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def setup_tracing() -> None:
    APP_NAME = "visualize"
    resource = Resource(attributes={SERVICE_NAME: APP_NAME})
    tracer_provider = TracerProvider(resource=resource)
    set_tracer_provider(tracer_provider)

    otlp_exporter = OTLPSpanExporter(
        endpoint="http://otel-collector:4318/v1/traces"
    )
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    RequestsInstrumentor().instrument()

setup_tracing()
#logging.info(f"Current trace span: {trace.get_current_span()}")
use_modern_fonts()
#os.makedirs("/tmp/py-yfinance-cache", exist_ok=True)
#yf.set_tz_cache_location("/tmp/py-yfinance-cache")
accounts = [d["account"] for d in call_api('/accounts')]
st.session_state.debug = False
PEPPER = get_secret("/visualize/PW_PEPPER")
FASTAPI_KEY = get_secret("/visualize/MY_API_KEY")
performance_total_response = call_api('/performance/total', timeout=60)
if 'first_run' not in st.session_state:
    st.session_state.expected_return = performance_total_response['cagr']*100
performance_day_response = call_api("/performance/day")
analytics_summary_response = call_api('/analytics/summary?years=1')
annual_expenses = call_api('/cash/drawdown')
mag7_response = call_api('/performance/mag7')
spiffy_pops = call_api("/performance/spiffy_pops")
#client = MongoClient(MONGO_URI, uuidRepresentation="standard")
#email_db = client[EMAIL_DB_NAME]
#users_db = client[USERS_DB_NAME]
engine = create_engine(f"mysql+pymysql://{MARIADB_USER}:{MARIADB_PASSWORD}@{MARIADB_HOST}:{MARIADB_PORT}/{MARIADB_DATABASE}", pool_pre_ping=True)

def coerce_float(value: Any) -> Optional[float]:
    """Best-effort conversion to float, returning None on failure."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None

# Default Values
#     initial_balance, expected_return, volatility, years, real_contribution, simulations, seed

def poll_import_status(
    portfolio_id: str,
    import_id: str,
    *,
    interval: float = 3.0,
    timeout: float = 600.0,
    headers: Optional[Dict[str, str]] = None,
    on_progress: Optional[Callable[[int, str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Poll the import status until it reaches a terminal state or times out.

    Terminal states: completed, failed, canceled.
    Returns the final JSON resource.
    """
    headers = headers or {"X-User-Id": st.session_state.user['username']}
    url = f"{FASTAPI_BASE_URL}/portfolios/{portfolio_id}/imports/{import_id}"

    start = time.time()
    last_status: Optional[str] = None

    while True:
        try:
            resp = requests.get(url, headers=headers, timeout=15)
        except requests.RequestException as e:
            raise RuntimeError(f"Polling request failed: {e}") from e

        if resp.status_code == 404:
            raise RuntimeError(f"Import not found: {import_id}")
        if resp.status_code >= 400:
            raise RuntimeError(f"Polling error {resp.status_code}: {resp.text}")

        data = resp.json()
        status = data.get("status")
        progress = data.get("progress")

        if on_progress:
            try:
                on_progress(int(progress or 0), str(status), data)
            except Exception:
                pass
        else:
            if status != last_status:
                print(f"status={status} progress={progress}%")
                last_status = status
            else:
                print(f"progress={progress}%")

        if status in {"completed", "failed", "canceled"}:
            return data

        if time.time() - start > timeout:
            raise TimeoutError(
                f"Timed out waiting for import {import_id} (last status={status}, progress={progress}%)"
            )

        time.sleep(interval)

def import_statements():
    st.header("Portfolio PDF Import")
    st.write("Upload one or more PDF statements and track progress.")
    uploads = st.file_uploader("PDF files", type=["pdf"], accept_multiple_files=True)

    # Only keep files named Statementmmddyyyy.pdf and sort by date in filename
    valid_uploads_sorted = []
    invalid_names = []
    if uploads:
        tmp = []
        for uf in uploads:
            name = uf.name.strip()
            m = re.fullmatch(r"Statement(\d{1,2})(\d{2})(\d{4})\.pdf", name)
            if not m:
                m = re.fullmatch(r'(\d{4})\-(\d{1,2})\-(\d{2})\.pdf', name)
                if not m:
                    invalid_names.append(name)
                    continue
                else:
                    mm, dd, yyyy = m.group(2), m.group(3), m.group(1)
            else:
                mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
            try:
                dt = datetime(int(yyyy), int(mm), int(dd))
            except ValueError:
                invalid_names.append(name)
                continue
            tmp.append((dt, uf))
        tmp.sort(key=lambda t: t[0])
        valid_uploads_sorted = [uf for _, uf in tmp]

    if invalid_names:
        st.warning("Ignoring files not matching Statementmmddyyyy.pdf: " + ", ".join(invalid_names))

    if st.button("Upload and Import", disabled=not valid_uploads_sorted):
        if not valid_uploads_sorted:
            st.warning("Please select at least one PDF.")
            st.stop()
        headers = {"X-User-Id": st.session_state.user['username']}
        if FASTAPI_KEY:
            headers["X-API-Key"] = FASTAPI_KEY

        # Build files for requests directly from UploadedFile objects
        files = [("pdfs", (uf.name, uf, "application/pdf")) for uf in valid_uploads_sorted]

        with st.spinner("Submitting import..."):
            url = f"{FASTAPI_BASE_URL}/portfolios/port1/imports"
            resp = requests.post(url, headers=headers, files=files, timeout=60)
            if resp.status_code >= 400:
                st.error(f"Upload failed {resp.status_code}: {resp.text}")
                st.stop()
            initial = resp.json()

        #st.info(f"Accepted import id: {initial['id']}")
        prog = st.progress(0)
        status_txt = st.empty()

        def _on_progress(pct: int, status: str, data: Dict[str, Any]):
            prog.progress(max(0, min(100, pct)))
            status_txt.write(f"Importing: ({pct}%)")

        try:
            final = poll_import_status(
                "port1",
                initial["id"],
                headers=headers,
                on_progress=_on_progress,
            )
        except TimeoutError as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"Polling failed: {e}")
            st.stop()

        if final.get("status") == "completed":
            #st.json(final)
            st.success(f"Import {final['status']} {final['progress']}%")
            load_holdings_sql(st.session_state.user['username'])
            clear_cache("holdings_view")
            clear_cache("balances")
            clear_cache("cash")
            clear_cache("cashflow")
            clear_cache("sbs_dioi")
            st.session_state.bal = get_networth(datetime.now().year, "dollar")
            st.session_state.day_gain = performance_day_response["day_gain"]
        elif final.get("status") == "failed":
            st.error("Import failed")
            st.json(final)
        elif final.get("status") == "canceled":
            st.warning("Import canceled")
            st.json(final)
        
def get_networth(year, units):
    accounts_response = call_api(f'/accounts/networth?year={year}&units={units}')
    return accounts_response['networth']
    
def log_runtime(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        logging.info(f"Method {func.__name__} took {end_time - start_time:.4f} seconds")
        return result
    return wrapper

def sidebar_simulation_panel():
    with st.sidebar:
        # ⚙️ Monte Carlo panel
        with st.expander("⚙️ Monte Carlo", expanded=False):
            st.caption("Monte Carlo Simulation Parameters")
            #_ = st.number_input("Initial Balance ($)", value=int(st.session_state.financials.get_current_net_worth()), step=1000, key="initial_balance")
            _ = st.number_input("Initial Balance ($)", value=int(get_networth(datetime.now().year, "dollar")), step=1000, key="initial_balance")
            performance_total_response = call_api(f'/performance/total') # Growth return over last 10 years
            #if st.session_state.account == 'all':
            #    st.session_state.expected_return = performance_total_response['cagr']*100
            #else:
            #    performance_xirr_response = call_api(f'/performance/xirr/{st.session_state.account}?period_in_months={st.session_state.projection_period}') # Growth return over last 10 years
            #    st.session_state.expected_return = performance_xirr_response['xirr (%)']
            st.session_state.expected_return = st.slider("Expected Annual Return (CAGR)", 0.0, 20.0, st.session_state.expected_return)
            if len(performance_total_response) > 0:
                st.session_state.volatility = st.slider("Annual Volatility (%)", 0.0, 30.0, (performance_total_response['annual_volatility']*100))/100
            else:
                st.session_state.volatility = 0.0
            _ = st.slider("Investment Horizon (Years)", 1, 50, 50, key="years")
            _ = st.slider("Inflation Rate", 0.0, 9.0, 2.5, step=1.0, key="inflation_rate")  # 3%

            if len(annual_expenses) > 0:
                _ = st.number_input("Annual Contribution ($)", value=-(int(annual_expenses['drawdown'])), step=1000, key="annual_contribution")
            else:
                st.session_state.annual_contribution = 0
            st.session_state.real_contribution = st.session_state.annual_contribution * ((1 + (st.session_state.inflation_rate/100)) ** st.session_state.years)
            _ = st.slider("Number of Simulations", 100, 5000, 1000, step=100, key="simulations")
            _ = st.number_input("Random Seed (optional)", value=42, key="seed")

def sidebar_configuration_panel():
    with st.sidebar:
        # ⚙️ Configuration panel
        with st.expander("⚙️ Configuration", expanded=False):
            st.caption("Place your future app settings here.")
            # Example placeholders:
            _ = st.checkbox("Enable dark mode (coming soon)", key="cfg_darkmode")
            _ = st.text_input("Default note prefix", key="cfg_prefix", placeholder="e.g., #todo ")
            #Other
            status = st.checkbox("Active Accounts Only", False)
            taxable = st.checkbox("Taxable", False)
            #show_txns = st.checkbox("Transactions", False)
            #expense_toggle = st.toggle("Show Expenses", value=False)

            #st.session_state.account = 'all'
            #if taxable:
            #    _ = st.selectbox("Select Account 👇", TAXABLE_ACCOUNTS, key="account")
            #elif status: # Active Accounts
            #    _ = st.selectbox("Select Account 👇", ACTIVE_ACCOUNTS, key="account")
            #else:
            _ = st.selectbox("Select Account 👇", accounts + ['all'], index=len(accounts), key="account")

            st.session_state.list_of_years = [str(year) for year in range(2017, datetime.now().year + 1)]
            _ = st.selectbox("Select Year 👇", st.session_state.list_of_years + ['all'], index=len(st.session_state.list_of_years), key="selected_year")
            _ = st.selectbox("Select Month 👇", [1,2,3,4,5,6,7,8,9,10,11,12], index=11 if datetime.now().month == 1 else datetime.now().month-2, key="selected_month")
            categories_json = call_api("/credit/category/total")
            category_list = [item["Category"] for item in categories_json if item.get("Category")]
            _ = st.selectbox("Select Category", category_list + ['all'], index=len(category_list), key="category")
            # Get all unique merchants from the DataFrame where the frequency is greater than 1
            merchant_list = call_api("/credit/merchant/list")
            _ = st.selectbox("Select Merchant", merchant_list, key="merchant")
            # Determine minimum slider value based on available statement months
            try:
                import os
                min_projection_period = -120 
                available_months = 0
                base_dir = os.path.abspath(PDF_PATH)
                if os.path.isdir(base_dir):
                    for y in os.listdir(base_dir):
                        if y.isdigit() and len(y) == 4:
                            ydir = os.path.join(base_dir, y)
                            if not os.path.isdir(ydir):
                                continue
                            for m in os.listdir(ydir):
                                if m.isdigit():
                                    mdir = os.path.join(ydir, m)
                                    if not os.path.isdir(mdir):
                                        continue
                                    if os.path.exists(os.path.join(mdir, PDF_FILE_TAXABLE)) or os.path.exists(os.path.join(mdir, PDF_FILE_RETIREMENT)):
                                        available_months += 1
                if 0 < available_months < min_projection_period:
                    min_projection_period = available_months
            except Exception:
                min_projection_period = 12
            _ = st.slider("Select Projection Period (Months)", min_value=min_projection_period, max_value=552, value=0, step=12, key="projection_period")
            #revenue_growth_threshold = st.sidebar.slider( "Select Minimum Revenue Growth (%)", min_value=0, max_value=100, value=20, step=1)
            #_ = st.sidebar.slider( "Select Minimum Price Drop (%)", min_value=-80, max_value=20, value=-10, step=1, key="price_drop_threshold")

@st.cache_data
def monte_carlo_simulation(
    initial_balance, expected_return, volatility,
    years, real_contribution, simulations, seed
    ):
    np.random.seed(seed)
    results = np.zeros((years + 1, simulations))
    results[0] = initial_balance

    for t in range(1, years + 1):
        rand_returns = np.random.normal(expected_return, volatility, simulations)
        results[t] = (results[t - 1] + real_contribution) * (1 + rand_returns)

    df = pd.DataFrame(results)
    df.index.name = "Year"

    percentiles = df.quantile([0.1, 0.5, 0.9], axis=1).T
    percentiles.columns = ['10th', '50th', '90th']

    return df, percentiles

#st.json(dict(st.session_state))
admin = AdminMariaDB()
admin.sidebar_admin_panel(engine)

sidebar_configuration_panel()

if 'user' in st.session_state and 'authenticated' in st.session_state.user:
    import_statements()
    # Set db_initialized to False if balances AND credit tables are both empty
    try:
        balances_empty = get_df("balances", engine=engine, ttl=60, parse_dates=["Date"]).empty
    except Exception:
        balances_empty = True
    try:
        credit_empty = get_df("credit", engine=engine, ttl=60, parse_dates=["Date"]).empty
    except Exception:
        credit_empty = True
    db_initialized = not (balances_empty and credit_empty)
    if db_initialized:
        sidebar_simulation_panel()
        # Following is not secured
        #if st.session_state.debug == True:
        #    #st.json(dict(st.session_state))
        #    logging.info(st.session_state)

        #home_container,
        today_container, invest_container, expense_contianer, txn_container = st.tabs(["Today", "Investments", "Expenses", "Transactions"])

        #with home_container:
        #    with st.status("Importing bank statements...", expanded=True) as status:
        #        progress_bar = st.progress(0)
        #        status_text = st.empty()
        #        upload_statement(status_text)
        if 'first_run' not in st.session_state:
            logging.info("First run - Loading Data...")
            #load_data(status, status_text, callback=update_progress)
            load_holdings_sql(st.session_state.user['username'])
            clear_cache("holdings_view")
            st.session_state.bal = get_networth(datetime.now().year, "dollar")
            prev_bal = get_networth(datetime.now().year - 1, "dollar")
            st.session_state.first_run = False
            #st.session_state.credit['Date'] = pd.to_datetime(st.session_state.credit['Date'], errors='coerce')
            #st.session_state.credit['Year'] = st.session_state.credit['Date'].dt.year
            #st.session_state.credit['Month'] = st.session_state.credit['Date'].dt.month


        with today_container:
            left_column, right_column = st.columns(2)
            with left_column:
                #today_gain = st.session_state.financials.holdings_df['Day_Gain'].sum()
                day_gain_value = coerce_float(performance_day_response.get("day_gain"))
                if day_gain_value is None:
                    logging.warning("Unable to parse day gain value: %s", performance_day_response.get("day_gain"))
                    day_gain_value = 0.0
                st.session_state.day_gain = day_gain_value
                st.metric(label="Net Worth (10⁵)", value=f"{'{:,.2f}'.format(st.session_state.bal/100000)}", delta=f"{'{:,.2f}'.format(st.session_state.day_gain)}")
                st.metric(label="Net Worth (BTC)", value=f"{'{:,.2f}'.format(get_networth(datetime.now().year, 'btc'))}", delta=f"{'{:,.2f}'.format(get_networth(datetime.now().year-1, 'btc'))}")
                st.metric(label="Net Worth (KG of GOLD)", value=f"{'{:,.2f}'.format(get_networth(datetime.now().year, 'gold_kg'))}", delta=f"{'{:,.2f}'.format(get_networth(datetime.now().year-1, 'gold_kg'))}")

                #df = st.session_state.credit.copy()
                #df = df[(df['Category'] != 'Education') & (df['Category'] != 'Debt Payments')]
                #grouped = df.groupby(['Year', 'Category'])['Amount'].sum().reset_index()
                current_year = datetime.now().year
                #current_year_expense = grouped[grouped['Year'] == current_year]['Amount'].sum()
                today = datetime.now()
                start_of_year = datetime(today.year, 1, 1)
                days_so_far = (today - start_of_year).days + 1
                #st.metric(
                #    label="Monthly Expense Limit (Based on 3.7% Drawdown)", 
                #    value=f"{'{:,.2f}'.format(30*(st.session_state.bal/10000))}", 
                #    delta=f"{'{:,.2f}'.format(30*(st.session_state.bal/10000)-30*(current_year_expense/days_so_far))}")
                st.metric(
                    label='Monthly Holding Period Return (HPR)',
                    value=f"{'{:,.2f}'.format(analytics_summary_response['average_return']*100)}%", 
                )
                st.metric(
                    label='Largest observed peak-to-trough decline',
                    value=f"{'{:,.2f}'.format(analytics_summary_response['max_drawdown']*100)}%", 
                )
                st.metric(
                    label='Annual Volatility',
                    value=f"{'{:,.2f}'.format(st.session_state.volatility*100)}%", 
                )
                st.metric(
                    label='Sharpe Ratio',
                    value=f"{'{:,.2f}'.format(analytics_summary_response['sharpe_ratio'])}", 
                )
                #st.metric(
                #    label='XIRR',
                #    value=f"{'{:,.2f}'.format(performance_total_response['xirr']*100)}%", 
                #)
                st.metric(
                    label='CAGR',
                    value=f"{'{:,.2f}'.format(performance_total_response['cagr']*100)}%", 
                )
                if st.session_state.expected_return != 0.0:
                    st.metric(
                        label='Rule of 72',
                        value=f"{'{:,.2f}'.format(72/st.session_state.expected_return)} Years", 
                    )
                st.metric(
                    label='Billionaire watch',
                    value=f"{int(round(performance_total_response['years_to_billionaire']+current_year))}", 
                )
                st.metric(
                    label='Magnificent 7 Score',
                    value=f"{mag7_response['score']}" 
                )
                #if len(spiffy_pops) > 0:
                st.metric(
                    label="Today's Spiffy Pops",
                    value=f"{spiffy_pops}" 
                )
            with right_column:
                plot_day_gain(right_column, engine)
                df_sim, percentiles = monte_carlo_simulation(
                    st.session_state.initial_balance, st.session_state.expected_return/100, st.session_state.volatility, st.session_state.years, st.session_state.real_contribution, st.session_state.simulations, st.session_state.seed
                )
                st.write("Simulation based on:")
                st.write(f"Account:{st.session_state.account}")
                st.write(f"Period: {st.session_state.projection_period}")
                st.write(f"Expected Return: {st.session_state.expected_return}")
                plot_scatter_chart(percentiles)

                # --- Summary Table ---
                #st.subheader("📊 Final Year Summary")
                #final = df_sim.loc[st.session_state.years]
                #summary = final.describe(percentiles=[.1, .5, .9]).T[['mean', 'std']]
                #st.dataframe(summary)

                plot_balance_history(st.session_state.account, right_column)
                plot_balance_history_animated(st.session_state.account, right_column)
                plot_account_value(right_column)

        with invest_container:
            # Investments
            plot_holdings(st.session_state.account, invest_container)    
            plot_performance(st.session_state.account, invest_container)
            plot_investment(invest_container, engine)
            plot_returns(invest_container)    
            #plot_backtest(invest_container, engine)
            plot_income(invest_container, engine)
            plot_unrealized_gain_loss(invest_container, engine)
            plot_realized_gain_loss(invest_container)
            #plot_balances(invest_container, engine)

        #with expense_contianer:
        if True:
            # Expenses
            plot_current_month_category(expense_contianer)
            plot_past_month_category(expense_contianer)
            plot_category_growth(st.session_state.category, expense_contianer, txn_container)
            plot_merchant_growth(st.session_state.merchant, expense_contianer, txn_container)
            #plot_expense_growth(expense_contianer)
            plot_total_expenses(expense_contianer)
            plot_monthly_expenses(expense_contianer)
            plot_annual_expenses(expense_contianer, txn_container)
            plot_category_by_year(expense_contianer)

else:
    # Render the landing page with sign-in/subscription CTA
    render_landing()
