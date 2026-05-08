import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import time

st.set_page_config(page_title="ASX Tech Funnel", layout="wide")
st.title("🕵️‍♂️ ASX Tech Strategy: Pullback + Trend")

def run_live_scan():
    # --- 1. DOWNLOAD & TARGET TECH SECTORS ---
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        # ASX CSV usually needs to skip 2-3 rows to find the header
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()

        # Define the exact Tech groups from your list
        tech_keywords = [
            'Software & Services', 
            'Technology Hardware & Equipment', 
            'Semiconductors & Semiconductor Equipment'
        ]

        # Find columns dynamically
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        # Filter for our 3 specific tech groups
        tech_df = df_asx[df_asx[sec_col].isin(tech_keywords)]
        tickers = [f"{c}.AX" for c in tech_df[cod_col]]
    except Exception as e:
        st.error(f"Failed to load ASX Directory: {e}")
        return

    # --- 2. DASHBOARD SETUP ---
    m1, m2, m3, m4 = st.columns(4)
    stat_total = m1.metric("Tech Universe", len(tickers))
    stat_cap = m2.metric("Passed Cap ($50M-$500M)", "0")
    stat_vol = m3.metric("Passed Vol (>$200k)", "0")
    stat_signal = m4.metric("BUY SIGNALS", "0")

    table_placeholder = st.empty()
    log_placeholder = st.empty()
    
    results = []
    counts = {"cap": 0, "vol": 0, "signal": 0}
    session = requests.Session()

    # --- 3. THE FUNNEL ---
    for i, ticker in enumerate(tickers):
        log_placeholder.text(f"Analyzing {ticker}...")
        
        try:
            stock = yf.Ticker(ticker, session=session)
            info = stock.fast_info
            
            # STAGE 1: Market Cap Filter
            mcap = info.get('market_cap', 0)
            if 50_000_000 <= mcap <= 500_000_000:
                counts["cap"] += 1
                stat_cap.metric("Passed Cap ($50M-$500M)", counts["cap"])
                
                # STAGE 2: Data & Volume Filter
                # We need 205+ days for a 200MA and a 5-day slope check
                hist = stock.history(period="250d")
                if len(hist) < 205: continue
                
                avg_val = (hist['Close'] * hist['Volume']).tail(20).mean()
                if avg_val >= 200_000:
                    counts["vol"] += 1
                    stat_vol.metric("Passed Vol (>$200k)", counts["vol"])
                    
                    # STAGE 3: Technical Analysis (MA20/50 Pullback + MA200 Slope)
                    hist['MA20'] = hist['Close'].rolling(window=20).mean()
                    hist['MA50'] = hist['Close'].rolling(window=50).mean()
                    hist['MA200'] = hist['Close'].rolling(window=200).mean()
                    
                    # Core Signal logic
                    hist['Signal'] = (hist['MA20'] / hist['MA50']) - 1
                    recent_signals = hist['Signal'].tail(5)
                    
                    # Trend Slope logic (Positive progression over last 5 days)
                    ma200_now = hist['MA200'].iloc[-1]
                    ma200_prev = hist['MA200'].iloc[-6]
                    slope = ((ma200_now - ma200_prev) / ma200_prev) * 100

                    # FINAL CRITERIA CHECK
                    # 1. Pullback below -8%
                    # 2. 4 days of signal growth
                    # 3. MA200 is flat or positive (Slope >= 0)
                    if recent_signals.iloc[-1] < -0.08 and \
                       all(recent_signals.diff().dropna() > 0) and \
                       slope >= 0:
                        
                        counts["signal"] += 1
                        stat_signal.metric("BUY SIGNALS", counts["signal"])
                        
                        results.append({
                            "Ticker": ticker,
                            "Price": round(hist['Close'].iloc[-1], 3),
                            "Pullback %": f"{round(recent_signals.iloc[-1]*100, 1)}%",
                            "MA200 Slope": round(slope, 4),
                            "Mkt Cap": f"${int(mcap/1e6)}M"
                        })
                        
                        # Display results immediately and sort by best trend slope
                        df_display = pd.DataFrame(results).sort_values(by='MA200 Slope', ascending=False)
                        table_placeholder.dataframe(df_display, use_container_width=True)

            # Small delay to avoid API blocking
            time.sleep(0.05)
        except Exception:
            continue

    log_placeholder.success(f"Finished! Checked {len(tickers)} Tech companies.")

if st.button('🚀 Run Strategy Scan'):
    run_live_scan()
