# Bot vs Brain: Quantitative Trading Simulator

A real-time algorithmic trading match platform and simulation engine that pits human discretionary trading against an automated quantitative algorithmic strategy. Built with Streamlit, Plotly, and Yahoo Finance.

---

## 1. System Architecture

The application operates as a reactive single-page architecture powered by Streamlit's session state machine and Plotly's rendering engine. The core execution cycle is partitioned into three distinct layers: Market Generation, Strategy Evaluation, and State Management.

```
+-------------------------------------------------------------------------+
|                              STREAMLIT UI                               |
|   +---------------------+   +---------------------+   +---------------+ |
|   |  Market Controls    |   |  Interactive Charts |   |  Order Entry  | |
|   |  (Ticker, Playback) |   |  (Candles, BB, RSI) |   |  (Buy/Sell)   | |
|   +----------+----------+   +----------+----------+   +-------+-------+ |
+--------------|-------------------------|----------------------|---------+
               |                         |                      |
               v                         v                      v
+-------------------------------------------------------------------------+
|                        SESSION STATE ENGINE                             |
|  - Time Series Histories (Open, High, Low, Close, SMA)                  |
|  - Human Portfolio (Cash, Shares, Trade Count)                          |
|  - Bot Portfolio (Cash, Shares, Peak Price, Entry Price, Days in Trade) |
+-----------------------+-----------------------------------+-------------+
                        |                                   |
                        v                                   v
+------------------------------------+    +-------------------------------+
|       MARKET ENGINE LAYER          |    |     QUANT STRATEGY ENGINE     |
|  - Stochastic GBM Simulation OR    |    |  - Regime Filter (SMA-20)     |
|  - Yahoo Finance Historical Ingest |    |  - Trend Follower (MACD)      |
|  - Real-time Candlestick Synthesis |    |  - Mean Reversion (RSI + BB)  |
|                                    |    |  - Dynamic Trailing Stop-Loss |
+------------------------------------+    +-------------------------------+
```

---

## 2. Market Generation Engine

The simulator supports two modes of price action: synthetic stochastic asset generation and real historical market playback.

### 2.1 Geometric Brownian Motion (GBM) Mode

When simulated data is selected, the price series evolves according to Geometric Brownian Motion with drift:

$$dS_t = \mu S_t dt + \sigma S_t dW_t$$

In discrete time steps, the transition function is formulated as:

$$S_{t+\Delta t} = S_t \exp\left(\left(\mu - \frac{\sigma^2}{2}\right)\Delta t + \sigma \sqrt{\Delta t} Z\right)$$

Where:
- $S_t$: Asset price at discrete time step $t$.
- $\mu$: Expected drift parameter ($\mu = 0.005$).
- $\sigma$: Volatility parameter ($\sigma = 0.04$).
- $\Delta t$: Time increment ($\Delta t = 1.0$).
- $Z \sim \mathcal{N}(0, 1)$: Standard normal random variable.

Intra-bar candlestick dynamics (Open, High, Low, Close) are synthesized using stochastic spread sampling:
- $\text{Open}_t = S_{t-1}$
- $\text{Close}_t = S_t$
- $V_t = S_t \cdot \sigma \cdot U(0, 1)$
- $\text{High}_t = \max(\text{Open}_t, \text{Close}_t) + V_t$
- $\text{Low}_t = \min(\text{Open}_t, \text{Close}_t) - V_t$

### 2.2 Historical Market Ingestion Mode

When a real ticker symbol is provided, the platform fetches 1 year of daily historical price series using the Yahoo Finance API. The data array is sequentially stepped through on each clock tick, preserving true market microstructure and historical volatility.

---

## 3. Quantitative Trading Algorithm (Bot Brain)

The quantitative agent implements a dual-mode strategy combining market regime classification, momentum crossover, volatility mean-reversion, and asymmetric risk management.

```
                         [ New Price Tick ]
                                 |
                                 v
                     [ Calculate Indicators ]
                     - SMA(20), StdDev(20)
                     - EMA(12), EMA(26), Signal(9)
                     - RSI(14)
                                 |
                                 v
                     [ Active Position Check ]
                     |                       |
            (Has Position)              (No Position)
                     |                       |
                     v                       v
          [ Risk & Exit Rules ]     [ Market Regime Check ]
          - Trailing Stop (5%)      |                     |
          - Stale Trade Exit (10d)  v                     v
                     |        (Trend Regime)       (Mean Reversion)
                     |        |                    |
                     |        v                    v
                     |    [ MACD Cross? ]      [ RSI / Band Touch? ]
                     |        |                    |
                     +--------+--------------------+
                                 |
                                 v
                     [ Execute Order & Rebalance ]
```

### 3.1 Market Regime Classification

The bot determines if the market is in a directional trending phase or an oscillating ranging phase by calculating the first derivative (slope) of the 20-period Simple Moving Average:

$$\text{SMA Slope} = \frac{\text{SMA}_{20}(t) - \text{SMA}_{20}(t-5)}{5}$$

$$\text{Regime} = \begin{cases} \text{Trending}, & \text{if } |\text{SMA Slope}| > 0.002 \cdot S_t \\ \text{Mean Reverting}, & \text{otherwise} \end{cases}$$

### 3.2 Signal Generation Logic

#### Trending Regime: Moving Average Convergence Divergence (MACD)
- $\text{EMA}_{12}(t) = \alpha_{12} S_t + (1 - \alpha_{12}) \text{EMA}_{12}(t-1)$
- $\text{EMA}_{26}(t) = \alpha_{26} S_t + (1 - \alpha_{26}) \text{EMA}_{26}(t-1)$
- $\text{MACD Line}(t) = \text{EMA}_{12}(t) - \text{EMA}_{26}(t)$
- $\text{Signal Line}(t) = \text{EMA}_{9}(\text{MACD Line}(t))$

Rules:
- Bullish Crossover ($\text{MACD}(t) > \text{Signal}(t)$ and $\text{MACD}(t-1) \le \text{Signal}(t-1)$) -> **BUY**
- Bearish Crossover ($\text{MACD}(t) < \text{Signal}(t)$ and $\text{MACD}(t-1) \ge \text{Signal}(t-1)$) -> **SELL**

#### Mean-Reverting Regime: Relative Strength Index (RSI) & Bollinger Bands
- $\text{Upper Band} = \text{SMA}_{20} + 2\sigma_{20}$
- $\text{Lower Band} = \text{SMA}_{20} - 2\sigma_{20}$
- $\text{RSI}_{14} = 100 - \left(\frac{100}{1 + \frac{\text{Avg Gain}_{14}}{\text{Avg Loss}_{14}}}\right)$

Rules:
- Oversold ($\text{RSI}_{14} < 30$ or $S_t \le \text{Lower Band}$) -> **BUY**
- Overbought ($\text{RSI}_{14} > 70$ or $S_t \ge \text{Upper Band}$) -> **SELL**

### 3.3 Position Sizing & Collateral Allocation

- The bot allocates a fixed fraction of total portfolio cash per trade:
  $$\text{Allocation} = \text{Bot Cash} \times 0.20$$
  $$\text{Shares} = \left\lfloor \frac{\text{Allocation}}{S_t} \right\rfloor$$
- Symmetrical support for Long positions ($\text{Shares} > 0$) and Short positions ($\text{Shares} < 0$).
- Fixed transaction fee penalty per execution: \$1.00 / ₹1.00.

### 3.4 Risk Management & Exit Discipline

The bot operates trailing stops and duration thresholds independently:

1. **Long Positions**:
   - Updates trailing peak: $\text{Peak Price} = \max(\text{Peak Price}, S_t)$.
   - Trailing Stop: Triggers **SELL** if $S_t < 0.95 \cdot \text{Peak Price}$ (5% trailing loss).
   - Time-Decay Exit: Triggers **SELL** if $\text{Days Held} \ge 10$ and $S_t < 1.02 \cdot \text{Entry Price}$.

2. **Short Positions**:
   - Updates trailing floor: $\text{Trough Price} = \min(\text{Trough Price}, S_t)$.
   - Trailing Stop: Triggers **BUY** (Cover) if $S_t > 1.05 \cdot \text{Trough Price}$ (5% adverse price surge).
   - Time-Decay Exit: Triggers **BUY** if $\text{Days Held} \ge 10$ and $S_t > 0.98 \cdot \text{Entry Price}$.

---

## 4. Human Interface & Execution Terminal

The trading terminal exposes technical indicators for discretionary human evaluation:
- **Candlestick Charting**: Rolling 50-tick visual window.
- **Bollinger Bands Overlay**: Volatility channels with shaded envelope.
- **RSI Subplot**: Momentum bounds with 30/70 boundary markers.
- **MACD Subplot**: MACD line, Signal line, and diverging histogram bars.
- **Order Execution Controls**: Granular lot sizing with real-time margin/collateral validation.

---

## 5. Performance Evaluation & Alpha Metrics

Upon termination of the match, total net asset values are computed:

$$\text{Portfolio Value} = \text{Cash} + (\text{Shares} \times S_{\text{final}})$$

$$\text{ROI} = \left(\frac{\text{Portfolio Value} - \text{Starting Capital}}{\text{Starting Capital}}\right) \times 100$$

$$\text{Market Baseline Return} = \left(\frac{S_{\text{final}} - S_{\text{initial}}}{S_{\text{initial}}}\right) \times 100$$

$$\text{Alpha} = \text{ROI} - \text{Market Baseline Return}$$

The summary dashboard highlights whether human intuition or the algorithmic agent outperformed both the counterparty and the passive Buy-and-Hold benchmark.

---

## 6. Project Structure

```
Bot-Vs-Brain/
|-- bot_vs_brain.py       # Main Streamlit application and execution engine
|-- requirements.txt      # Production runtime dependencies
|-- README.md             # Technical architecture blueprint
`-- .gitignore            # Git ignore definitions
```

---

## 7. Installation and Execution

### 7.1 Prerequisites
- Python 3.9 or higher
- Git

### 7.2 Clone and Setup
```bash
git clone https://github.com/hi1r0/Bot-Vs-Brain.git
cd Bot-Vs-Brain
```

### 7.3 Virtual Environment Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate virtual environment (Linux/macOS)
source .venv/bin/activate
```

### 7.4 Install Dependencies
```bash
pip install -r requirements.txt
```

### 7.5 Run the Application
```bash
streamlit run bot_vs_brain.py
```
The application will launch automatically in your default browser at `http://localhost:8501`.
