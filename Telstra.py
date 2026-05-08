import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="ASX Tech Picker", layout="wide")
st.title("🚀 ASX 'Blind' Tech Pullback Finder")

def get_asx_tech_signals():
    # 1. Download official ASX list with Error Handling
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        # The ASX CSV usually has 1-3 rows of junk at the top. 
        # We use 'header=0' and skip the first few lines to find the actual columns.
        df_asx = pd.read_csv(io.StringIO(response.text), skiprows=2)
        
        # Clean column names (remove whitespace)
        df_asx.columns = df_asx.columns.str.strip()
        
        # Find the right columns even if names vary slightly
        sector_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        code_col = [c for c in df_asx.columns if 'code' in c.lower()][0]

        # Filter for Information Technology
        tech_df = df_asx[df_asx[sector_col].str.contains('Information Technology', na=False, case=False)]
        tickers = [f"{code}.AX" for code in tech_df[code_col]]
    except Exception as e:
        st.error(f"Error loading ASX Directory: {e}")
        return pd.DataFrame()

    st.write(f"Scanning {len(tickers)} Tech companies...")
    progress_bar = st.progress(0)
    final_results = []

    # Create a session to help avoid 429 Rate Limits
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    for i, ticker in enumerate(tickers):
        progress_bar.progress((i + 1) / len(tickers))
        try:
            stock = yf.Ticker(ticker, session=session)
            fast = stock.fast_info
            
            # Market Cap Filter ($50M - $500M)
            mkt_cap = fast.get('market_cap', 0)
            if not (50_000_000 <= mkt_cap <= 500_000_000): continue

            # Get Data
            hist = stock.history(period="250d")
            if len(hist) < 210: continue

            # Volume Value Check (> $200k)
            avg_val = (hist['Close'] * hist['Volume']).tail(20).mean()
            if avg_val < 200_000: continue

            # Technicals
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            hist['MA50'] = hist['Close'].rolling(window=50).mean()
            hist['MA200'] = hist['Close'].rolling(window=200).mean()
            hist['Signal'] = (hist['MA20'] / hist['MA50']) - 1
            
            # Slope of MA200 (Last 5 days)
            slope = ((hist['MA200'].iloc[-1] - hist['MA200'].iloc[-6]) / hist['MA200'].iloc[-6]) * 100

            # STRATEGY CHECK
            recent = hist['Signal'].tail(5)
            # Pullback < -8%, 4-day growth, MA200 not falling
            if recent.iloc[-1] < -0.08 and all(recent.diff().dropna() > 0) and slope >= 0:
                final_results.append({
                    'Ticker': ticker,
                    'Price': round(hist['Close'].iloc[-1], 3),
                    'Pullback %': f"{round(recent.iloc[-1] * 100, 2)}%",
                    'Trend Slope': round(slope, 4),
                    'Mkt Cap': f"${round(mkt_cap/1e6)}M"
                })
            
            # Small sleep to prevent Yahoo blocking you
            time.sleep(0.1)
        except:
            continue

    # Return results as a DataFrame
    if not final_results:
        return pd.DataFrame()
    
    return pd.DataFrame(final_results).sort_values(by='Trend Slope', ascending=False)

# --- MAIN EXECUTION ---
if st.button('Run Market Scan'):
    with st.spinner('Analyzing ASX Technology Sector...'):
        df_final = get_asx_tech_signals()
        
        if df_final.empty:
            st.warning("No stocks met your strict criteria today. Try again tomorrow!")
        else:
            st.success(f"Found {len(df_final)} potential entries!")
            st.dataframe(df_final, use_container_width=True)
