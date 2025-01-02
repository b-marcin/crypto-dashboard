import os
import streamlit as st
import ccxt
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ------------------------------------------------------------------------------
# 1. Page Title
# ------------------------------------------------------------------------------
st.title("Crypto Dashboard with CMC Fear & Greed + TradingView-Like Signals")

# ------------------------------------------------------------------------------
# 2. User inputs and config
# ------------------------------------------------------------------------------

# You can store your API key in Streamlit secrets or environment variable:
# st.secrets["CMC_API_KEY"] or os.environ.get("CMC_API_KEY")
CMC_API_KEY = st.text_input("Enter your CMC API key", type="password")

# Exchange selection (binance by default)
exchange_name = "binance"

# Symbol selection
symbols = st.multiselect(
    "Select cryptos to analyze (vs USDT on Binance):",
    ["BTC/USDT", "ETH/USDT", "SOL/USDT", "AVAX/USDT"],
    default=["BTC/USDT", "ETH/USDT"]
)

# Date range for data
default_start = datetime.now() - timedelta(days=365)
start_date = st.date_input("Start Date", value=default_start)
end_date = st.date_input("End Date", value=datetime.now())
timeframe = st.selectbox("Timeframe", ["1d", "4h", "1h"], index=0)

# Use separate trend lengths for each asset, as in your script, or just a single input
st.write("Provide custom Trend Length for each symbol (from your TV script defaults):")
trend_length_btc = st.number_input("BTC Trend Length", value=93, min_value=1)
trend_length_eth = st.number_input("ETH Trend Length", value=158, min_value=1)
trend_length_sol = st.number_input("SOL Trend Length", value=238, min_value=1)
trend_length_avax = st.number_input("AVAX Trend Length", value=82, min_value=1)

# Map the user input to a dictionary for convenience
trend_lengths = {
    "BTC/USDT": trend_length_btc,
    "ETH/USDT": trend_length_eth,
    "SOL/USDT": trend_length_sol,
    "AVAX/USDT": trend_length_avax
}

# ATR parameters from your script
atr_period = 200
atr_multiplier = 0.8

# ------------------------------------------------------------------------------
# 3. Fetch Fear and Greed Index from CMC
# ------------------------------------------------------------------------------
def get_cmc_fear_and_greed(api_key: str, limit=1):
    """
    Fetch the latest Fear and Greed Index from CMC (limit=1 -> newest record).
    Using the endpoint from your snippet:
      GET https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical
    """
    url = "https://pro-api.coinmarketcap.com/v3/fear-and-greed/historical"
    headers = {
        "Accepts": "application/json",
        "X-CMC_PRO_API_KEY": api_key
    }
    params = {
        "limit": limit  # fetch 1 record for the latest
    }
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    return data

if CMC_API_KEY:
    try:
        fg_data = get_cmc_fear_and_greed(CMC_API_KEY, limit=1)
        # Example response structure:
        # {
        #   "status": {...},
        #   "data": [
        #       {
        #         "timestamp": "2024-09-02T12:00:00.000Z",
        #         "value": 50,
        #         "value_classification": "Neutral"
        #       }
        #   ]
        # }
        fg_value = fg_data["data"][0]["value"]
        fg_class = fg_data["data"][0]["value_classification"]
        timestamp_str = fg_data["data"][0]["timestamp"]
        
        st.subheader("Fear & Greed Index (CMC)")
        st.write(f"**Latest Value**: {fg_value} | **Classification**: {fg_class}")
        st.write(f"**Timestamp**: {timestamp_str}")
    except Exception as e:
        st.error(f"Unable to fetch Fear & Greed from CMC: {e}")
else:
    st.write("Enter your CMC API key above to fetch Fear & Greed Index data.")

# ------------------------------------------------------------------------------
# 4. Set up ccxt to fetch data
# ------------------------------------------------------------------------------
try:
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class({
        'enableRateLimit': True,
    })
except AttributeError:
    st.error(f"Exchange '{exchange_name}' is not supported by ccxt.")
    st.stop()

def fetch_ohlcv(symbol, timeframe, since, limit=1000):
    """
    Fetch OHLCV data from the given exchange using ccxt.
    since: a Unix timestamp in milliseconds
    """
    data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
    # data is in the format: [ [timestamp, open, high, low, close, volume], ... ]
    df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def date_to_milliseconds(d):
    return int(d.timestamp() * 1000)

# ------------------------------------------------------------------------------
# 5. TradingView script logic in Python (for each symbol)
# ------------------------------------------------------------------------------
def compute_signals(df: pd.DataFrame, trend_length: int):
    """
    Replicate the relevant parts of your TradingView script:
      atr_value = ta.sma(ta.atr(200), 200) * 0.8
      sma_high  = ta.sma(high, length) + atr_value
      sma_low   = ta.sma(low, length) - atr_value
      trend flips when close crosses sma_high or sma_low
    """
    # Sort by timestamp (just in case)
    df = df.sort_values("timestamp").copy().reset_index(drop=True)

    # 1) Compute ATR over atr_period=200
    #    a) True Range
    df["hl"]   = df["high"] - df["low"]
    df["h_pc"] = (df["high"] - df["close"].shift(1)).abs()
    df["l_pc"] = (df["low"] - df["close"].shift(1)).abs()
    df["TR"]   = df[["hl", "h_pc", "l_pc"]].max(axis=1)
    #    b) rolling mean of TR
    df["ATR"] = df["TR"].rolling(window=atr_period).mean()
    #    c) multiply by 0.8
    df["atr_value"] = df["ATR"] * atr_multiplier

    # 2) Compute sma_high and sma_low
    #    Rolling mean of "high" or "low" over "trend_length", then +/- atr_value
    df["sma_high"] = df["high"].rolling(window=trend_length).mean() + df["atr_value"]
    df["sma_low"]  = df["low"].rolling(window=trend_length).mean()  - df["atr_value"]

    # 3) Identify trend
    #    We'll store a boolean: True = uptrend, False = downtrend
    df["trend"] = None

    # We'll iterate row by row to replicate the cross logic
    # (Alternatively, you can do something more vectorized.)
    current_trend = False  # default
    for i in range(len(df)):
        if i == 0:
            df.at[i, "trend"] = current_trend
            continue
        prev_close = df.at[i-1, "close"]
        prev_sma_high = df.at[i-1, "sma_high"]
        prev_sma_low = df.at[i-1, "sma_low"]

        # cross above
        if (df.at[i, "close"] > df.at[i, "sma_high"]) and (prev_close <= prev_sma_high):
            current_trend = True
        # cross below
        elif (df.at[i, "close"] < df.at[i, "sma_low"]) and (prev_close >= prev_sma_low):
            current_trend = False

        df.at[i, "trend"] = current_trend

    df["trend"] = df["trend"].astype(bool)

    # 4) Signal up if "trend" changes from False to True
    df["signal_up"] = (df["trend"] != df["trend"].shift(1)) & (df["trend"] == True)

    # 5) Signal down if "trend" changes from True to False
    df["signal_down"] = (df["trend"] != df["trend"].shift(1)) & (df["trend"] == False)

    return df

# ------------------------------------------------------------------------------
# 6. For each selected symbol, fetch data, compute signals, plot
# ------------------------------------------------------------------------------
for sym in symbols:
    st.subheader(f"{sym} - {timeframe} data with signals")

    # Convert user dates to ms
    since_ms = date_to_milliseconds(datetime.combine(start_date, datetime.min.time()))
    # We might do multiple fetches if needed, but let's try a single fetch with limit=1000 or more
    # If you want more data, you might have to do some pagination logic in ccxt.
    df_symbol = fetch_ohlcv(sym, timeframe, since=since_ms, limit=2000)

    # Filter by the chosen end_date (ccxt may give you more than needed)
    df_symbol = df_symbol[df_symbol["timestamp"] <= pd.to_datetime(end_date)]

    # If there's insufficient data, skip
    if len(df_symbol) < atr_period:
        st.warning(f"Not enough data for {sym} to compute signals (need at least {atr_period} bars).")
        continue

    # Compute signals
    df_symbol = compute_signals(df_symbol, trend_lengths[sym])

    # Show tail of data
    st.dataframe(df_symbol.tail(5))

    # Plot with Plotly
    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df_symbol["timestamp"],
        open=df_symbol["open"],
        high=df_symbol["high"],
        low=df_symbol["low"],
        close=df_symbol["close"],
        name=sym
    ))

    buy_signals = df_symbol[df_symbol["signal_up"]]
    sell_signals = df_symbol[df_symbol["signal_down"]]

    fig.add_trace(go.Scatter(
        x=buy_signals["timestamp"],
        y=buy_signals["low"] * 0.99,
        mode="markers",
        marker=dict(symbol="triangle-up", color="green", size=12),
        name="Buy Signal"
    ))

    fig.add_trace(go.Scatter(
        x=sell_signals["timestamp"],
        y=sell_signals["high"] * 1.01,
        mode="markers",
        marker=dict(symbol="triangle-down", color="red", size=12),
        name="Sell Signal"
    ))

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        title=f"{sym} Price & Signals",
        height=600
    )

    st.plotly_chart(fig, use_container_width=True)

    # Optional additional metrics (just a sample)
    latest_close = df_symbol["close"].iloc[-1]
    latest_volume = df_symbol["volume"].iloc[-1]
    st.metric(label=f"{sym} Latest Close Price", value=round(latest_close, 2))
    st.metric(label=f"{sym} Latest Bar Volume", value=f"{int(latest_volume):,}")

# ------------------------------------------------------------------------------
# 7. Footer.
# ------------------------------------------------------------------------------
st.write("---")
st.write("""
**Notes / Next Steps**:
- This demo uses [ccxt](https://github.com/ccxt/ccxt) for fetching OHLCV data from Binance. 
- The Fear & Greed Index is fetched via the CoinMarketCap API. 
- The TradingView script logic (ATR-based trend detection) is replicated in Python using 
  rolling calculations and basic cross detection.
- Consider adding real-time updates, alerts, or integrated trade execution in the future.
""")
