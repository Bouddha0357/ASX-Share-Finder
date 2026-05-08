import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io

st.set_page_config(page_title="ASX Batch Scanner", layout="wide")
st.title("⚡ ASX Tech: High-Speed Batch Scanner")

def run_strategy():
    # 1. Get the Tickers from ASX
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        
        tech_groups = ['Software & Services', 'Technology Hardware & Equipment', 'Semiconductors & Semiconductor Equipment']
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        tech_df = df_asx[df_asx[sec_col].isin(tech_groups)]
        tickers = [f"{c}.AX" for c in tech_df[cod_col]]
    except Exception as e:
        st.error(f"Failed to load ASX list: {e}")
        return

    st.info(f"Attempting to batch download data for {len(tickers)} companies...")

    # 2. THE BATCH DOWNLOAD (This is the magic part)
    # This downloads one big table of Close prices for everyone at once
    try:
        data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=True)
        
        if data.empty:
            st.error("Yahoo returned NO data. They may have blocked this session. Try again in 5 minutes.")
            return

        close_prices = data['Close']
        volumes = data['Volume']
    except Exception as e:
        st.error(f"Batch Download Error: {e}")
        return

    # 3. PROCESS THE DATA
    results = []
    
    for ticker in tickers:
        try:
            # Get individual series
            prices = close_prices[ticker].dropna()
            vols = volumes[ticker].dropna()
            
            if len(prices) < 205: continue
            
            # 1. Size Proxy: Turnover (Last 20 days average)
            daily_turnover = (prices * vols).tail(20).mean()
            if daily_turnover < 100_000: continue # Only stocks trading $100k+ daily
            
            # 2. Moving Averages
            ma20 = prices.rolling(20).mean()
            ma50 = prices.rolling(50).mean()
            ma200 = prices.rolling(200).mean()
            
            # 3. The Signal (Pullback from MA50)
            pullback = (ma20.iloc[-1] / ma50.iloc[-1]) - 1
            
            # 4. Trend Slope (MA200 direction)
            slope = (ma200.iloc[-1] - ma200.iloc[-6]) / ma200.iloc[-6]
            
            # Logic: -8% pullback, MA200 is flat or up
            if pullback < -0.08 and slope >= 0:
                results.append({
                    "Ticker": ticker,
                    "Price": round(prices.iloc[-1], 3),
                    "Pullback": f"{round(pullback*100, 1)}%",
                    "Turnover": f"${int(daily_turnover/1000)}k",
                    "Trend": "Bullish" if slope > 0 else "Flat"
                })
        except:
            continue

    if results:
        st.success(f"Found {len(results)} potential setups!")
        st.dataframe(pd.DataFrame(results))
    else:
        st.warning("No stocks met the criteria today. Try widening the filters.")

if st.button('🚀 Run Batch Strategy'):
    run_strategy()
