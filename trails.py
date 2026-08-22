import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd


# --- 1. INITIALIZE GAME STATE ---
def reset_game(starting_price=100.0):
    st.session_state.tick = 0
    st.session_state.price = starting_price

    # Reset histories with the starting price
    st.session_state.open_history = [starting_price]
    st.session_state.high_history = [starting_price]
    st.session_state.low_history = [starting_price]
    st.session_state.close_history = [starting_price]
    st.session_state.sma_history = [starting_price]

    # Portfolios
    st.session_state.user_cash = 10000.0  # Increased starting cash for real stock prices
    st.session_state.user_shares = 0
    st.session_state.bot_cash = 10000.0
    st.session_state.bot_shares = 0

    st.session_state.trade_fee = 1.00


if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.real_data = None  # Holds the downloaded market data
    st.session_state.current_data_index = 0
    st.session_state.asset_name = "Simulated Asset"
    reset_game()


# --- 2. GAME LOGIC FUNCTIONS ---
def advance_market():
    # If we have real data loaded, read the next row
    if st.session_state.real_data is not None:
        if st.session_state.current_data_index < len(st.session_state.real_data) - 1:
            st.session_state.current_data_index += 1
            row = st.session_state.real_data.iloc[st.session_state.current_data_index]

            # Extract real OHLC
            open_price = float(row['Open'])
            high_price = float(row['High'])
            low_price = float(row['Low'])
            new_close = float(row['Close'])
        else:
            st.toast("End of real historical data reached!", icon="🛑")
            return  # Stop advancing if we run out of data
    else:
        # Fallback to the simulated math if no real data is loaded
        import random, math
        mu, sigma, dt = 0.005, 0.04, 1.0
        prev_close = st.session_state.price
        Z = random.gauss(0, 1)
        new_close = prev_close * math.exp((mu - (sigma ** 2) / 2) * dt + sigma * math.sqrt(dt) * Z)
        if new_close < 1.0: new_close = 1.0
        open_price = prev_close
        volatility = new_close * sigma * random.random()
        high_price = max(open_price, new_close) + volatility
        low_price = min(open_price, new_close) - volatility

    st.session_state.price = new_close

    # Update Histories
    st.session_state.open_history.append(open_price)
    st.session_state.high_history.append(high_price)
    st.session_state.low_history.append(low_price)
    st.session_state.close_history.append(new_close)

    if len(st.session_state.close_history) > 50:
        st.session_state.open_history.pop(0)
        st.session_state.high_history.pop(0)
        st.session_state.low_history.pop(0)
        st.session_state.close_history.pop(0)

    # Bot SMA Logic (5-period)
    recent_closes = st.session_state.close_history[-5:]
    current_sma = sum(recent_closes) / len(recent_closes)

    st.session_state.sma_history.append(current_sma)
    if len(st.session_state.sma_history) > 50: st.session_state.sma_history.pop(0)

    # Bot Trading Logic
    total_buy_cost = st.session_state.price + st.session_state.trade_fee
    if st.session_state.price > current_sma and st.session_state.bot_cash >= total_buy_cost:
        st.session_state.bot_cash -= total_buy_cost
        st.session_state.bot_shares += 1
    elif st.session_state.price < current_sma and st.session_state.bot_shares > 0:
        st.session_state.bot_cash += (st.session_state.price - st.session_state.trade_fee)
        st.session_state.bot_shares -= 1

    st.session_state.tick += 1


def human_buy():
    total_cost = st.session_state.price + st.session_state.trade_fee
    if st.session_state.user_cash >= total_cost:
        current_sma = st.session_state.sma_history[-1]
        if st.session_state.price > current_sma * 1.03:
            st.toast("🚀 ANTIGRAVITY ENGAGED! You FOMO bought the top!", icon="⚠️")
        st.session_state.user_cash -= total_cost
        st.session_state.user_shares += 1
    advance_market()


def human_sell():
    if st.session_state.user_shares > 0:
        current_sma = st.session_state.sma_history[-1]
        if st.session_state.price < current_sma * 0.97:
            st.toast("📉 GRAVITY CRASH! You panic sold the bottom!", icon="💥")
        st.session_state.user_cash += (st.session_state.price - st.session_state.trade_fee)
        st.session_state.user_shares -= 1
    advance_market()


def wait():
    advance_market()


def load_real_data(ticker_symbol):
    try:
        # Download 6 months of daily data
        df = yf.download(ticker_symbol, period="6mo", interval="1d", progress=False)

        # Flatten columns if yfinance returns a MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        if df.empty:
            st.sidebar.error(f"Could not find data for {ticker_symbol}")
            return

        st.session_state.real_data = df
        st.session_state.current_data_index = 0
        st.session_state.asset_name = ticker_symbol.upper()

        # Start the game at the exact price of the first day in the downloaded data
        starting_price = float(df.iloc[0]['Close'])
        reset_game(starting_price)
        st.sidebar.success(f"Loaded {ticker_symbol} successfully!")

    except Exception as e:
        st.sidebar.error(f"Error loading data: {e}")


# --- 3. UI DASHBOARD ---
st.set_page_config(layout="wide", page_title="Bot vs Brain")

# --- SIDEBAR FOR ASSET SELECTION ---
with st.sidebar:
    st.header("⚙️ Market Settings")
    st.write("Play against the bot using real stock or crypto data!")
    ticker_input = st.text_input("Ticker Symbol", value="AAPL", help="Examples: TSLA, BTC-USD, RELIANCE.NS, INFY.NS")
    if st.button("Load Real Market Data", use_container_width=True):
        load_real_data(ticker_input)
    st.divider()
    st.write("**Current Asset:**")
    st.subheader(st.session_state.asset_name)

st.title("🧠 Bot vs. Brain: The Quant Challenge")

user_val = st.session_state.user_cash + (st.session_state.user_shares * st.session_state.price)
bot_val = st.session_state.bot_cash + (st.session_state.bot_shares * st.session_state.price)

col1, col2, col3 = st.columns(3)
col1.metric("👤 Human Portfolio", f"₹{user_val:.2f}",
            f"Cash: ₹{st.session_state.user_cash:.0f} | Shares: {st.session_state.user_shares}")
col2.metric("📈 Current Price", f"₹{st.session_state.price:.2f}", f"Day: {st.session_state.tick}")
col3.metric("🤖 Bot Portfolio", f"₹{bot_val:.2f}",
            f"Cash: ₹{st.session_state.bot_cash:.0f} | Shares: {st.session_state.bot_shares}")

# --- DRAW PLOTLY CANDLESTICK CHART ---
fig = go.Figure()

x_values = list(range(len(st.session_state.close_history)))

fig.add_trace(go.Candlestick(
    x=x_values,
    open=st.session_state.open_history,
    high=st.session_state.high_history,
    low=st.session_state.low_history,
    close=st.session_state.close_history,
    name=st.session_state.asset_name,
    increasing_line_color='#00ff00',
    decreasing_line_color='#ff0000'
))

fig.add_trace(go.Scatter(
    x=x_values,
    y=st.session_state.sma_history,
    mode='lines',
    name='Bot SMA (5)',
    line=dict(color='#ff9900', dash='dash', width=2)
))

fig.update_layout(
    template='plotly_dark',
    height=450,
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis_title="Days",
    yaxis_title="Price",
    xaxis_rangeslider_visible=False
)
st.plotly_chart(fig, use_container_width=True)

# Controls
st.markdown("### Trading Terminal (Fee: ₹1.00/trade)")
c1, c2, c3 = st.columns(3)
with c1:
    st.button("🟢 BUY", on_click=human_buy, use_container_width=True)
with c2:
    st.button("🔴 SELL", on_click=human_sell, use_container_width=True)
with c3:
    st.button("⏳ WAIT (Next Day)", on_click=wait, use_container_width=True)