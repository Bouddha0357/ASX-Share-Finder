import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="ASX Tech Picker", layout="wide")
st.title("🚀 ASX Tech Pullback Finder (Simplified)")

def get_asx_tech_signals():
    # 1. Robust ASX List Download
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        # We try to read the CSV and find where the headers start
        data_content = response.text
        df_asx = pd.read_csv(io.StringIO(data_content), skiprows=2)
        
        # Cleanup column names
        df_asx.columns = df_asx.columns.str.strip()
        
        # Locate the columns dynamically by keyword
        sector_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        code_col = [c for c in df_asx.columns if 'code' in c.lower()][0]

        # Filter for Tech
        tech_df = df_asx[df_asx[sector_col].str.contains('Information Technology', na=False, case=False)]
        tickers = [f"{code}.AX" for code in tech_df[code_col]]
    except Exception as e:
        st.error(f"Failed to find tickers: {e}")
        return pd.DataFrame()

    st.info(f"Scanning {len(tickers)} Tech tickers for Pullback signals...")
    progress_bar = st.progress(0)
    final_results = []

    # Use a session to prevent Yahoo from blocking the Streamlit IP
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    for i, ticker in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        try:
            stock = yf.Ticker(ticker, session=session)
            # Use fast_info for speed
            fast = stock.fast_info
            
            # 1. Market Cap Filter ($50M - $500M)
            mkt_cap = fast.get('market_cap', 0)
            if not (50_000_000 <= mkt_cap <= 500_000_000): continue

            # 2. Get 100 days of history (much faster than 250d)
            hist = stock.history(period="100d")
            if len(hist) < 55: continue

            # 3. Volume Value Check (> $200k)
            avg_val = (hist['Close'] * hist['Volume']).tail(20).mean()
            if avg_val < 200_000: continue

            # 4. Calculate Moving Averages
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            hist['MA50'] = hist['Close'].rolling(window=50).mean()
            hist['Signal'] = (hist['MA20'] / hist['MA50']) - 1
            
            # 5. Core Logic: -8% Pullback + 4-day recovery
            recent_signals = hist['Signal'].tail(5)
            
            # Current signal is deeply negative
            is_deep_pullback = recent_signals.iloc[-1] < -0.08
            # The signal has been rising for the last 4 days
            is_curling_up = all(recent_signals.diff().dropna() > 0)

            if is_deep_pullback and is_curling_up:
                final_results.append({
                    'Ticker': ticker,
                    'Price': round(hist['Close'].iloc[-1], 3),
                    'Pullback %': f"{round(recent_signals.iloc[-1] * 100, 2)}%",
                    'Mkt Cap': f"${round(mkt_cap/1e6)}M",
                    'Avg Daily $': f"${round(avg_val/1000)}k"
                })
            
            # Safety delay
            time.sleep(0.1)
            
        except:
            continue

    if not final_results:
        return pd.DataFrame()
    
    return pd.DataFrame(final_results)

# --- EXECUTION ---
if st.button('Start Tech Scan'):
    with st.spinner('Calculating signals...'):
        df = get_asx_tech_signals()
        
        if df.empty:
            st.warning("No Tech stocks match the criteria right now.")
        else:
            st.success(f"Found {len(df)} matches!")
            st.dataframe(df, use_container_width=True)
