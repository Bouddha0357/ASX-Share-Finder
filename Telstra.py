import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io

st.set_page_config(page_title="ASX Master Strategy", layout="wide")
st.title("🎯 ASX Alpha: Pullback Strategy")
st.markdown("Scanning for high-liquidity stocks in an uptrend with a fresh pullback.")

def run_strategy():
    # 1. FETCH & FILTER TICKERS
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        
        target_groups = [
            'Software & Services', 
            'Technology Hardware & Equipment', 
            'Semiconductors & Semiconductor Equipment',
            'Capital Goods',
            'Commercial & Professional Services'
        ]
        
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    # 2. BATCH DOWNLOAD
    st.info(f"Checking {len(tickers)} companies across target sectors...")
    data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=False)
    
    if data.empty:
        st.error("No data returned from Yahoo. Try again in a minute.")
        return

    close_prices = data['Close']
    volumes = data['Volume']
    final_results = []

    # 3. ANALYSIS LOOP
    for ticker in tickers:
        try:
            p = close_prices[ticker].dropna()
            v = volumes[ticker].dropna()

            if len(p) < 205: continue

            # Filter: Liquidity ($50k/day min)
            turnover = (p * v).tail(20).mean()
            if turnover < 50_000: continue

            # Filter: MA200 Slope (Long term trend)
            ma200 = p.rolling(200).mean()
            slope = (ma200.iloc[-1] - ma200.iloc[-6]) / ma200.iloc[-6]
            if slope < 0: continue

            # Filter: Pullback Logic (-4% MA20/MA50 gap)
            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            pullback_val = (ma20.iloc[-1] / ma50.iloc[-1]) - 1
            
            # Curl Logic: Is the signal improving compared to yesterday?
            sig_today = (ma20.iloc[-1] / ma50.iloc[-1])
            sig_yesterday = (ma20.iloc[-2] / ma50.iloc[-2])

            if pullback_val < -0.04 and sig_today > sig_yesterday:
                sector_label = filtered_df[filtered_df[cod_col] == ticker.replace('.AX','')][sec_col].values[0]
                
                final_results.append({
                    "Ticker": ticker,
                    "Sector": sector_label,
                    "Price": round(p.iloc[-1], 2),
                    "Pullback %": round(pullback_val * 100, 2),
                    "Daily Turnover": f"${round(turnover/1000)}k",
                    "Trend": "Rising" if slope > 0.001 else "Stable"
                })
        except:
            continue

    # 4. RESULTS DISPLAY
    if final_results:
        # Sort by the deepest pullback (most 'on sale')
        df_final = pd.DataFrame(final_results).sort_values("Pullback %", ascending=True)
        # Clean up the index display
        df_final.index = range(1, len(df_final) + 1)
        
        st.success(f"Found {len(df_final)} actionable setups!")
        st.table(df_final) # Using st.table for a cleaner look than the interactive dataframe
    else:
        st.warning("No matches currently meet the 'Uptrend + Pullback' criteria.")

if st.button('🚀 Execute Master Scan'):
    run_strategy()
