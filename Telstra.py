import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import time

st.set_page_config(page_title="ASX Live Screener", layout="wide")
st.title("🕵️‍♂️ Live ASX Tech Funnel")

def run_live_scan():
    # --- 1. INITIAL SCRAPE ---
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        
        # Sector/Code column detection
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        # Initial Filter: TECH ONLY
        tech_df = df_asx[df_asx[sec_col].str.contains('Information Technology', na=False, case=False)]
        tickers = [f"{c}.AX" for c in tech_df[cod_col]]
    except Exception as e:
        st.error(f"Scrape failed: {e}")
        return

    # --- 2. LIVE DASHBOARD SETUP ---
    col1, col2, col3, col4 = st.columns(4)
    stat_total = col1.metric("Tech Universe", len(tickers))
    stat_cap = col2.metric("Passed Cap", "0")
    stat_vol = col3.metric("Passed Vol", "0")
    stat_signal = col4.metric("BUY SIGNALS", "0")

    st.subheader("Live Processing Feed")
    # This 'placeholder' is the secret—it lets us rewrite the table in real-time
    table_placeholder = st.empty()
    log_placeholder = st.empty()
    
    results = []
    counts = {"cap": 0, "vol": 0, "signal": 0}
    
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    # --- 3. THE LOOP ---
    for i, ticker in enumerate(tickers):
        log_placeholder.text(f"Checking {ticker} ({i+1}/{len(tickers)})...")
        
        try:
            stock = yf.Ticker(ticker, session=session)
            fast = stock.fast_info
            
            # Market Cap Check
            mcap = fast.get('market_cap', 0)
            if 50_000_000 <= mcap <= 500_000_000:
                counts["cap"] += 1
                stat_cap.metric("Passed Cap", counts["cap"])
                
                # Volume Check
                hist = stock.history(period="60d")
                if len(hist) < 50: continue
                
                avg_val = (hist['Close'] * hist['Volume']).tail(20).mean()
                if avg_val >= 200_000:
                    counts["vol"] += 1
                    stat_vol.metric("Passed Vol", counts["vol"])
                    
                    # MA Logic Check
                    hist['MA20'] = hist['Close'].rolling(window=20).mean()
                    hist['MA50'] = hist['Close'].rolling(window=50).mean()
                    hist['Signal'] = (hist['MA20'] / hist['MA50']) - 1
                    
                    recent = hist['Signal'].tail(5)
                    if recent.iloc[-1] < -0.08 and all(recent.diff().dropna() > 0):
                        counts["signal"] += 1
                        stat_signal.metric("BUY SIGNALS", counts["signal"])
                        
                        # Add to our live list
                        results.append({
                            "Ticker": ticker,
                            "Price": round(hist['Close'].iloc[-1], 3),
                            "Pullback %": f"{round(recent.iloc[-1]*100, 1)}%",
                            "Mkt Cap": f"${int(mcap/1e6)}M"
                        })
                        
                        # UPDATE THE TABLE IMMEDIATELY
                        table_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)

            time.sleep(0.05) # Keep it smooth
        except:
            continue

    log_placeholder.success("✅ Scan Complete!")

if st.button('🚀 Start Real-Time Funnel Scan'):
    run_live_scan()
