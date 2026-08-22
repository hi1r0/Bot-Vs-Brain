import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
import numpy as np
import random
import math
import time


# --- 1. INITIALIZE GAME STATE ---
def reset_game(starting_price=100.0):
    st.session_state.tick = 0
    st.session_state.price = starting_price

    st.session_state.open_history = [starting_price] * 30
    st.session_state.high_history = [starting_price] * 30
    st.session_state.low_history = [starting_price] * 30
    st.session_state.close_history = [starting_price] * 30
    st.session_state.sma_history = [starting_price] * 30

    starting_cash = st.session_state.get('starting_capital', 1000000.0)

    st.session_state.user_cash = starting_cash
    st.session_state.user_shares = 0
    st.session_state.human_trades = 0

    st.session_state.bot_cash = starting_cash
    st.session_state.bot_shares = 0
    st.session_state.bot_trades = 0

    st.session_state.bot_entry_price = 0.0
    st.session_state.bot_peak_price = 0.0
    st.session_state.bot_days_in_trade = 0

    st.session_state.trade_fee = 1.00
    st.session_state.data_exhausted = False
    st.session_state.game_over = False


if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.game_started = False
    st.session_state.starting_capital = 1000000.0
    st.session_state.real_data = None
    st.session_state.current_data_index = 0
    st.session_state.asset_name = "Simulated Asset"
    st.session_state.trade_qty = 10  # Default quantity to trade
    reset_game()


# --- 2. ADVANCED QUANT BOT LOGIC (NOW WITH SHORTING) ---
def execute_bot_trade(action, current_price):
    if action == "BUY":
        if st.session_state.bot_shares < 0:
            # COVER SHORT POSITION
            shares_to_buy = abs(st.session_state.bot_shares)
            cost = (shares_to_buy * current_price) + st.session_state.trade_fee
            st.session_state.bot_cash -= cost
            st.session_state.bot_shares = 0
            st.session_state.bot_trades += 1
            st.session_state.bot_days_in_trade = 0
        elif st.session_state.bot_shares == 0 and st.session_state.bot_cash > current_price:
            # GO LONG
            investment = st.session_state.bot_cash * 0.20
            shares_to_buy = math.floor(investment / current_price)
            if shares_to_buy > 0:
                cost = (shares_to_buy * current_price) + st.session_state.trade_fee
                st.session_state.bot_cash -= cost
                st.session_state.bot_shares += shares_to_buy
                st.session_state.bot_trades += 1
                st.session_state.bot_entry_price = current_price
                st.session_state.bot_peak_price = current_price
                st.session_state.bot_days_in_trade = 0

    elif action == "SELL":
        if st.session_state.bot_shares > 0:
            # CLOSE LONG POSITION
            revenue = (st.session_state.bot_shares * current_price) - st.session_state.trade_fee
            st.session_state.bot_cash += revenue
            st.session_state.bot_shares = 0
            st.session_state.bot_trades += 1
            st.session_state.bot_days_in_trade = 0
        elif st.session_state.bot_shares == 0 and st.session_state.bot_cash > current_price:
            # GO SHORT (Using 20% of cash as collateral)
            investment = st.session_state.bot_cash * 0.20
            shares_to_short = math.floor(investment / current_price)
            if shares_to_short > 0:
                revenue = (shares_to_short * current_price) - st.session_state.trade_fee
                st.session_state.bot_cash += revenue
                st.session_state.bot_shares -= shares_to_short  # Negative shares = Short
                st.session_state.bot_trades += 1
                st.session_state.bot_entry_price = current_price
                st.session_state.bot_peak_price = current_price  # For shorts, this tracks the LOWEST price
                st.session_state.bot_days_in_trade = 0


def advanced_bot_brain():
    closes = pd.Series(st.session_state.close_history)
    current_price = closes.iloc[-1]

    if len(closes) < 30: return

    # Indicators
    ema_12 = closes.ewm(span=12, adjust=False).mean()
    ema_26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()

    delta = closes.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]

    sma_20 = closes.rolling(window=20).mean()
    std_20 = closes.rolling(window=20).std()
    lower_band = sma_20 - (std_20 * 2)
    upper_band = sma_20 + (std_20 * 2)

    sma_slope = (sma_20.iloc[-1] - sma_20.iloc[-5]) / 5
    is_trending = abs(sma_slope) > (current_price * 0.002)

    # --- DEFENSE (Stop-Losses) ---
    if st.session_state.bot_shares != 0:
        st.session_state.bot_days_in_trade += 1

        # DEFENSE FOR LONGS
        if st.session_state.bot_shares > 0:
            if current_price > st.session_state.bot_peak_price:
                st.session_state.bot_peak_price = current_price
            if current_price < (st.session_state.bot_peak_price * 0.95):  # Trailing Stop
                execute_bot_trade("SELL", current_price)
                return
            if st.session_state.bot_days_in_trade >= 10 and current_price < (st.session_state.bot_entry_price * 1.02):
                execute_bot_trade("SELL", current_price)
                return

        # DEFENSE FOR SHORTS
        elif st.session_state.bot_shares < 0:
            if current_price < st.session_state.bot_peak_price:  # For shorts, peak is the lowest price
                st.session_state.bot_peak_price = current_price
            if current_price > (st.session_state.bot_peak_price * 1.05):  # Trailing Stop Loss (Price went UP 5%)
                execute_bot_trade("BUY", current_price)  # Buy to Cover
                return
            if st.session_state.bot_days_in_trade >= 10 and current_price > (st.session_state.bot_entry_price * 0.98):
                execute_bot_trade("BUY", current_price)
                return

    # --- OFFENSE (Signals) ---
    action = "HOLD"
    if is_trending:
        if macd_line.iloc[-1] > signal_line.iloc[-1] and macd_line.iloc[-2] <= signal_line.iloc[-2]:
            action = "BUY"
        elif macd_line.iloc[-1] < signal_line.iloc[-1] and macd_line.iloc[-2] >= signal_line.iloc[-2]:
            action = "SELL"
    else:
        if current_rsi < 30 or current_price <= lower_band.iloc[-1]:
            action = "BUY"
        elif current_rsi > 70 or current_price >= upper_band.iloc[-1]:
            action = "SELL"

    if action != "HOLD":
        execute_bot_trade(action, current_price)


# --- 3. MARKET ENGINE & HUMAN LOGIC ---
def advance_market():
    if st.session_state.real_data is not None:
        if st.session_state.current_data_index < len(st.session_state.real_data) - 1:
            st.session_state.current_data_index += 1
            row = st.session_state.real_data.iloc[st.session_state.current_data_index]
            open_price = float(row['Open'])
            high_price = float(row['High'])
            low_price = float(row['Low'])
            new_close = float(row['Close'])
        else:
            st.session_state.data_exhausted = True
            st.session_state.game_over = True
            st.toast("Match Complete! Calculating final scores...", icon="🏁")
            return
    else:
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
    st.session_state.open_history.append(open_price)
    st.session_state.high_history.append(high_price)
    st.session_state.low_history.append(low_price)
    st.session_state.close_history.append(new_close)

    if len(st.session_state.close_history) > 100:
        st.session_state.open_history.pop(0)
        st.session_state.high_history.pop(0)
        st.session_state.low_history.pop(0)
        st.session_state.close_history.pop(0)

    advanced_bot_brain()
    st.session_state.tick += 1


def human_buy(qty):
    total_cost = (st.session_state.price * qty) + st.session_state.trade_fee
    if st.session_state.user_cash >= total_cost:
        st.session_state.user_cash -= total_cost
        st.session_state.user_shares += qty  # Adds shares (buying long or covering short)
        st.session_state.human_trades += 1
    else:
        st.toast("Not enough cash to Buy/Cover!", icon="🚫")


def human_sell(qty):
    required_collateral = st.session_state.price * qty
    current_long_value = max(0, st.session_state.user_shares * st.session_state.price)

    # Allow selling if they have long shares, OR if they have enough cash to act as margin for shorting
    if (st.session_state.user_cash + current_long_value) >= required_collateral:
        st.session_state.user_cash += (st.session_state.price * qty) - st.session_state.trade_fee
        st.session_state.user_shares -= qty  # Subtracts shares (selling long or going short)
        st.session_state.human_trades += 1
    else:
        st.toast("Not enough margin cash to Sell Short!", icon="🚫")


def load_real_data(ticker_symbol):
    try:
        df = yf.download(ticker_symbol, period="1y", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if df.empty:
            st.sidebar.error(f"Could not find data for {ticker_symbol}")
            return

        st.session_state.real_data = df
        st.session_state.current_data_index = 0
        st.session_state.asset_name = ticker_symbol.upper()
        starting_price = float(df.iloc[0]['Close'])
        reset_game(starting_price)
        st.sidebar.success(f"Loaded {ticker_symbol} successfully!")
    except Exception as e:
        st.sidebar.error(f"Error loading data: {e}")


# Formatting helper for UI
def format_position(shares):
    if shares > 0:
        return f"Long {shares}"
    elif shares < 0:
        return f"Short {abs(shares)}"
    return "Flat (0)"


# --- 4. UI DASHBOARD ---
st.set_page_config(layout="wide", page_title="Bot vs Brain")

with st.sidebar:
    st.header("⚙️ Market Settings")
    ticker_input = st.text_input("Ticker Symbol", value="AAPL")
    if st.button("Load Real Market Data", use_container_width=True):
        load_real_data(ticker_input)
    st.divider()
    st.write("**Market Controls:**")
    auto_play = st.toggle("▶️ Live Market (Auto-Play)", key="auto_play",
                          disabled=not st.session_state.game_started or st.session_state.game_over)
    game_speed = st.slider("Speed (Seconds per day)", min_value=0.1, max_value=3.0, value=0.5, step=0.1,
                           disabled=not st.session_state.game_started or st.session_state.game_over)

if not st.session_state.game_started:
    st.title("🧠 Bot vs. Brain: The Quant Challenge")
    st.markdown("### Match Setup")
    capital_input = st.number_input("Initial Capital (₹)", min_value=1000.0, value=1000000.0, step=50000.0, format="%f")
    st.write(f"**Starting Bankroll:** ₹{capital_input:,.2f}")
    if st.button("🚀 Start Challenge", type="primary", use_container_width=True):
        st.session_state.starting_capital = capital_input
        reset_game(st.session_state.price)
        st.session_state.game_started = True
        st.rerun()

elif st.session_state.game_over:
    st.title("🏁 Match Complete!")
    user_final_val = st.session_state.user_cash + (st.session_state.user_shares * st.session_state.price)
    bot_final_val = st.session_state.bot_cash + (st.session_state.bot_shares * st.session_state.price)
    starting_cap = st.session_state.starting_capital

    user_profit = user_final_val - starting_cap
    bot_profit = bot_final_val - starting_cap
    user_roi = (user_profit / starting_cap) * 100
    bot_roi = (bot_profit / starting_cap) * 100

    initial_price = st.session_state.close_history[0]
    final_price = st.session_state.price
    market_return_pct = ((final_price - initial_price) / initial_price) * 100

    st.markdown("### 🏆 Match Results")
    if user_final_val > bot_final_val:
        st.success(f"🎉 YOU WIN! You beat the algorithm by ₹{(user_final_val - bot_final_val):,.2f}!")
    elif bot_final_val > user_final_val:
        st.error(f"💀 THE BOT WINS. The algorithm beat you by ₹{(bot_final_val - user_final_val):,.2f}.")
    else:
        st.warning("🤝 It's a tie!")

    st.divider()
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("#### 👤 Human Performance")
        st.metric("Final Portfolio", f"₹{user_final_val:,.2f}", f"{user_roi:.2f}% ROI")
        st.write(f"**Total Trades:** {st.session_state.human_trades}")
        st.write(f"- Cash: ₹{st.session_state.user_cash:,.2f}")
        st.write(f"- Position: {format_position(st.session_state.user_shares)}")

    with c2:
        st.markdown("#### 🤖 Bot Performance")
        st.metric("Final Portfolio", f"₹{bot_final_val:,.2f}", f"{bot_roi:.2f}% ROI")
        st.write(f"**Total Trades:** {st.session_state.bot_trades}")
        st.write(f"- Cash: ₹{st.session_state.bot_cash:,.2f}")
        st.write(f"- Position: {format_position(st.session_state.bot_shares)}")

    with c3:
        st.markdown("#### 📈 Market Baseline")
        st.metric(f"Asset: {st.session_state.asset_name}", f"₹{final_price:,.2f}",
                  f"{market_return_pct:.2f}% Market Return")
        st.write(f"Did Human beat market? **{'Yes' if user_roi > market_return_pct else 'No'}**")
        st.write(f"Did Bot beat market? **{'Yes' if bot_roi > market_return_pct else 'No'}**")

    st.divider()
    if st.button("🔄 Play Again", type="primary", use_container_width=True):
        st.session_state.game_started = False
        st.session_state.game_over = False
        st.rerun()

else:
    st.title("🧠 Bot vs. Brain: The Quant Challenge")
    if st.button("🛑 End Match & See Results"):
        st.session_state.game_over = True
        st.rerun()

    user_val = st.session_state.user_cash + (st.session_state.user_shares * st.session_state.price)
    bot_val = st.session_state.bot_cash + (st.session_state.bot_shares * st.session_state.price)

    col1, col2, col3 = st.columns(3)
    col1.metric("👤 Human Portfolio", f"₹{user_val:,.2f}",
                f"Cash: ₹{st.session_state.user_cash:,.0f} | Position: {format_position(st.session_state.user_shares)}")
    col2.metric("📈 Current Price", f"₹{st.session_state.price:,.2f}", f"Day: {st.session_state.tick}")
    col3.metric("🤖 Bot Portfolio", f"₹{bot_val:,.2f}",
                f"Cash: ₹{st.session_state.bot_cash:,.0f} | Position: {format_position(st.session_state.bot_shares)}")

    # --- CHART MATH ---
    closes = pd.Series(st.session_state.close_history[-50:])
    x_values = list(range(len(closes)))

    sma_20 = closes.rolling(window=20).mean()
    std_20 = closes.rolling(window=20).std()
    upper_band = sma_20 + (std_20 * 2)
    lower_band = sma_20 - (std_20 * 2)

    delta = closes.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    ema_12 = closes.ewm(span=12, adjust=False).mean()
    ema_26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    # --- HUMAN TOOLKIT TOGGLES ---
    st.markdown("### 🛠️ Human Toolkit (Visual Indicators)")
    t1, t2, t3 = st.columns(3)
    with t1:
        show_bb = st.toggle("Bollinger Bands (Volatility)")
    with t2:
        show_rsi = st.toggle("RSI (Momentum)")
    with t3:
        show_macd = st.toggle("MACD (Trend)")

    # --- DRAW CHARTS ---
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=x_values, open=st.session_state.open_history[-50:], high=st.session_state.high_history[-50:],
        low=st.session_state.low_history[-50:], close=st.session_state.close_history[-50:],
        name="Price", increasing_line_color='#00ff00', decreasing_line_color='#ff0000'
    ))

    if show_bb:
        fig.add_trace(
            go.Scatter(x=x_values, y=upper_band, line=dict(color='rgba(255,255,255,0.4)', dash='dot'), name='Upper BB'))
        fig.add_trace(
            go.Scatter(x=x_values, y=lower_band, line=dict(color='rgba(255,255,255,0.4)', dash='dot'), fill='tonexty',
                       fillcolor='rgba(255,255,255,0.05)', name='Lower BB'))

    fig.update_layout(template='plotly_dark', height=400, margin=dict(l=0, r=0, t=10, b=0),
                      xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    if show_rsi:
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(x=x_values, y=rsi, line=dict(color='#b366ff', width=2), name='RSI'))
        fig_rsi.add_hline(y=70, line_dash="dot", line_color="red", annotation_text="Overbought")
        fig_rsi.add_hline(y=30, line_dash="dot", line_color="green", annotation_text="Oversold")
        fig_rsi.update_layout(template='plotly_dark', height=200, margin=dict(l=0, r=0, t=10, b=0),
                              yaxis_range=[0, 100], yaxis_title="RSI")
        st.plotly_chart(fig_rsi, use_container_width=True)

    if show_macd:
        fig_macd = go.Figure()
        fig_macd.add_trace(go.Bar(x=x_values, y=macd_hist, marker_color='gray', name='Histogram'))
        fig_macd.add_trace(go.Scatter(x=x_values, y=macd_line, line=dict(color='#3399ff'), name='MACD'))
        fig_macd.add_trace(go.Scatter(x=x_values, y=signal_line, line=dict(color='#ff9900'), name='Signal'))
        fig_macd.update_layout(template='plotly_dark', height=200, margin=dict(l=0, r=0, t=10, b=0), yaxis_title="MACD")
        st.plotly_chart(fig_macd, use_container_width=True)

    # --- TRADING TERMINAL ---
    st.markdown("### Trading Terminal")

    # NEW: Quantity Input
    trade_qty = st.number_input("Shares to Trade:", min_value=1, value=10, step=10)

    c1, c2 = st.columns(2)
    with c1:
        st.button("🟢 BUY / COVER SHORT", on_click=human_buy, args=(trade_qty,), use_container_width=True)
    with c2:
        st.button("🔴 SELL / GO SHORT", on_click=human_sell, args=(trade_qty,), use_container_width=True)

    if st.session_state.auto_play and not st.session_state.get('data_exhausted', False):
        time.sleep(st.session_state.get('game_speed', 0.5))
        advance_market()
        st.rerun()