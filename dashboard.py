import streamlit as st
import pandas as pd
import requests
import yfinance as yf
from plotly import graph_objects as go

# Set page title
st.set_page_config(page_title='Crypto Trading Dashboard')

# Header
st.title('Crypto Trading Dashboard')

# Fetch Crypto Fear and Greed Index
st.subheader('Crypto Fear & Greed Index')
fg_url = 'https://api.alternative.me/fng/?limit=0'
fg_response = requests.get(fg_url)
fg_data = fg_response.json()
fg_df = pd.DataFrame(fg_data['data'])
fg_df['value'] = fg_df['value'].astype(int)
fg_df['timestamp'] = pd.to_datetime(fg_df['timestamp'], unit='s')

# Plot Fear and Greed Index
fig_fg = go.Figure()
fig_fg.add_trace(go.Scatter(x=fg_df['timestamp'], y=fg_df['value'], name='Fear & Greed Index'))
fig_fg.update_layout(title='Crypto Fear & Greed Index Over Time',
                     xaxis_title='Date',
                     yaxis_title='Index Value')
st.plotly_chart(fig_fg)

# Fetch price data for selected cryptocurrencies
tickers = ['BTC-USD', 'ETH-USD', 'SOL-USD', 'AVAX-USD']
data = yf.download(tickers, period="1y", interval="1d")

# Price and Volume Charts
st.subheader('Price and Volume Charts')
selected_crypto = st.selectbox('Select Cryptocurrency', tickers)
df = data.loc[:, (selected_crypto, ['Close', 'Volume'])]
df.columns = ['Price', 'Volume']

fig_price_volume = go.Figure()
fig_price_volume.add_trace(go.Scatter(x=df.index, y=df['Price'], name='Price'))
fig_price_volume.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', yaxis='y2'))
fig_price_volume.update_layout(title=f'{selected_crypto} Price and Volume',
                               yaxis=dict(title='Price'),
                               yaxis2=dict(title='Volume', overlaying='y', side='right'))
st.plotly_chart(fig_price_volume)

# Technical Indicators - RSI
st.subheader('Technical Indicators - RSI')
delta = df['Price'].diff()
up = delta.copy()
down = delta.copy()
up[up < 0] = 0
down[down > 0] = 0
roll_up = up.rolling(14).mean()
roll_down = down.abs().rolling(14).mean()
rs = roll_up / roll_down
rsi = 100.0 - (100.0 / (1.0 + rs))

fig_rsi = go.Figure()
fig_rsi.add_trace(go.Scatter(x=rsi.index, y=rsi, name='RSI'))
fig_rsi.add_hline(y=70, name='Overbought', line_dash='dash', line_color='red')
fig_rsi.add_hline(y=30, name='Oversold', line_dash='dash', line_color='green')
fig_rsi.update_layout(title=f'{selected_crypto} RSI (14)')
st.plotly_chart(fig_rsi)

# Portfolio Performance (Example)
st.subheader('Portfolio Performance')
portfolio_df = pd.DataFrame({
    'Asset': ['BTC', 'ETH', 'SOL', 'AVAX'],
    'Quantity': [0.5, 2, 10, 20],
    'Price': [data.loc[:, (ticker, 'Close')].iloc[-1] for ticker in tickers]
})
portfolio_df['Value'] = portfolio_df['Quantity'] * portfolio_df['Price']
fig_portfolio = go.Figure()
fig_portfolio.add_trace(go.Bar(x=portfolio_df['Asset'], y=portfolio_df['Value'], name='Portfolio Value'))
fig_portfolio.update_layout(title='Current Portfolio Value')
st.plotly_chart(fig_portfolio)

# News Sentiment (Placeholder)
st.subheader('News Sentiment')
st.write('Coming soon...')
