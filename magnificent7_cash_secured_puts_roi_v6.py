import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px

# Function to format numbers
def fmt(x):
    return f"{x:.2f}" if isinstance(x, (float, int)) else x

# Get upcoming Fridays for expiration
def get_weekly_expirations(n=10):
    today = datetime.today()
    expirations = []
    for i in range(n):
        friday = today + timedelta((4 - today.weekday()) % 7 + i * 7)
        expirations.append(friday.strftime("%Y-%m-%d"))
    return expirations

# Streamlit App Layout
st.title("📊 Options Analyzer: Cash-Secured Puts & Covered Calls")

# Strategy selector
strategy = st.selectbox("Select Strategy", ["Cash Secured Put", "Covered Call"])

# User Inputs
min_price = st.number_input("Minimum Current Price", min_value=0.0, value=50.0)
max_price = st.number_input("Maximum Current Price", min_value=min_price, value=500.0)
moneyness_pct = st.selectbox("Moneyness %", [1, 2, 3, 4, 5, 10, 15, 20, 30])
expiration_list = get_weekly_expirations(8)

# Initial stock list and user input
magnificent7 = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA"]
etfs = ["SPY", "QQQ"]
all_stocks = magnificent7 + etfs
additional_tickers = st.text_input("➕ Add more tickers (comma separated)", "")

if additional_tickers:
    all_stocks.extend([t.strip().upper() for t in additional_tickers.split(",")])

unique_stocks = sorted(set(all_stocks))
tickers_list = ["ALL"] + unique_stocks
selected_stock = st.selectbox("Select Ticker or 'ALL'", tickers_list)

# Option analysis function
@st.cache_data(show_spinner=False)
def analyze_options(ticker, expirations, strategy, moneyness_pct, min_price, max_price):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="5d")
        current_price = hist["Close"].iloc[-1]
        if current_price < min_price or current_price > max_price:
            return []

        options_data = []
        for expiration in expirations:
            try:
                opt_chain = stock.option_chain(expiration)
                options = opt_chain.puts if strategy == "Cash Secured Put" else opt_chain.calls
                target_strike = round(current_price * (1 - moneyness_pct / 100) if strategy == "Cash Secured Put" else current_price * (1 + moneyness_pct / 100), 2)
                options_filtered = options[options["strike"] <= target_strike] if strategy == "Cash Secured Put" else options[options["strike"] >= target_strike]
                if options_filtered.empty:
                    continue
                selected = options_filtered.iloc[-1] if strategy == "Cash Secured Put" else options_filtered.iloc[0]
                strike_price = selected["strike"]
                premium = (selected["bid"] + selected["ask"]) / 2 if selected["bid"] and selected["ask"] else selected["lastPrice"]
                days_to_exp = (datetime.strptime(expiration, "%Y-%m-%d") - datetime.today()).days
                abs_roi = premium / strike_price * 100
                ann_roi = (abs_roi / days_to_exp) * 365 if days_to_exp > 0 else 0

                row = {
                    "Ticker": ticker,
                    "Strategy": strategy,
                    "Current Price": fmt(current_price),
                    "Strike Price": fmt(strike_price),
                    "Analyst Target": fmt(info.get("targetMeanPrice", 0.0)),
                    "Premium": fmt(premium),
                    "Days to Exp": days_to_exp,
                    "Abs ROI (%)": fmt(abs_roi),
                    "Ann ROI (%)": fmt(ann_roi),
                    "Div Yield": fmt(info.get("dividendYield", 0.0) * 100),
                    "Next Earnings": info.get("earningsDate", "N/A"),
                    "Recommendation": info.get("recommendationKey", "N/A"),
                    "EPS (TTM)": fmt(info.get("trailingEps", 0.0)),
                    "EPS Trend": "Beat" if info.get("earningsQuarterlyGrowth", 0) > 0 else "Miss",
                    "Overall Score": fmt(info.get("recommendationMean", 0.0)),
                    "Expiration": expiration,
                    "Sector": info.get("sector", "N/A"),
                    "Industry": info.get("industry", "N/A")
                }
                options_data.append(row)
            except Exception as e:
                continue
        return options_data
    except Exception as e:
        return []

# Ticker loop
if selected_stock == "ALL":
    tickers_to_process = unique_stocks
else:
    tickers_to_process = [selected_stock]

all_results = []
for tkr in tickers_to_process:
    results = analyze_options(tkr, expiration_list, strategy, moneyness_pct, min_price, max_price)
    all_results.extend(results)

# Display Data
if all_results:
    df = pd.DataFrame(all_results)
    df = df.sort_values(by="Ann ROI (%)", ascending=False)

    st.dataframe(df)

    st.subheader("📈 ROI Trend by Expiration")
    fig = px.line(df, x="Expiration", y="Ann ROI (%)", color="Ticker", markers=True)
    st.plotly_chart(fig)

    st.download_button("📥 Download CSV", df.to_csv(index=False), "options_analysis.csv", "text/csv")
else:
    st.warning("No data found for selected filters or strategy.")