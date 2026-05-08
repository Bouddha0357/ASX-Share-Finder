import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import time
import random

st.set_page_config(page_title="ASX Stealth Scanner", layout="wide")
st.title("🕵️‍♂️ ASX Tech Stealth Funnel")

def run_live_scan():
    # --- 1. DOWNLOAD TICKERS ---
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        # Use a real browser user-agent
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()

        # The specific GICS groups we want
        tech_groups = ['Software & Services', 'Technology Hardware & Equipment', 'Semiconductors & Semiconductor Equipment']
        
        # Locate columns
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        tech_df = df_asx[df_asx[sec_col].isin(tech_groups)]
        tickers = [f"{c}.AX" for c in tech_df[cod_col]]
    except Exception as e:
        st.error(f"ASX CSV Error: {e}")
        return

    # --- 2. LIVE DASHBOARD ---
    m1, m2, m3 = st.columns(3)
    stat_total = m1.metric("Tech Universe", len(tickers))
    stat_liq = m2.metric("Passed Liquidity", "0")
    stat_signal = m3.metric("BUY SIGNALS", "0")

    table_placeholder = st.empty()
    log_placeholder = st.empty()
    
    results = []
    counts = {"liq": 0, "signal": 0}
    
    # We use a single session but refresh it if it gets blocked
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'})

    # --- 3. THE STEALTH LOOP ---
    for i, ticker in enumerate(tickers):
        log_placeholder.text(f"Scanning {ticker}... ({i+1}/{len(tickers)})")
        
        try:
            # We skip 'info' and 'fast_info' entirely (they are the most blocked)
            # We jump straight to history, which is often more stable
            stock = yf.Ticker(ticker, session=session)
            hist = stock.history(period="250d", interval="1d")
            
            if hist.empty or len(hist) < 205:
                continue

            # Calculate Daily Turnover (Value) as our ONLY size filter
            # If a stock trades $100k+ a day, it's liquid enough
            avg_daily_val = (hist['Close'] * hist['Volume']).tail(20).mean()
            
            if avg_daily_val >= 100_000: # Lowered to 100k to ensure we find matches
                counts["liq"] += 1
                stat_liq.metric("Passed Liquidity", counts["liq"])
                
                # TECHNICALS
                hist['MA20'] = hist['Close'].rolling(window=20).mean()
                hist['MA50'] = hist['Close'].rolling(window=50).mean()
                hist['MA200'] = hist['Close'].rolling(window=200).mean()
                
                # Core Signal
                hist['Signal'] = (hist['MA20'] / hist['MA50']) - 1
                recent = hist['Signal'].tail(5)
                
                # Trend Slope
                ma200_now = hist['MA200'].iloc[-1]
                ma200_prev = hist['MA200'].iloc[-6]
                slope = ((ma200_now - ma200_prev) / ma200_prev) * 100

                # Final Rules
                if recent.iloc[-1] < -0.08 and all(recent.diff().dropna() > 0) and slope >= 0:
                    counts["signal"] += 1
                    stat_signal.metric("BUY SIGNALS", counts["signal"])
                    
                    results.append({
                        "Ticker": ticker,
                        "Price": f"${round(hist['Close'].iloc[-1], 3)}",
                        "Pullback": f"{round(recent.iloc[-1]*100, 1)}%",
                        "Slope": round(slope, 4),
                        "Daily $": f"${int(avg_daily_val/1000)}k"
                    })
                    table_placeholder.dataframe(pd.DataFrame(results))

            # RANDOM DELAY: Key to staying unblocked
            time.sleep(random.uniform(0.1, 0.4))
            
        except Exception:
            continue

    log_placeholder.success("✅ Stealth Scan Finished.")

if st.button('🚀 Start Stealth Scan'):
    run_live_scan()
