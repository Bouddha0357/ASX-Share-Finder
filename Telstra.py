import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io

st.set_page_config(page_title="ASX Multi-Sector Scanner", layout="wide")
st.title("🚀 ASX Multi-Sector Pullback Strategy")

def run_strategy():
    # 1. FETCH TICKERS & EXPAND SECTORS
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        
        # Expanded Sector List
        target_groups = [
            'Software & Services', 
            'Technology Hardware & Equipment', 
            'Semiconductors & Semiconductor Equipment',
            'Capital Goods',
            'Commercial & Professional Services'
        ]
        
        # Locate columns dynamically
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    # --- 2. BATCH DOWNLOAD ---
    st.info(f"Scanning {len(tickers)} companies across 5 major sectors...")
    # Progress bar for the batch download
    data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=False)
    
    if data.empty:
        st.error("No data returned from Yahoo.")
        return

    close_prices = data['Close']
    volumes = data['Volume']
    final_results = []

    # --- 3. PROCESSING WITH "REAL-WORLD" FILTERS ---
    for ticker in tickers:
        try:
            p = close_prices[ticker].dropna()
            v = volumes[ticker].dropna()

            if len(p) < 205: continue

            # Filter 1: Liquidity Floor ($50k/day)
            turnover = (p * v).tail(20).mean()
            if turnover < 50_000: continue

            # Filter 2: Trend Safety (MA200 Flat or Rising)
            ma200 = p.rolling(200).mean()
            # Slope check (current vs 5 days ago)
            slope = (ma200.iloc[-1] - ma200.iloc[-6]) / ma200.iloc[-6]
            if slope < 0: continue

            # Filter 3: Pullback Logic
            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            pullback = (ma20.iloc[-1] / ma50.iloc[-1]) - 1
            
            # Curl check: Is the pullback leveling off or starting to rise?
            is_curling = (ma20.iloc[-1] / ma50.iloc[-1]) > (ma20.iloc[-2] / ma50.iloc[-2])

            # Buy Signal: -4% pullback and curling up
            if pullback < -0.04 and is_curling:
                # Find the sector for this ticker to display in table
                sector_label = filtered_df[filtered_df[cod_col] == ticker.replace('.AX','')][sec_col].values[0]
                
                final_results.append({
                    "Ticker": ticker,
                    "Sector": sector_label,
                    "Price": round(p.iloc[-1], 2),
                    "Pullback": f"{round(pullback*100, 1)}%",
                    "Turnover": f"${int(turnover/1000)}k",
                    "Trend": "Rising" if slope > 0.001 else "Flat"
                })
        except:
            continue

    # --- 4. OUTPUT ---
    if final_results:
        st.success(f"Strategy found {len(final_results)} matches across the expanded sectors!")
        st.dataframe(pd.DataFrame(final_results).sort_values("Pullback"), use_container_width=True)
    else:
        st.warning("No matches found. This suggests a broad market surge where nothing is 'on sale' or a broad decline where trends have broken.")

if st.button('Run Master Scan'):
    run_strategy()
