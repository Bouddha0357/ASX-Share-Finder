import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import time

st.set_page_config(page_title="ASX Tech Scanner", layout="wide")
st.title("🚀 ASX Tech: Liquidity & Trend Scanner")

# --- USER CONTROLS ---
st.sidebar.header("Strategy Settings")
# Instead of Mkt Cap, we use Daily Dollar Turnover as a proxy for 'size' and 'interest'
min_turnover = st.sidebar.number_input("Min Daily Turnover ($k)", value=100) * 1_000

def run_live_scan():
    # 1. Get Tickers
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()

        tech_keywords = ['Software & Services', 'Technology Hardware & Equipment', 'Semiconductors & Semiconductor Equipment']
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        tech_df = df_asx[df_asx[sec_col].isin(tech_keywords)]
        tickers = [f"{c}.AX" for c in tech_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    # --- DASHBOARD ---
    m1, m2, m3 = st.columns(3)
    stat_total = m1.metric("Tech Universe", len(tickers))
    stat_liq = m2.metric("Passed Liquidity", "0")
    stat_signal = m3.metric("BUY SIGNALS", "0")

    table_placeholder = st.empty()
    log_placeholder = st.empty()
    
    results = []
    counts = {"liq": 0, "signal": 0}
    session = requests.Session()

    for i, ticker in enumerate(tickers):
        log_placeholder.text(f"Scanning {ticker}...")
        
        try:
            stock = yf.Ticker(ticker, session=session)
            # Fetching 250 days to cover MA200 and Slope
            hist = stock.history(period="250d")
            
            if len(hist) < 205:
                continue

            # LIQUIDITY FILTER (Price * Volume)
            # This ensures the stock is "real" and active
            avg_daily_turnover = (hist['Close'] * hist['Volume']).tail(20).mean()
            
            if avg_daily_turnover >= min_turnover:
                counts["liq"] += 1
                stat_liq.metric("Passed Liquidity", counts["liq"])
                
                # TECHNICALS
                hist['MA20'] = hist['Close'].rolling(window=20).mean()
                hist['MA50'] = hist['Close'].rolling(window=50).mean()
                hist['MA200'] = hist['Close'].rolling(window=200).mean()
                
                # Pullback Signal
                hist['Signal'] = (hist['MA20'] / hist['MA50']) - 1
                recent = hist['Signal'].tail(5)
                
                # MA200 Slope (Is it a falling knife?)
                ma200_now = hist['MA200'].iloc[-1]
                ma200_prev = hist['MA200'].iloc[-6]
                slope = ((ma200_now - ma200_prev) / ma200_prev) * 100

                # CRITERIA: -8% pullback, 4-day curl up, MA200 not crashing
                if recent.iloc[-1] < -0.08 and all(recent.diff().dropna() > 0) and slope >= 0:
                    counts["signal"] += 1
                    stat_signal.metric("BUY SIGNALS", counts["signal"])
                    
                    results.append({
                        "Ticker": ticker,
                        "Price": round(hist['Close'].iloc[-1], 3),
                        "Pullback %": f"{round(recent.iloc[-1]*100, 1)}%",
                        "MA200 Slope": round(slope, 4),
                        "Daily Turnover": f"${int(avg_daily_turnover/1000)}k"
                    })
                    
                    df_display = pd.DataFrame(results).sort_values(by='MA200 Slope', ascending=False)
                    table_placeholder.dataframe(df_display, use_container_width=True)

            time.sleep(0.05)
        except:
            continue

    log_placeholder.success("Scan Complete.")

if st.button('🚀 Start Strategy Scan'):
    run_live_scan()
