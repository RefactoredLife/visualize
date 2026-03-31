import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from app.common.utils import call_api
import pandas as pd
from app.modules.Benchmark import Benchmark 
from scipy.optimize import curve_fit
import numpy as np
from plotly.subplots import make_subplots
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import logging
from common.dbcache import get_df

colors = ['green','aqua','red','purple','orange','brown','pink','gray','olive','cyan','azure','blue','burlywood','chartreuse','coral','cornflowerblue','darkgoldenrod','darkgray','darkkhaki','darkorange','darkseagreen']

#accounts = [d["account"] for d in call_api('/accounts')]
accounts = [d["account"] for d in (call_api('/accounts') or [])]


def debug_log(label, df):
    if st.session_state.get("debug", False):
        st.write(f"🔍 {label}:", df)
        
def color_balance(val):
    # Apply conditional formatting
    color = 'red' if val < 0 else 'green'
    return f'color: {color}'

def train_model(months_to_project, engine):
    #df = st.session_state.fidelity.balances.get()
    df = get_df("balances", engine=engine, ttl=60, parse_dates=["Date"]) 
    if df.empty:
        return

    # Add current balances to the DataFrame
    #accounts = df['Account'].unique()
    #df2 = self.get_current_balances([key.lower() for key in accounts])
    accounts_response = call_api("/accounts")
    df2 = pd.DataFrame(accounts_response)[['account','total_value']]
    df2.columns = ['Account', 'Balance']

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

def plot_pie_chart(container, title, labels, values, hole):
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=hole,
        marker=dict(line=dict(color="#000000", width=1)),
        #textinfo="label+percent"
        textinfo="none",  # ← hides text labels entirely
        hoverinfo="label+percent+value", 
    )])

    #TODO: add following line to all charts to match fonts to streamlit custom fonts
    fig.update_layout(font=dict(family="Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, 'Helvetica Neue', Arial, sans-serif"))

    fig.update_layout(
        title=title,
        showlegend=True
    )

    with container:
        st.plotly_chart(fig, use_container_width=True)

def plot_scatter_chart(percentiles):
        # --- Plotly Chart ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=percentiles.index,
            y=percentiles['50th'],
            mode='lines',
            name='Median (50th percentile)',
            line=dict(color='blue')
        ))
        fig.add_trace(go.Scatter(
            x=percentiles.index,
            y=percentiles['90th'],
            mode='lines',
            name='90th percentile',
            line=dict(color='green', dash='dot')
        ))
        fig.add_trace(go.Scatter(
            x=percentiles.index,
            y=percentiles['10th'],
            mode='lines',
            name='10th percentile',
            line=dict(color='red', dash='dot'),
            fill='tonexty',
            fillcolor='rgba(0,100,80,0.2)'
        ))
        fig.update_layout(
            title="Monte Carlo Simulation",
            xaxis_title="Year",
            yaxis_title="Portfolio Value ($)",
            hovermode="x unified",
            template="plotly_white"
        )
        fig.update_layout(
            legend=dict(
                orientation="h",           # horizontal layout
                yanchor="bottom",
                y=1.02,                    # a bit above the top of the plot
                xanchor="left",
                x=0.5                      # center it horizontally
            )
        )
        st.plotly_chart(fig, use_container_width=True)

def plot_stacked_bar_chart(container, color, df, x, y, chart_title, xaxis_title, yaxis_title, hover_data):
    #fig = px.bar(df, x=x, y=y, title=chart_title, color_discrete_sequence=px.colors.qualitative.Plotly, hover_data=hover_data)
    fig = px.bar(df, x=x, y=y, title=chart_title, color=color, text_auto=True, hover_data=hover_data)
    fig.update_layout(hoverlabel=dict(font=dict(size=20)))
    fig.update_layout(barmode='stack', xaxis_title=xaxis_title, yaxis_title=yaxis_title)
    with container:
        st.plotly_chart(fig)
                
# Stocks
def plot_day_gain(container, engine):
    #df = st.session_state.fidelity.holdings_df.get()
    df = get_df("holdings_view", engine=engine, ttl=60)
    if df.empty:
        return

    # 👇 Compute total Day_Gain per Ticker
    ticker_totals = df.groupby("Ticker")["Day_Gain"].sum().reset_index()
    ticker_totals.rename(columns={"Day_Gain": "Ticker_Total_Gain"}, inplace=True)

    # 👇 Merge total back into original DataFrame
    df = df.merge(ticker_totals, on="Ticker", how="left")

    # ✅ Create bar chart
    fig = px.bar(
        df,
        x='Ticker',
        y='Day_Gain',
        title='Day Gains',
        color='Day_Gain',
        #color_continuous_scale=['red', 'lightgrey', 'green'],
        color_continuous_scale=[
            "#8B0000",  # dark red
            "#FF9999",  # light red
            "#D3D3D3",  # light grey near zero
            "#90EE90",  # light green
            "#006400"   # dark green
        ],
        range_color=[df['Day_Gain'].min(), df['Day_Gain'].max()]  # span across
    )

    # ✅ Customize tooltip to show only Ticker and Ticker Total
    fig.update_traces(
        customdata=df[['Ticker_Total_Gain']],
        hovertemplate=(
            "Ticker: %{x}<br>" +
            "Ticker Total Gain: $%{customdata[0]:,.2f}" +
            "<extra></extra>"
        )
    )

    fig.update_layout(coloraxis_showscale=False)

    with container:
        st.plotly_chart(fig, use_container_width=True)

def plot_category_by_year(container):

    # Copy data and filter out the 'Education' category
    #df = df.copy()
    if st.session_state.selected_year == 'all':
        #df = df[df['Year'].astype(str).isin(st.session_state.list_of_years)]
        df = pd.DataFrame(call_api("/credit/category/total"),columns=['Category', 'Amount'])
    else:
        #df = df[df['Year'] == int(st.session_state.selected_year)]
        df = pd.DataFrame(call_api(f"/credit/category/total?interval=yearly&month=1&year={st.session_state.selected_year}"),columns=['Category', 'Amount'])
    # Group spending by Year and Category
    grouped = df.groupby(['Category'])['Amount'].sum().reset_index()
 
    color_map = {
        'Housing': 'green',
        'Insurance': 'red',
        'Transportation': 'aqua',
        'Food & Dining': 'purple',
        'Utilities': 'orange',
        'Healthcare':'brown',
        'Subscription': 'pink',
        'Entertainment': 'gray',
        'Shopping': 'olive',
        'Personal Care': 'cyan',
        'Travel': 'azure',
        'Debt Payments': 'blue',
        'Tax': 'burlywood',
        'Education': 'chartreuse',
        'Miscellaneous': 'coral'
    }   

    # Create the bar chart
    fig = px.bar(
        grouped,
        x='Category',
        y='Amount',
        color='Category',
        color_discrete_map=color_map,
        title='Category By Year',
        labels={'Amount': 'Amount', 'Category': 'Category'},
        text_auto=True,
        #height=1000
    )

    with container:
        st.plotly_chart(fig)

def plot_holdings(account, container):
    if account.upper() == 'ALL':
        holdings_dict = call_api('/holdings')
    else:
        holdings_dict = call_api(f'/holdings?account={account.upper()}')
    df = pd.DataFrame(holdings_dict)    
    if df.empty:
        return
    df = df.nlargest(100, 'Total_Cost_Basis')
    plot_stacked_bar_chart(container, None, df, chart_title=f'{account.capitalize()} Holdings', xaxis_title='Ticker', x='Ticker', y=['Total_Cost_Basis','Unrealized_Gain/Loss'], yaxis_title='Ending Market Value', hover_data={'Ending_Market_Value': True})
        
def plot_performance(account, container):
    values = []
    df = pd.DataFrame([], columns=['Account', 'XIRR (%)'])
    if account.upper() == 'ALL':
        xirr_list = call_api(f'/performance/xirr?period_in_months={st.session_state.projection_period}')
        if len(xirr_list) == 0:
            return
        for acc in accounts:
            #temp_xirr = fin.calculate_xirr(acc.lower())
            temp_xirr = next((item['xirr (%)'] for item in xirr_list if item['account'] == acc.upper()), None)
            values.append(0.0 if temp_xirr is None else round(temp_xirr, 2))
        df['Account'] = accounts
    else:
        xirr_list = call_api(f'/performance/xirr/{account.upper()}?period_in_months={st.session_state.projection_period}')
        if len(xirr_list) == 0:
            return
        temp_xirr = xirr_list['xirr (%)']
        #temp_xirr = fin.calculate_xirr(account.upper())
        values.append(0.0 if temp_xirr is None else round(temp_xirr, 2))
        df['Account'] = [account.upper()]
    df['XIRR (%)'] = values
    fig = px.bar(df, x='Account', y='XIRR (%)', color='Account', title=f'{account.capitalize()} Performance', text_auto=True, color_discrete_sequence=colors)
    with container:
        st.plotly_chart(fig)

def get_cash_and_stock(engine):
    #holdings_df = st.session_state.fidelity.holdings_df.get()
    holdings_df = get_df("holdings_view", engine=engine, ttl=60)
    if holdings_df.empty:
        return pd.DataFrame()
    # Calculate the amount invested in each account
    amount_invested_df = holdings_df.groupby('Account')['Ending_Market_Value'].sum().reset_index()
    amount_invested_df.columns = ['Account', 'Amount Invested']

    #cash_df = st.session_state.fidelity.cash_df.get()
    cash_df = get_df("cash", engine=engine, ttl=60)
    # Calculate the cash amount in each account
    cash_amount_df = cash_df.groupby('Account')['Ending_Market_Value'].sum().reset_index()
    cash_amount_df.columns = ['Account', 'Cash Amount']

    # Calculate the Total amount
    total_amount_df = pd.DataFrame([], columns=['Account', 'Total Amount'])
    total_amount_df['Account'] = amount_invested_df['Account']
    total_amount_df['Total Amount'] = amount_invested_df['Amount Invested'] + cash_amount_df['Cash Amount']

    # Merge the two DataFrames
    merged_df = pd.merge(amount_invested_df, cash_amount_df, on='Account', how='left')
    merged_df = pd.merge(merged_df, total_amount_df, on='Account', how='left')
    merged_df.fillna(0, inplace=True)  # Fill NaN values with 0

    return merged_df

def plot_investment(container, engine):
    df = get_cash_and_stock(engine)
    if df.empty:
        return
    plot_stacked_bar_chart(container, None, df, 'Account',['Amount Invested','Cash Amount'],'Investment Holdings','Account','Value',{'Total Amount': True})

def plot_returns(container):
    benchmark = Benchmark()
    #TODO: Create benchmark table
    df = benchmark.get_df()
    df['Date'] = pd.to_datetime(df['Date'])
    fig = px.line(df, x='Date', y=['Balance', 'SPY Market Value'], title='Cumulative Returns vs. Benchmark')
    fig.update_layout(xaxis_title='Date', yaxis_title='Cumulative Returns')
    with container:
        st.plotly_chart(fig)
    
def plot_balance_history_old(account, container):
    #if 'INDIVIDUAL' in account.upper():
    if True:
        growth_data = call_api(endpoint=f"/accounts/{account.upper()}/balance/history",
                        method="GET")
        if len(growth_data) == 0:
            return
        dividends_data = call_api(endpoint="/accounts/dividends/balance/history",
                        method="GET")
        # Convert both lists to DataFrames
        df_growth = pd.DataFrame(growth_data)
        df_dividends = pd.DataFrame(dividends_data)

        # Ensure date columns are datetime
        df_growth['date'] = pd.to_datetime(df_growth['date'])
        df_dividends['date'] = pd.to_datetime(df_dividends['date'])

        # Rename balance columns
        df_growth = df_growth.rename(columns={"balance": "growth_balance"})
        df_dividends = df_dividends.rename(columns={"balance": "dividends_balance"})

        # Merge on date
        merged_df = pd.merge(df_growth, df_dividends, on='date', how='outer').fillna(0)

        # Calculate total balance
        merged_df['balance'] = merged_df['growth_balance'] + merged_df['dividends_balance']

        # Sort by date
        merged_df = merged_df.sort_values('date')

    #else:
    #    data = call_api(endpoint=f"/accounts/{account.upper()}/balance/history",
    #                    method="GET")
    #    if len(data) == 0:
    #        return
    #    # Convert to DataFrame
    #    merged_df = pd.DataFrame(data)
    #    merged_df['date'] = pd.to_datetime(merged_df['date'])
    #    # Group by date and sum balances
    #    merged_df = merged_df.groupby("date", as_index=False).sum()

    # Sort by date
    merged_df = merged_df.sort_values('date')

    # Plot total balance history
    fig = px.line(
        merged_df,
        x='date',
        y='balance',
        title=f'Balance History ({account.upper()})',
        markers=True
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Balance ($)', hovermode='x unified')

    with container:
        # Streamlit render
        st.plotly_chart(fig, use_container_width=True)
        merged_df = pd.DataFrame()

def plot_balance_history(account, container):
    data = call_api(endpoint=f"/accounts/{account.upper()}/balance/history", method="GET")
    if len(data) == 0:
        return
    # Convert to DataFrame
    merged_df = pd.DataFrame(data)
    merged_df['date'] = pd.to_datetime(merged_df['date'])
    # Group by date and sum balances
    merged_df = merged_df.groupby("date", as_index=False).sum()

    # Sort by date
    merged_df = merged_df.sort_values('date')

    # Plot total balance history
    fig = px.line(
        merged_df,
        x='date',
        y='balance',
        title=f'Balance History ({account.upper()})',
        markers=True
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Balance ($)', hovermode='x unified')

    with container:
        # Streamlit render
        st.plotly_chart(fig, use_container_width=True)
        merged_df = pd.DataFrame()

def plot_balance_history_animated(account, container):
    data = call_api(endpoint=f"/accounts/{account.upper()}/balance/history", method="GET")
    if len(data) == 0:
        return
    df = pd.DataFrame(data)
    if df.empty:
        return
    df['date'] = pd.to_datetime(df['date'])
    df = df.groupby("date", as_index=False).sum().sort_values('date')

    if df.empty:
        return

    df['year'] = df['date'].dt.year
    df = (
        df.sort_values('date')
          .groupby('year', as_index=False)
          .agg({'balance': 'last'})
    )

    if df.empty:
        return

    max_points = 100
    if len(df) > max_points:
        df = df.tail(max_points).reset_index(drop=True)

    raw_time_remaining = 2071 - df['year']
    target_year_remaining = 2071 - 2025
    start_remaining = raw_time_remaining.iloc[0]
    remaining_range = max(start_remaining - target_year_remaining, 1)

    normalized_time = target_year_remaining + (
        (raw_time_remaining - target_year_remaining) *
        (100 - target_year_remaining) /
        remaining_range
    )
    normalized_time = normalized_time.clip(lower=target_year_remaining, upper=100)

    df['time_remaining'] = normalized_time
    df['normalized_balance'] = df['balance'] / 100000  # keep scale comparable to normalized time
    df['year_label'] = df['year'].astype(str)

    categories = ["Time Remaining (Normalized)", "Balance"]
    colors = ["#2F9E44", "#4C6EF5"]

    initial_values = [df['time_remaining'].iloc[0], df['normalized_balance'].iloc[0]]
    base_trace = go.Bar(x=categories, y=initial_values, marker_color=colors)

    frames = []
    slider_steps = []
    for _, row in df.iterrows():
        frame_name = row['year_label']
        frame_trace = go.Bar(
            x=categories,
            y=[row['time_remaining'], row['normalized_balance']],
            marker_color=colors
        )
        frames.append(go.Frame(data=[frame_trace], name=frame_name))
        slider_steps.append({
            "args": [[frame_name], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}],
            "label": frame_name,
            "method": "animate",
        })

    fig = go.Figure(data=[base_trace], frames=frames)
    fig.update_layout(
        title="Balance vs. Time To 2071",
        xaxis_title="Metric",
        yaxis_title="Value (Balance in $100k)",
        yaxis=dict(range=[0, 100]),
        hovermode="closest",
        updatemenus=[{
            "type": "buttons",
            "showactive": False,
            "y": 1.15,
            "x": 1,
            "xanchor": "right",
            "yanchor": "top",
            "buttons": [
                {
                    "label": "Play",
                    "method": "animate",
                    "args": [None, {"frame": {"duration": 400, "redraw": True}, "fromcurrent": True}],
                },
                {
                    "label": "Pause",
                    "method": "animate",
                    "args": [[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}],
                },
            ],
        }],
        sliders=[{
            "pad": {"t": 30},
            "currentvalue": {"prefix": "Year: "},
            "steps": slider_steps,
        }],
    )

    with container:
        st.plotly_chart(fig, use_container_width=True)
    df = pd.DataFrame()
        
def plot_account_value(container):
    accounts_response = call_api("/accounts")
    if len(accounts_response) == 0:
        return
    df = pd.DataFrame(accounts_response)
    df = df[['account','total_value']]
    df.columns = ['Account', 'Balance']
    plot_pie_chart(container, "📊 Account Balances Distribution", df["Account"], df["Balance"], 0.5)
        
def plot_income(container, engine):
    #sbs_dioi = st.session_state.sbs_dioi.get()[st.session_state.sbs_dioi.get()['Description'].str.contains('Dividend|Interest', case=False, na=False)]
    #sbs_dioi = st.session_state.fidelity.sbs_dioi.get()
    sbs_dioi = get_df("sbs_dioi", engine=engine, ttl=60, parse_dates=["Date"])
    if sbs_dioi.empty:
        return
    sbs_dioi['Year'] = sbs_dioi['Date'].dt.year
    sbs_dioi = sbs_dioi[sbs_dioi['Description'].str.contains('Dividend')]
    aggregated_df = sbs_dioi.groupby(['Year', 'Account'])['Amount'].sum().reset_index()
    plot_stacked_bar_chart(container,'Account',aggregated_df,'Year','Amount','Total Income by Year and Account','Year','Amount',hover_data=None)
        
def plot_unrealized_gain_loss(container, engine):
    #df = st.session_state.fidelity.holdings_df.get()
    df = get_df("holdings_view", engine=engine, ttl=60)
    if df.empty:
        return
    df = df.groupby('Account').agg({
        "Unrealized_Gain/Loss": "sum"
    }).reset_index()

    fig = px.bar(df, x='Account', y='Unrealized_Gain/Loss', color='Account', title='Unrealized Gains/Loss by Account', labels={'Unrealized Gain/Loss': 'Unrealized Gain/Loss', 'Account': 'Account'}, color_discrete_sequence=colors)
    with container:
        st.plotly_chart(fig)
        
def plot_realized_gain_loss(container):
    df_list = []
    for account in accounts:
        for year in list(range(2017,2025)):
            api_uri = f"/tax/gains/realized?account={account.upper()}&year={year}"
            realized_gain = call_api(api_uri)
            row = [account.upper(), year, realized_gain['gains']]
            df_list.append(row)
        
    aggregated_df = pd.DataFrame(df_list, columns=['Account','Year','Amount'])  
    aggregated_df['Total'] = aggregated_df.groupby('Year')['Amount'].transform('sum')

    fig = px.bar(
        aggregated_df,
        x='Year',
        y='Amount',
        color='Account',
        title='Realized Gain/Loss by Year and Account',
        labels={'Amount': 'Amount', 'Year': 'Year'},
        hover_data={
            'Account': True,  # Show the account name
            'Amount': True,   # Show the individual account's amount
            'Total': True  # Show the total amount for the year
        }
    )
    with container:
        st.plotly_chart(fig)  
       
def plot_balances(container, engine):
    combined_df = train_model(st.session_state.projection_period, engine)

    # Split the data into historical and projected
    #latest_date = st.session_state.fidelity.balances.get()['Date'].max()
    latest_date = get_df("balances", engine=engine, ttl=60, parse_dates=["Date"])['Date'].max()
    if df.empty:
        return
    #latest_date = pd.to_datetime('today').normalize()
    historical_df = combined_df[combined_df['Date'] <= latest_date]
    projected_df = combined_df[combined_df['Date'] > latest_date]

    # Create the figure
    fig = go.Figure()

    # Add historical data as a solid line
    fig.add_trace(go.Scatter(
        x=historical_df['Date'],
        y=historical_df['Balance'],
        mode='lines+markers',
        name='Historical Balance',
        line=dict(color='blue', dash='solid')  # Solid line
    ))

    # Add projected data as a dotted line
    fig.add_trace(go.Scatter(
        x=projected_df['Date'],
        y=projected_df['Balance'],
        mode='lines+markers',
        name='Projected Balance',
        line=dict(color='red', dash='dot'),  # Dotted line
        marker=dict(size=2)
    ))

    # Add annotation for the latest balance
    latest_projected_date = projected_df['Date'].max()
    #latest_balance = projected_df.loc[projected_df['Date'] == latest_projected_date, 'Balance'].values[0]
    latest_balance = projected_df.loc[projected_df['Date'] == pd.to_datetime('today').normalize(), 'Balance'].values[0]
    fig.add_annotation(
        x=latest_projected_date,
        y=latest_balance,
        text=f"Latest Balance: {latest_balance:,.2f}",
        showarrow=True,
        arrowhead=2,
        ax=0,
        ay=-40,
        font=dict(size=12)
    )

    # Update layout
    fig.update_layout(
        title='Balance with Trendline and Projections',
        xaxis_title='Date',
        yaxis_title='Balance',
        legend_title='Legend'
    )

    with container:
        # Display the chart
        st.plotly_chart(fig)
         
# Expenses        
def plot_category_growth(category, container, txn_container):
    #df = df.copy()
    #df['Date'] = pd.to_datetime(df['Date'])

    #if category != 'all':
    #    df = df[df['Category'] == category].copy()

    #df['Year'] = df['Date'].dt.year
    df = pd.DataFrame(call_api(f"/credit/category/annual?category={category}"), columns=['Year', 'Amount'])
    yearly_cat = df.groupby('Year', as_index=False)['Amount'].sum()

    fig = px.bar(
        yearly_cat,
        x='Year',
        y='Amount',
        title=f'{category} Amount by Year',
        labels={'Amount': 'Total Amount'},
        text='Amount'
    )

    fig.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')

    with container:
        st.plotly_chart(fig, use_container_width=True)
    
        #if show_txns:
        #st.write("Category Filter")
        #if 'unbilled_txns' in st.session_state:
        #    df = safe_concat(df, st.session_state.unbilled_txns)
        #show_category_df(df, category, txn_container)

def plot_merchant_growth(merchant, container, txn_container):
    #df = df.copy()
    #df['Date'] = pd.to_datetime(df['Date'])
    #merch_df = df[df['Description'] == merchant].copy()

    #merch_df['Year'] = merch_df['Date'].dt.year
    #yearly_cat = merch_df.groupby('Year', as_index=False)['Amount'].sum()
    yearly_cat = pd.DataFrame(call_api(f"/credit/merchant/annual?merchant={merchant}"), columns=['Year', 'Amount'])

    fig = px.bar(
        yearly_cat,
        x='Year',
        y='Amount',
        title=f'{merchant} Amount by Year',
        labels={'Amount': 'Total Amount'},
        text='Amount'
    )

    fig.update_traces(texttemplate='%{text:.2s}', textposition='outside')
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide')
    with container:
        st.plotly_chart(fig, use_container_width=True)
        #if show_txns:
        #st.write("Merchant Filter")
        #if 'unbilled_txns' in st.session_state:
        #    df = safe_concat(df, st.session_state.unbilled_txns)
        #show_merchant_df(df, merchant, txn_container)

def plot_total_expenses(container):
    #df = df.copy()
    # Ensure Date is a datetime if needed
    #df['Date'] = pd.to_datetime(df['Date'])

    # Aggregate the data by expense Category
    #agg_df = df.groupby('Category').agg(
    #    total_amount=('Amount', 'sum'),
    #    transaction_count=('Amount', 'count'),
    #    average_amount=('Amount', 'mean')
    #).reset_index()
    agg_df = pd.DataFrame(call_api("/credit/category/mean"), 
                          columns=['Category', 'total_amount', 'transaction_count','average_amount'])

    # Create the bubble chart:
    # - x-axis: Average transaction amount per category
    # - y-axis: Total amount spent per category
    # - Bubble size: Number of transactions (transaction_count)
    # - Bubble color: Category
    fig = px.scatter(
        agg_df,
        x='average_amount',
        y='total_amount',
        size='transaction_count',
        color='Category',
        hover_name='Category',
        size_max=60,
        title='Credit Card Spending by Expense Category'
    )

    with container:
        st.plotly_chart(fig, theme="streamlit", use_container_width=True)
        
def plot_monthly_expenses(container):
    #df = df.copy()
    #df = df[df['Category'] != 'Education']
    #df['Date'] = pd.to_datetime(df['Date'])
    #df['YearMonth'] = df['Date'].dt.to_period('M').dt.to_timestamp()

    # Group by YearMonth and Category, summing the amounts:
    #agg_df = df.groupby(['YearMonth', 'Category'], as_index=False)['Amount'].sum()
    agg_df = pd.DataFrame(call_api("/credit/category/agg"), columns=['YearMonth', 'Category', 'Amount'])

    # Create a multi-line chart:
    fig = px.line(
        agg_df,
        x='YearMonth',
        y='Amount',
        color='Category',
        markers=True,
        title='Monthly Spending Trends by Category'
    )

    with container:
        st.plotly_chart(fig)

def plot_annual_expenses(container, txn_container):
    #df = df.copy()
    #df = df[(df['Category'] != 'Education') & (df['Category'] != 'Debt Payments')]
    # Group spending by Year and Category
    #grouped = df.groupby(['Year', 'Category'])['Amount'].sum().reset_index()
    grouped = pd.DataFrame(call_api("/credit/category/annual"), columns=['Year', 'Category', 'Amount'])
    
    # Create the bar chart
    fig = px.bar(
        grouped,
        x='Year',
        y='Amount',
        color='Category',
        color_discrete_sequence=colors,
        title='Annual Expenses',
        labels={'Amount': 'Total Amount', 'Year': 'Year'},
        text_auto=True,
        #height=1000
    )

    # Improve layout with hover and spike lines for better interactivity
    fig.update_layout(
        barmode='relative',
        hovermode='x',
        yaxis=dict(
            showspikes=True,
            spikemode='across',
            spikesnap='cursor',
            spikedash='dot',
            spikecolor='gray',
            spikethickness=1
        )
    )
    fig.update_traces(hovertemplate=None, hoverinfo='all')
    
    # Compute the total spending per year across all categories
    total_grouped = grouped.groupby('Year', as_index=False)['Amount'].sum()
    
    # Add the trace line overlay:
    fig.add_trace(
        go.Scatter(
            x=total_grouped['Year'],
            y=total_grouped['Amount'],
            mode='lines+markers',
            name='Total Spending',
            #line=dict(color='black', width=3),
            marker=dict(size=8)
        )
    )
    with container:
        st.plotly_chart(fig)

    #with txn_container:
    #    #if show_txns:
    #    st.write("Filter Year")
    #    if 'unbilled_txns' in st.session_state:
    #        df = safe_concat(df, st.session_state.unbilled_txns)
    #    show_annual_category_df(df, txn_container)

def show_category_df(df, category, category_growth):
    with category_growth:
        df = df.copy()
        # Print data matching the chart
        if category == 'all':
            if st.session_state.selected_year == 'all':
                result_df = df
            else:
                result_df = df[df['Date'].dt.year == int(st.session_state.selected_year)]
        else:
            if st.session_state.selected_year == 'all':
                result_df = df[df['Category'] == category]
            else:
                result_df = df[(df['Category'] == category) & (df['Date'].dt.year == int(st.session_state.selected_year))]

        result_df = result_df[['Date', 'Description', 'Amount', 'Category', 'Account']]
        result_df = result_df.sort_values(by='Date', ascending=False)
        icons = {
            "Debt Payments": "💳",
            "Food & Dining": "🍽️",
            "Tax": "🧾",
            "Housing": "🏠",
            "Utilities": "🔌",
            "Healthcare": "��",
            "Miscellaneous": "📦",
            "Transportation": "🚗",
            "Travel": "✈️",
            "Subscription": "🔄",
            "Entertainment": "🎮",
            "Shopping": "🛍️",
            "Insurance": "🛡️",
            "Personal Care": "🧴",
            "Education": "🎓"
        }
        result_df["Icon"] = result_df["Category"].map(icons)
        result_df.reset_index(drop=True, inplace=True)
        styled_df = result_df.style.map(color_balance, subset=['Amount']).format({result_df.columns[2]: "{:.2f}",'Date': lambda t: t.strftime('%m/%d/%Y')}) #.highlight_max(axis=0)
        st.dataframe(styled_df, height=1000, width=800)
        
def show_merchant_df(df, merchant, container):
    df = df.copy()
    # Print data matching the chart
    if st.session_state.selected_year == 'all':
        result_df = df[df['Description'] == merchant]
    else:
        result_df = df[(df['Description'] == merchant) & (df['Date'].dt.year == int(st.session_state.selected_year))]
    result_df = result_df[['Date', 'Description', 'Amount', 'Category', 'Account']]
    result_df = result_df.sort_values(by='Date', ascending=False)
    #styled_df = result_df.style.format({result_df.columns[2]: "{:.2f}"}) #.highlight_max(axis=0)
    styled_df = result_df.style.map(color_balance, subset=['Amount']).format({result_df.columns[2]: "{:.2f}",'Date': lambda t: t.strftime('%m/%d/%Y')}) #.highlight_max(axis=0)
    with container:
        st.dataframe(styled_df, height=1000, width=800)
        
def plot_expense_growth(container):
    df = df.copy()
    df = df[(df['Category'] != 'Education') & (df['Category'] != 'Debt Payments')]
    df = df[~((df['Category'] == 'Tax') & (df['Account'] == 'cash'))]
    # Remove transactions for current year
    current_year = datetime.today().year
    df = df[df['Date'].dt.year != current_year]
    
    # Convert Date column to datetime and extract the year
    df['Date'] = pd.to_datetime(df['Date'])
    df['Year'] = df['Date'].dt.year

    # Group by Year to calculate total expenses per year
    yearly_expenses = df.groupby('Year', as_index=False)['Amount'].sum()
    yearly_expenses = yearly_expenses.sort_values('Year')

    # Calculate annual growth rate (percentage change)
    yearly_expenses['Growth Rate'] = yearly_expenses['Amount'].pct_change() * 100

    # Create a Plotly figure with two y-axes
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add a bar chart for total expenses (primary y-axis)
    fig.add_trace(
        go.Bar(
            x=yearly_expenses['Year'],
            y=yearly_expenses['Amount'],
            name='Total Expenses'
        ),
        secondary_y=False
    )

    # Add a line chart for annual growth rate (secondary y-axis)
    fig.add_trace(
        go.Scatter(
            x=yearly_expenses['Year'],
            y=yearly_expenses['Growth Rate'],
            mode='lines+markers',
            name='Annual Growth Rate',
            marker=dict(color='red')
        ),
        secondary_y=True
    )

    # Update layout
    fig.update_layout(
        title_text="Annual Expenses and Growth Rate",
        xaxis_title="Year",
    )

    # Set y-axis titles for both axes
    fig.update_yaxes(title_text="Total Expenses", secondary_y=False)
    fig.update_yaxes(title_text="Annual Growth Rate (%)", secondary_y=True)

    with container:
        # Display in Streamlit
        st.plotly_chart(fig)
       

     
def show_annual_category_df(df, container):
    df = df.copy()

    # Configure grid options
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_column('Amount', type=['numericColumn'], aggFunc='sum')
    #gb.configure_column('Category', rowGroup=True, hide=True)
    gb.configure_pagination(paginationAutoPageSize=False)
    gb.configure_default_column(filter=True, sortable=True, resizable=True)
    gb.configure_selection('single')
    gb.configure_side_bar()
    gb.configure_default_column(enableRowGroup=True)
    #gb.configure_grid_options(groupIncludeFooter=True, groupIncludeTotalFooter=True)
    gb.configure_grid_options(domLayout='normal', groupIncludeTotalFooter=True)
    grid_options = gb.build()

    # Display the grid with returnMode and updateMode
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.NO_UPDATE,  # <-- prevents re-running on filter
        allow_unsafe_jscode=True,
        theme='streamlit',
        enable_enterprise_modules=True
    )

    # Access filtered data if needed
    filtered_df = grid_response['data']

def plot_current_month_category(container):
    # Copy data and filter out the 'Education' category
    #df = df.copy()
    #unbilled_df = st.session_state.unbilled_txns.copy()
    #df = safe_concat(df, unbilled_df)

    now = datetime.now()
    current_year = now.year
    #current_month = now.month
    #df = df[(df['Date'].dt.year == current_year) & (df['Date'].dt.month == current_month)]

    # Group spending by Year and Category
    #grouped = df.groupby(['Category'])['Amount'].sum().reset_index()
    grouped_dict = call_api(f"/credit/category/total?interval=monthly&month=0&year={current_year}")
    if len(grouped_dict) == 0:
        return
    grouped = pd.DataFrame(grouped_dict, columns=['Category', 'Amount'])
 
    color_map = {
        'Housing': 'green',
        'Insurance': 'red',
        'Transportation': 'aqua',
        'Food & Dining': 'purple',
        'Utilities': 'orange',
        'Healthcare':'brown',
        'Subscription': 'pink',
        'Entertainment': 'gray',
        'Shopping': 'olive',
        'Personal Care': 'cyan',
        'Travel': 'azure',
        'Debt Payments': 'blue',
        'Tax': 'burlywood',
        'Education': 'chartreuse',
        'Miscellaneous': 'coral'
    }   

    # Create the bar chart
    fig = px.bar(
        grouped,
        x='Category',
        y='Amount',
        color='Category',
        color_discrete_map=color_map,
        title='Current Month Spending',
        labels={'Amount': 'Amount', 'Category': 'Category'},
        text_auto=True,
        #height=1000
    )

    with container:
        st.plotly_chart(fig)

def plot_past_month_category(container):
    # Copy data and filter out the 'Education' category
    #df = df.copy()
    #if st.session_state.selected_year == 'all':
    #    df = df[df['Year'] == datetime.now().year]
    #else:
    #    df = df[df['Year'] == int(st.session_state.selected_year)]
    #df = df[df['Date'].dt.month == int(st.session_state.selected_month)]
    #grouped = df.groupby(['Category'])['Amount'].sum().reset_index()
    now = datetime.now()
    current_year = now.year
    past_month = now.month - 1
    grouped_dict = call_api(f"/credit/category/total?interval=monthly&month={past_month}&year={current_year}")
    grouped = pd.DataFrame(grouped_dict)    
    if grouped.empty:
        return

    plot_pie_chart(container, f"{st.session_state.selected_month}/{st.session_state.selected_year} Categories", grouped['Category'], grouped['Amount'], 0.5)

def plot_backtest_old(container, engine):
    #sbs_df = st.session_state.fidelity.sbs_dioi.get()
    sbs_df = get_df("sbs_dioi", engine=engine, ttl=60, parse_dates=["Date"])
    if sbs_df.empty:
        return
    #TODO: Create spy_max_from_perplexity table
    spy_df = st.session_state.fidelity.spy_max_from_perplexity_df.get()
    #TODO: Create holdings_history table
    holdings_df = st.session_state.fidelity.holdings_history_df

    # Ensure numeric conversion
    sbs_df["Amount"] = pd.to_numeric(sbs_df["Amount"], errors="coerce")
    sbs_df = sbs_df.dropna(subset=["Amount"])
    sbs_df["Date"] = pd.to_datetime(sbs_df["Date"])
    sbs_df = sbs_df.sort_values("Date")

    # Clean SPY
    spy_df = spy_df.rename(columns=lambda x: x.strip().lower())
    if "close" not in spy_df.columns:
        st.error("SPY.csv must have a 'Close' column.")
        st.stop()
    spy_df["date"] = pd.to_datetime(spy_df["date"])
    spy_df.set_index("date", inplace=True)
    spy_df = spy_df[["close"]].rename(columns={"close": "SPY_Close"})

    # Build SPY portfolio simulation
    cashflow = sbs_df.groupby("Date")["Amount"].sum().rename("Cashflow")
    all_dates = pd.date_range(start=sbs_df["Date"].min(), end=spy_df.index.max())
    timeline = pd.DataFrame(index=all_dates)
    timeline.index = pd.to_datetime(timeline.index).normalize()

    # Join SPY and cashflow
    timeline = timeline.join(spy_df).join(cashflow).fillna({"Cashflow": 0})
    timeline["SPY_Close"].ffill(inplace=True)
    timeline = timeline.dropna(subset=["SPY_Close"])

    # ✅ FIX: Reverse cashflow sign to simulate investing in SPY
    timeline["Adjusted_Cashflow"] = -timeline["Cashflow"]

    # Simulate SPY investment
    spy_units = 0
    spy_value = []
    st.write(timeline[["Cashflow", "Adjusted_Cashflow"]].head(30))
    st.write(timeline[["Cashflow", "Adjusted_Cashflow"]].tail(30))
    for i in timeline.itertuples():
        if pd.notna(i.SPY_Close) and i.SPY_Close > 0:
            if i.Adjusted_Cashflow != 0:
                spy_units += i.Adjusted_Cashflow / i.SPY_Close
        spy_value.append(spy_units * i.SPY_Close)
    st.write("Final SPY units:", spy_units)
    st.write("Final SPY value:", spy_value[-1])
    timeline["SPY_Value"] = spy_value

    # Actual portfolio value from holdings snapshots
    holdings_df["Ending_Market_Value"] = (
        holdings_df["Ending_Market_Value"]
        .replace("unavailable", np.nan)
        .replace(r"[\$,]", "", regex=True)
        .astype(float)
    )
    holdings_df["Date"] = pd.to_datetime(holdings_df["Date"])
    portfolio_snapshots = (
        holdings_df.groupby("Date")["Ending_Market_Value"]
        .sum()
        .rename("MyPortfolio")
    )
    portfolio_snapshots.index = pd.to_datetime(portfolio_snapshots.index).normalize()
    timeline.index.name = "Date"
    timeline = timeline.join(portfolio_snapshots)
    timeline["MyPortfolio"].ffill(inplace=True)

    st.write("Cashflow stats:")
    st.write(timeline["Cashflow"].describe())
    st.write("Adjusted_Cashflow stats:")
    st.write(timeline["Adjusted_Cashflow"].describe())
    st.write("NaN SPY prices after join:", timeline["SPY_Close"].isna().sum())
    st.write(timeline[timeline["Cashflow"] != 0 & timeline["SPY_Close"].isna()])
    st.write("Unique SPY dates:", spy_df.index.unique().sort_values().to_list()[:5])
    st.write("Unique Cashflow dates:", sbs_df['Date'].unique().tolist()[:5])
    st.write("Timeline index sample:", timeline.index[:5])

    # Normalize to same starting point
    baseline_date = timeline["MyPortfolio"].first_valid_index()
    if baseline_date:
        baseline = timeline.loc[baseline_date]
        timeline["MyPortfolio_Norm"] = timeline["MyPortfolio"] / baseline.MyPortfolio * 100
        timeline["SPY_Value_Norm"] = timeline["SPY_Value"] / baseline.SPY_Value * 100

        with container:
            mode = st.radio(
                "Select View Mode",
                ["📊 Normalized Growth", "💵 Absolute Value"],
                index=0,
                horizontal=True
            )

            # Optional debug view
            st.write(timeline[["SPY_Close", "Cashflow", "Adjusted_Cashflow", "SPY_Value"]].head(10))
            st.write(timeline[["SPY_Close", "Cashflow", "Adjusted_Cashflow", "SPY_Value"]].tail(10))
            initial = timeline["SPY_Value"].iloc[0]
            final = timeline["SPY_Value"].iloc[-1]
            st.write("SPY return: {:.2f}%".format((final - initial) / initial * 100))

            st.subheader("Portfolio vs SPY (Stock Picking)")

            if mode == "📊 Normalized Growth":
                fig = px.line(
                    timeline.reset_index(),
                    x="Date",
                    y=["MyPortfolio_Norm", "SPY_Value_Norm"],
                    labels={"value": "Value", "variable": "Portfolio"},
                    title="Portfolio vs SPY (Normalized)"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                fig = px.line(
                    timeline.reset_index(),
                    x="Date",
                    y=["MyPortfolio", "SPY_Value"],
                    labels={"value": "Value ($)", "variable": "Portfolio"},
                    title="Portfolio vs SPY (Absolute Value)"
                )
                st.plotly_chart(fig, use_container_width=True)

def plot_backtest_chart(container, timeline):
    mode = st.radio("View Mode", ["📊 Normalized Growth", "💵 Absolute Value"], horizontal=True)
    with container:
        if mode == "📊 Normalized Growth":
            fig = px.line(
                timeline.reset_index(),
                x="Date",
                y=["MyPortfolio_Norm", "SPY_Value_Norm"],
                labels={"value": "Normalized Value", "variable": "Portfolio"},
                title="Portfolio vs SPY (Normalized)"
            )
        else:
            fig = px.line(
                timeline.reset_index(),
                x="Date",
                y=["MyPortfolio", "SPY_Value"],
                labels={"value": "Value ($)", "variable": "Portfolio"},
                title="Portfolio vs SPY (Absolute Value)"
            )
        st.plotly_chart(fig, use_container_width=True)

@st.cache_data
def load_and_clean_data(engine):
    #sbs_df = st.session_state.fidelity.sbs_dioi.get()
    sbs_df = get_df("sbs_dioi", engine=engine, ttl=60, parse_dates=["Date"])
    if sbs_df.empty:
        return
    sbs_df = sbs_df.sort_values('Date')
    #TODO: Create spy_max_from_perplexity table
    spy_df = st.session_state.fidelity.spy_max_from_perplexity_df.get()
    spy_df = spy_df.sort_values('Date')
    # TODO: Create holdings_history table
    holdings_df = st.session_state.fidelity.holdings_history_df

    sbs_df["Date"] = pd.to_datetime(sbs_df["Date"]).dt.normalize()
    sbs_df["Amount"] = pd.to_numeric(sbs_df["Amount"], errors="coerce")

    spy_df = spy_df.rename(columns=lambda x: x.strip().lower())
    spy_df["date"] = pd.to_datetime(spy_df["date"]).dt.normalize()
    spy_df = spy_df.set_index("date")[["close"]].rename(columns={"close": "SPY_Close"})

    holdings_df["Date"] = pd.to_datetime(holdings_df["Date"]).dt.normalize()
    holdings_df["Ending_Market_Value"] = (
        holdings_df["Ending_Market_Value"]
        .replace("unavailable", np.nan)
        .replace(r"[\$,]", "", regex=True)
        .astype(float)
    )

    debug_log("✅ Cleaned SBS DF:", sbs_df.head())
    debug_log("✅ Cleaned SPY DF (index):", spy_df.index[:5])
    debug_log("✅ Holdings DF:", holdings_df.head())

    return sbs_df, spy_df, holdings_df

@st.cache_data
def build_timeline(sbs_df, spy_df):
    all_dates = pd.date_range(start=sbs_df["Date"].min(), end=spy_df.index.max())
    timeline = pd.DataFrame(index=all_dates)
    timeline.index.name = "Date"

    timeline = timeline.join(spy_df)
    timeline["SPY_Close"].ffill(inplace=True)

    cashflow = sbs_df.groupby("Date")["Amount"].sum().rename("Cashflow")
    timeline = timeline.join(cashflow)
    timeline["Cashflow"].fillna(0, inplace=True)

    debug_log("📊 Timeline (SPY+Cashflow):", timeline.head(10))
    debug_log("🚫 Cashflow with missing SPY:", timeline[timeline["Cashflow"] != 0 & timeline["SPY_Close"].isna()])

    return timeline

@st.cache_data
def simulate_spy_portfolio(timeline):
    spy_units = 0
    values = []
    for row in timeline.itertuples():
        if pd.notna(row.SPY_Close) and row.SPY_Close > 0:
            if row.Cashflow != 0:
                spy_units += row.Cashflow / row.SPY_Close
            values.append(spy_units * row.SPY_Close)
        else:
            values.append(np.nan)
    timeline["SPY_Value"] = values
    debug_log("📈 Simulated SPY Value (head):", timeline[["Cashflow", "SPY_Close", "SPY_Value"]].head(10))
    debug_log("📈 Simulated SPY Value (tail):", timeline[["Cashflow", "SPY_Close", "SPY_Value"]].tail(10))
    return timeline

@st.cache_data
def add_real_portfolio(timeline, holdings_df):
    real_portfolio = (
        holdings_df.groupby("Date")["Ending_Market_Value"]
        .sum()
        .rename("MyPortfolio")
    )
    timeline = timeline.join(real_portfolio)
    timeline["MyPortfolio"].ffill(inplace=True)
    debug_log("💼 Real Portfolio Snapshots:", timeline[["MyPortfolio"]].dropna().head(10))
    return timeline

@st.cache_data
def normalize_portfolios(timeline):
    valid = timeline[["MyPortfolio", "SPY_Value"]].dropna()
    if valid.empty:
        st.warning("No overlapping portfolio/SPY data to normalize.")
        return timeline
    baseline = valid.iloc[0]
    timeline["MyPortfolio_Norm"] = timeline["MyPortfolio"] / baseline.MyPortfolio * 100
    timeline["SPY_Value_Norm"] = timeline["SPY_Value"] / baseline.SPY_Value * 100
    debug_log("📊 Normalized values:", timeline[["MyPortfolio_Norm", "SPY_Value_Norm"]].dropna().head())
    st.write("Initial values used:", baseline.MyPortfolio, baseline.SPY_Value)
    return timeline

def plot_backtest(container, engine):
    sbs_df, spy_df, holdings_df = load_and_clean_data(engine)
    timeline = build_timeline(sbs_df, spy_df)
    timeline = simulate_spy_portfolio(timeline)
    timeline = add_real_portfolio(timeline, holdings_df)
    timeline = normalize_portfolios(timeline)
    plot_backtest_chart(container, timeline)
