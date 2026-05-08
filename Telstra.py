import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="ASX Micro-Cap Alpha", layout="wide")
st.title("🚀 ASX Alpha: High-Speed $50M-$500M Scanner")

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
        
        target_groups = ['Software & Services', 'Technology Hardware & Equipment', 
                         'Semiconductors & Semiconductor Equipment', 'Capital Goods',
                         'Commercial & Professional Services']
        
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    # 2. FAST BATCH DOWNLOAD (Prices only)
    status_text = st.empty()
    status_text.info(f"⚡ Batch downloading {len(tickers)} companies...")
    
    data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=False)
    close_prices = data['Close']
    volumes = data['Volume']
    
    final_results = []
    temp_found_data = {}

    # 3. ANALYSIS LOOP
    for i, ticker in enumerate(tickers):
        if i % 20 == 0:
            status_text.info(f"Analyzing {i}/{len(tickers)} stocks...")
            
        try:
            p = close_prices[ticker].dropna()
            v = volumes[ticker].dropna()
            if len(p) < 205: continue

            # Technical Filters FIRST (Fast)
          
            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            spread = (ma20 / ma50) - 1
            
            # Pullback + Curl Logic
            if spread.iloc[-1] < -0.04 and spread.iloc[-1] > spread.iloc[-2]:
                
                # ONLY NOW do we check Market Cap (Saves 90% of time)
                info = yf.Ticker(ticker).fast_info
                mcap = info.get('market_cap', 0)
                
                if 50_000_000 <= mcap <= 5_000_000_000:
                    turnover = (p * v).tail(20).mean()
                    sector_label = filtered_df[filtered_df[cod_col] == ticker.replace('.AX','')][sec_col].values[0]
                    
                    final_results.append({
                        "Ticker": ticker,
                        "Sector": sector_label,
                        "Price": round(p.iloc[-1], 3),
                        "Mkt Cap": f"${int(mcap/1_000_000)}M",
                        "Pullback %": round(spread.iloc[-1] * 100, 2),
                        "Turnover": f"${int(turnover/1000)}k"
                    })
                    temp_found_data[ticker] = pd.DataFrame({
                        'Close': p, 'MA20': ma20, 'MA50': ma50, 'MA200': ma200, 'Spread': spread
                    })
        except: continue

    status_text.empty()
    st.session_state.scan_results = pd.DataFrame(final_results) if final_results else None
    st.session_state.found_data = temp_found_data

# --- APP LAYOUT ---
if st.button('🚀 Execute Alpha Scan'):
    run_strategy()

# (Include the same Table and Charting logic here as before)
