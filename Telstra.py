import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="ASX Micro-Cap Alpha", layout="wide")
st.title("🚀 ASX Alpha: $50M - $500M Growth Scanner")

# --- INITIALIZE MEMORY ---
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

    st.info(f"Scanning {len(tickers)} companies for Micro-Cap Alpha...")
    
    # We need to fetch 'MarketCap' along with prices
    # Note: Market Cap in yfinance can be spotty for very small stocks, 
    # but for $50m+ it is generally reliable.
    data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=False)
    
    close_prices = data['Close']
    volumes = data['Volume']
    
    final_results = []
    temp_found_data = {}

    for ticker in tickers:
        try:
            # 1. PRICE DATA CHECK
            p = close_prices[ticker].dropna()
            v = volumes[ticker].dropna()
            if len(p) < 205: continue

            # 2. MARKET CAP FILTER (Crucial Step)
            # Fetching info for market cap (slows down scan slightly but essential)
            info = yf.Ticker(ticker).fast_info
            mcap = info.get('market_cap', 0)
            
            # Filter for $50M to $500M
            if not (50_000_000 <= mcap <= 500_000_000):
                continue

            # 3. LIQUIDITY & TREND FILTERS
            turnover = (p * v).tail(20).mean()
            if turnover < 30_000: continue # Lowered for smaller caps

            ma200 = p.rolling(200).mean()
            # HARD FLOOR RULE: Price must be above MA200
            if p.iloc[-1] < ma200.iloc[-1]: continue
            
            slope = (ma200.iloc[-1] - ma200.iloc[-6]) / ma200.iloc[-6]
            if slope < 0: continue

            # 4. PULLBACK & CURL LOGIC
            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            spread = (ma20 / ma50) - 1
            
            # Signal: -4% pullback and starting to curl up
            if spread.iloc[-1] < -0.04 and spread.iloc[-1] > spread.iloc[-2]:
                sector_label = filtered_df[filtered_df[cod_col] == ticker.replace('.AX','')][sec_col].values[0]
                
                final_results.append({
                    "Ticker": ticker,
                    "Sector": sector_label,
                    "Price": round(p.iloc[-1], 3),
                    "Mkt Cap": f"${int(mcap/1_000_000)}M",
                    "Pullback %": round(spread.iloc[-1] * 100, 2),
                    "Turnover": f"${int(turnover/1000)}k"
                })
                temp_found_data[ticker] = pd.DataFrame({'Close': p, 'MA20': ma20, 'MA50': ma50, 'MA200': ma200, 'Spread': spread})
        except: continue

    st.session_state.scan_results = pd.DataFrame(final_results) if final_results else None
    st.session_state.found_data = temp_found_data

# --- APP LAYOUT ---
if st.button('🚀 Scan for Growth Alpha'):
    run_strategy()

if st.session_state.scan_results is not None:
    df_final = st.session_state.scan_results.sort_values("Pullback %")
    st.success(f"Found {len(df_final)} High-Growth Setups!")
    st.dataframe(df_final, use_container_width=True)

    # ... [Insert the same Charting Logic from the previous response here] ...
