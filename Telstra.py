import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go

st.set_page_config(page_title="ASX Alpha Diagnostic", layout="wide")
st.title("🔍 ASX Diagnostic Scanner")

# --- PARAMETERS ---
streak = st.sidebar.slider("Streak Days", 0, 5, 1) # Set to 0 to see ALL stocks
show_all = st.sidebar.checkbox("Show all stocks (Ignore momentum)", value=False)

def run_diagnostic():
    # 1. Fetch Tickers
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        # Adding 'Materials' to find the resilient gold/lithium stocks
        target_groups = ['Software & Services', 'Capital Goods', 'Materials', 'Health Care Equipment & Services']
        
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        # Limiting to top 100 for a fast diagnostic
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]][:100]
    except Exception as e:
        st.error(f"ASX CSV Error: {e}")
        return

    st.info(f"Scanning {len(tickers)} tickers... (May 13, 2026 Market Data)")
    
    # 2. Batch Download
    data = yf.download(tickers, period="100d", interval="1d", group_by='column', progress=False)
    
    if data.empty:
        st.error("🚨 Yahoo Finance returned NO data. You may be rate-limited. Try again in 15 mins.")
        return

    results = []
    
    for ticker in tickers:
        try:
            p = data['Close'][ticker].dropna()
            if len(p) < 50: continue
            
            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            log_spread = np.log(ma20 / ma50)
            diff = log_spread.diff()
            
            # Momentum logic
            is_recovering = (diff.tail(streak) > 0).all() if streak > 0 else True
            is_in_pullback = log_spread.iloc[-1] < 0
            
            # Diagnostic: Add everything if 'show_all' is checked, otherwise apply filters
            if show_all or (is_recovering and is_in_pullback):
                results.append({
                    "Ticker": ticker,
                    "Price": round(p.iloc[-1], 3),
                    "Log Gap": round(log_spread.iloc[-1], 4),
                    "Status": "Matched" if (is_recovering and is_in_pullback) else "Diagnostic"
                })
        except: continue

    if results:
        st.write(pd.DataFrame(results))
    else:
        st.warning("Still no matches. The market sell-off today is likely too deep for a recovery signal.")

if st.button("Run Diagnostic"):
    run_diagnostic()
