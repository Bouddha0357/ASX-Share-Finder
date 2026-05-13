import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- APP CONFIG ---
st.set_page_config(page_title="ASX Alpha Pro", layout="wide")
st.title("🚀 ASX Alpha: Log-Recovery Dashboard")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("Strategy Filters")
target_streak = st.sidebar.slider("Recovery Streak (Days)", 1, 5, 2, help="Days log-spread must be rising")
mcap_min = st.sidebar.number_input("Min Market Cap ($M)", value=10) * 1_000_000
mcap_max = st.sidebar.number_input("Max Market Cap ($M)", value=750) * 1_000_000

# --- MEMORY ---
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None
if 'found_data' not in st.session_state:
    st.session_state.found_data = {}

def run_strategy():
    # 1. FETCH TICKERS
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        
        # Sector Targets
        target_groups = [
            'Software & Services', 'Capital Goods', 'Materials', 
            'Technology Hardware & Equipment'
        ]
        
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    status_text = st.empty()
    status_text.info(f"⚡ Downloading data for {len(tickers)} tickers...")
    
    # 2. BATCH DOWNLOAD
    data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=False)
    
    if data.empty or 'Close' not in data:
        st.error("🚨 Yahoo Finance returned no data. You may be rate-limited. Wait 15 mins.")
        return

    close_prices = data['Close']
    volumes = data['Volume']
    
    final_results = []
    temp_found_data = {}

    # 3. ANALYSIS LOOP
    for i, ticker in enumerate(tickers):
        if i % 50 == 0:
            status_text.info(f"Analyzing: {i}/{len(tickers)} stocks...")
            
        try:
            # Skip tickers with no data
            if ticker not in close_prices or close_prices[ticker].dropna().empty:
                continue
                
            p = close_prices[ticker].dropna()
            v = volumes[ticker].dropna()
            if len(p) < 60: continue

            # Technicals
            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            log_spread = np.log(ma20 / ma50)
            
            # Log Spread Change
            diff = log_spread.diff()
            
            # CRITERIA: 
            # 1. Rising for X days
            # 2. Still in a pullback (negative gap)
            is_curling = (diff.tail(target_streak) > 0).all()
            is_pullback = log_spread.iloc[-1] < 0
            
            if is_curling and is_pullback:
                # Market Cap Check
                info = yf.Ticker(ticker).fast_info
                mcap = info.get('market_cap', 0)
                
                if mcap_min <= mcap <= mcap_max:
                    turnover = (p * v).tail(20).mean()
                    # Filter for minimum liquidity ($10k/day)
                    if turnover < 10_000: continue
                    
                    final_results.append({
                        "Ticker": ticker,
                        "Price": round(p.iloc[-1], 3),
                        "Mkt Cap": f"${int(mcap/1_000_000)}M",
                        "Log Gap": round(log_spread.iloc[-1], 4),
                        "Turnover": f"${int(turnover/1000)}k"
                    })
                    temp_found_data[ticker] = pd.DataFrame({
                        'Close': p, 'MA20': ma20, 'MA50': ma50, 'LogSpread': log_spread
                    })
        except: continue

    status_text.empty()
    st.session_state.scan_results = pd.DataFrame(final_results) if final_results else None
    st.session_state.found_data = temp_found_data

# --- UI LOGIC ---
if st.button('🚀 Execute Alpha Scan'):
    run_strategy()

if st.session_state.scan_results is not None:
    df_final = st.session_state.scan_results.sort_values("Log Gap", ascending=False)
    st.success(f"Found {len(df_final)} setups!")
    st.dataframe(df_final, use_container_width=True)

    st.divider()
    selected_ticker = st.selectbox("Detailed Analysis", df_final['Ticker'].tolist())
    
    if selected_ticker and selected_ticker in st.session_state.found_data:
        df_plot = st.session_state.found_data[selected_ticker].tail(100)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # LOG RECOVERY (LEFT AXIS)
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['LogSpread'], name="Log Recovery", 
            line=dict(color='lime', width=2), fill='tozeroy'
        ), secondary_y=True)

        # PRICE & MAs (RIGHT AXIS)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name="Price", line=dict(color='white')), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], name="MA20", line=dict(color='yellow')), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA50'], name="MA50", line=dict(color='royalblue')), secondary_y=False)

        fig.update_layout(
            paper_bgcolor='black', plot_bgcolor='black', font=dict(color='white'),
            xaxis_rangeslider_visible=False, height=600,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)
elif st.session_state.scan_results is None and 'scan_results' in st.session_state:
    st.warning("No stocks passed the momentum filters. The current market sell-off has likely broken the recovery streaks for most companies.")
