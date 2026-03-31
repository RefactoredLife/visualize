# Visualize

`Visualize` is a personal finance intelligence platform focused on portfolio analytics, financial forecasting, expense intelligence, and interactive decision support.

It combines statement ingestion, portfolio analytics, expense intelligence, forecasting, and interactive dashboards into a single Streamlit application backed by APIs, databases, and observability tooling. The goal is to turn messy financial data into decision-grade software.

## Overview

The application is designed to:

- Building an end-to-end product instead of isolated notebooks or scripts
- Turning unstructured financial inputs into structured analytics
- Designing interactive decision-support dashboards for real users
- Connecting multiple data sources, APIs, and storage layers into one workflow
- Applying quantitative finance concepts to real portfolio and cash-flow questions
- Shipping with Docker, environment-driven config, caching, and telemetry

## App Features

### Portfolio Intelligence

- Net worth tracking across accounts
- Day gain monitoring and account-level performance views
- CAGR, holding period return, annual volatility, Sharpe ratio, and drawdown metrics
- Portfolio vs. benchmark style analysis and normalized performance tracking
- Unrealized and realized gain/loss views
- Tax-aware capital gains analysis across accounts and years
- Lot selection workflows to support more tax-efficient selling decisions
- Income analytics for dividends and interest
- Holdings breakdowns and account value visualizations

### Forecasting And Financial Modeling

- Monte Carlo simulation with configurable return, volatility, inflation, contribution, horizon, and seed inputs
- Long-range portfolio projection workflows
- Rule-of-72 style wealth compounding views
- "Years to billionaire" style scenario metrics
- Retirement modeling module for future income, withdrawals, taxes, expenses, and net worth

### Spending And Cash-Flow Analytics

- Expense categorization workflows
- Merchant-level and category-level spending analysis
- Monthly, annual, and trend-based expense dashboards
- Current-month and prior-month category comparison views
- Cash-flow and drawdown analytics
- Transaction-level exploration for spending behavior

### Document And Data Ingestion

- PDF statement import pipeline with progress polling
- Filename validation and chronological import ordering
- Support for processed balances, cash, holdings, transactions, and benchmark datasets
- Google Sheets integration for holdings and transaction workflows
- Gmail ingestion/parsing utilities for transaction-related emails and finance alerts

### GenAI / AI-Adjacent Engineering Signals

- Environment hooks for LLM providers and Google AI services
- NLP/AI-oriented dependency stack for enrichment and automation workflows
- Fuzzy matching and description normalization patterns for messy financial data
- A codebase structure that is ready for AI-assisted categorization, entity cleanup, and workflow orchestration

### Product And Platform Engineering

- Streamlit + Plotly interactive analytics UI
- MariaDB-backed user accounts and persisted notes
- Mongo-compatible utilities for historical document workflows
- API-first integration with a FastAPI-style backend
- In-process DataFrame caching for faster dashboard performance
- OpenTelemetry tracing for operational visibility
- Docker and Docker Compose deployment support

## Capabilities

This repository brings together several technical areas:

- GenAI engineering: structuring systems that can enrich, classify, and normalize noisy financial data
- Finance engineering: modeling returns, risk, benchmark comparisons, drawdowns, and retirement scenarios
- Data engineering: ingesting PDFs, spreadsheets, API payloads, and email-derived transactions
- Full-stack delivery: shipping a usable web app with authentication, storage, caching, and observability
- Product thinking: turning raw financial records into workflows that answer meaningful user questions

## User Experience

The application currently supports:

- A landing experience for unauthenticated users
- Account sign-up and login from the sidebar
- Statement upload and import progress tracking
- A configurable analytics sidebar for account, year, month, category, merchant, and projection controls
- Dashboard tabs for `Today`, `Investments`, `Expenses`, and `Transactions`

## Tech Stack

- Python
- Streamlit
- Plotly
- Pandas / NumPy / SciPy / scikit-learn
- SQLAlchemy + MariaDB
- MongoDB utilities
- Requests-based API integration
- Google Sheets APIs
- Gmail / IMAP parsing
- yFinance market data workflows
- OpenTelemetry
- Docker / Docker Compose

## Repository Structure

```text
.
├── app/
│   ├── common/
│   │   ├── config.py
│   │   ├── dbcache.py
│   │   └── utils.py
│   ├── modules/
│   │   ├── AdminMariaDB.py
│   │   ├── AdminMongo.py
│   │   ├── Benchmark.py
│   │   ├── CashFlow.py
│   │   ├── Financials.py
│   │   ├── Gmail.py
│   │   ├── GoogleSheets.py
│   │   ├── Income.py
│   │   ├── Options.py
│   │   ├── Plot.py
│   │   ├── Retirement.py
│   │   ├── Valuation.py
│   │   └── Welcome.py
│   └── visualize.py
├── .streamlit/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11+ or compatible local environment
- `pip`
- Docker and Docker Compose if you want containerized execution
- Access to the supporting environment variables used by the app
- A reachable backend API for the endpoints configured through `FASTAPI_BASE_URL`

### Local Setup

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Provide environment files or exported environment variables for your local setup.
5. Run the app:

```bash
streamlit run app/visualize.py
```

### Docker

Build and run the Streamlit app with Docker:

```bash
docker build -t visualize .
docker run -p 8501:8501 --env-file .env.visualize visualize
```

### Docker Compose

The repository also includes `docker-compose.yml` for a fuller environment-driven setup:

```bash
docker compose up --build
```

The compose file expects supporting env files such as:

- `.env.google`
- `.env.mariadb`
- `.env.mongodb`
- `.env.visualize`

## Configuration Notes

The app is heavily environment-driven. Important configuration areas include:

- Finance data paths and processed CSV locations
- FastAPI base URL and API key
- MariaDB connection settings
- Google service account credentials
- Gmail/IMAP credentials
- Account mappings and external account metadata
- Optional observability and tracing endpoints

Most of this wiring is centralized in `app/common/config.py`.

## Example Product Questions This App Can Answer

- How is my portfolio performing versus its long-term growth rate?
- What is my current net worth across all tracked accounts?
- How volatile is my portfolio, and what has the worst drawdown been?
- Which lots should I sell to reduce realized gains or improve tax efficiency?
- How are my spending categories changing year over year?
- Which merchants are driving the most expense growth?
- What does my financial future look like under different return assumptions?
- How sustainable is my current retirement path?

## Summary

`Visualize` is a full-stack financial intelligence product for transforming raw financial records into structured analytics, forecasts, and decision-support dashboards. It combines data ingestion, quantitative modeling, user-facing visualization, and production-oriented infrastructure in one application.
