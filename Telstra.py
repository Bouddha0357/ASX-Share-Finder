import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="ASX Alpha Pro", layout="wide")
st.title("🚀 ASX Alpha: Small-Cap Recovery")

# --- SIDEBAR SETTINGS ---
st.sidebar.header("Filter Settings")
# Set streak to 1 or 2 to ensure results in volatile markets
target_streak = st.sidebar.slider("Recovery Streak (Days)", 1, 5, 2)
# Widened Market Cap for more results
mcap_min = st.sidebar.number_input("Min Mkt Cap ($M)", value=10) * 1_000_000
mcap_max = st.sidebar.number_input("Max Mkt Cap ($M)", value=750) * 1_000_000

if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None
if 'found_data' not in st.session_state:
    st.session_state.found_data = {}

def run_strategy():
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        target_groups = ['Software & Services', 'Capital Goods', 'Materials', 'Technology Hardware & Equipment']
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    status_text = st.empty()
    status_text.info(f"⚡ Analyzing {len(tickers)} tickers...")
    
    # Batch download
    data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=False)
    close_prices = data['Close']
    volumes = data['Volume']
    
    final_results = []
    temp_found_data = {}

    for i, ticker in enumerate(tickers):
        try:
            p = close_prices[ticker].dropna()
            v = volumes[ticker].dropna()
            if len(p) < 60: continue

            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            log_spread = np.log(ma20 / ma50)
            
            diff = log_spread.diff()
            # Requirement: Recovery streak AND still in a pullback
            if (diff.tail(target_streak) > 0).all() and log_spread.iloc[-1] < 0:
                
                # Check Market Cap only for momentum winners
                info = yf.Ticker(ticker).fast_info
                mcap = info.get('market_cap', 0)
                
                if mcap_min <= mcap <= mcap_max:
                    turnover = (p * v).tail(20).mean()
                    # Final Filter: Ensure at least some trading activity ($10k/day)
                    if turnover < 10_000: continue
                    
                    final_results.append({
                        "Ticker": ticker,
                        "Price": round(p.iloc[-1], 3),
                        "Mkt Cap": f"${int(mcap/1_000_000)}M",
                        "Log Gap": round(log_spread.iloc[-1], 4),
                        "Turnover": f"${int(turnover/1000)}k"
                    })
                    temp_found_data[ticker] = pd.DataFrame({'Close': p, 'MA20': ma20, 'MA50': ma50, 'LogSpread': log_spread})
        except: continue

    status_text.empty()
    st.session_state.scan_results = pd.DataFrame(final_results) if final_results else None
    st.session_state.found_data = temp_found_data

if st.button('🚀 Run Alpha Scan'):
    run_strategy()

if st.session_state.scan_results is not None:
    df_final = st.session_state.scan_results.sort_values("Log Gap", ascending=False)
    st.dataframe(df_final, use_container_width=True)

    st.divider()
    selected = st.selectbox("View Chart", df_final['Ticker'].tolist())
    if selected and selected in st.session_state.found_data:
        d = st.session_state.found_data[selected].tail(100)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Scatter(x=d.index, y=d['LogSpread'], name="Log Recovery", line=dict(color='lime'), fill='tozeroy'), secondary_y=True)
        fig.add_trace(go.Scatter(x=d.index, y=d['Close'], name="Price", line=dict(color='white')), secondary_y=False)
        fig.add_trace(go.Scatter(x=d.index, y=d['MA20'], name="MA20", line=dict(color='yellow')), secondary_y=False)
        fig.add_trace(go.Scatter(x=d.index, y=d['MA50'], name="MA50", line=dict(color='royalblue')), secondary_y=False)
        fig.update_layout(paper_bgcolor='black', plot_bgcolor='black', font=dict(color='white'), height=600)
        st.plotly_chart(fig, use_container_width=True)
