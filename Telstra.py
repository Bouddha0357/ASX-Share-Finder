import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import time

st.set_page_config(page_title="ASX Tech Funnel", layout="wide")
st.title("🕵️‍♂️ ASX Tech Strategy: Pullback + Trend")

# --- USER CONTROLS ---
st.sidebar.header("Filter Settings")
min_cap = st.sidebar.number_input("Min Market Cap ($M)", value=50) * 1_000_000
max_cap = st.sidebar.number_input("Max Market Cap ($M)", value=500) * 1_000_000
min_vol = st.sidebar.number_input("Min Daily Volume ($k)", value=200) * 1_000

def run_live_scan():
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()

        tech_keywords = [
            'Software & Services', 
            'Technology Hardware & Equipment', 
            'Semiconductors & Semiconductor Equipment'
        ]

        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        tech_df = df_asx[df_asx[sec_col].isin(tech_keywords)]
        tickers = [f"{c}.AX" for c in tech_df[cod_col]]
    except Exception as e:
        st.error(f"Failed to load ASX Directory: {e}")
        return

    # --- DASHBOARD ---
    m1, m2, m3, m4 = st.columns(4)
    stat_total = m1.metric("Tech Universe", len(tickers))
    stat_cap = m2.metric("Passed Cap", "0")
    stat_vol = m3.metric("Passed Vol", "0")
    stat_signal = m4.metric("BUY SIGNALS", "0")

    table_placeholder = st.empty()
    log_placeholder = st.empty()
    
    results = []
    counts = {"cap": 0, "vol": 0, "signal": 0}
    session = requests.Session()

    for i, ticker in enumerate(tickers):
        log_placeholder.text(f"Processing {ticker} ({i+1}/{len(tickers)})...")
        
        try:
            stock = yf.Ticker(ticker, session=session)
            
            # FAILSAFE MARKET CAP: Try fast_info, then basic info
            mcap = stock.fast_info.get('market_cap', 0)
            if mcap == 0: # Backup check
                mcap = stock.info.get('marketCap', 0)
            
            # Check if it fits the range
            if min_cap <= mcap <= max_cap:
                counts["cap"] += 1
                stat_cap.metric("Passed Cap", counts["cap"])
                
                hist = stock.history(period="250d")
                if len(hist) < 205: continue
                
                # Liquidity check
                avg_val = (hist['Close'] * hist['Volume']).tail(20).mean()
                if avg_val >= min_vol:
                    counts["vol"] += 1
                    stat_vol.metric("Passed Vol", counts["vol"])
                    
                    # Technicals
                    hist['MA20'] = hist['Close'].rolling(window=20).mean()
                    hist['MA50'] = hist['Close'].rolling(window=50).mean()
                    hist['MA200'] = hist['Close'].rolling(window=200).mean()
                    
                    hist['Signal'] = (hist['MA20'] / hist['MA50']) - 1
                    recent = hist['Signal'].tail(5)
                    
                    # MA200 Slope
                    slope = ((hist['MA200'].iloc[-1] - hist['MA200'].iloc[-6]) / hist['MA200'].iloc[-6]) * 100

                    if recent.iloc[-1] < -0.08 and all(recent.diff().dropna() > 0) and slope >= 0:
                        counts["signal"] += 1
                        stat_signal.metric("BUY SIGNALS", counts["signal"])
                        
                        results.append({
                            "Ticker": ticker,
                            "Price": round(hist['Close'].iloc[-1], 3),
                            "Pullback %": f"{round(recent.iloc[-1]*100, 1)}%",
                            "Trend Slope": round(slope, 4),
                            "Mkt Cap": f"${int(mcap/1e6)}M"
                        })
                        
                        df_display = pd.DataFrame(results).sort_values(by='Trend Slope', ascending=False)
                        table_placeholder.dataframe(df_display, use_container_width=True)

            time.sleep(0.05)
        except Exception:
            continue

    log_placeholder.success("Scan Finished.")

if st.button('🚀 Run Strategy Scan'):
    run_live_scan()
