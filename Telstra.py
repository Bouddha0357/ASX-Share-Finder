import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io

st.set_page_config(page_title="ASX Diagnostic Scanner", layout="wide")
st.title("🔍 Strategy Diagnostic: Where are we losing them?")

def run_diagnostic():
    # 1. ASX LIST FETCH
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers, timeout=15)
    df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
    df_asx.columns = df_asx.columns.str.strip()
    
    tech_groups = ['Software & Services', 'Technology Hardware & Equipment', 'Semiconductors & Semiconductor Equipment']
    tech_df = df_asx[df_asx['GICS industry group'].isin(tech_groups)]
    tickers = [f"{c}.AX" for c in tech_df['ASX code']]

    # 2. BATCH DOWNLOAD
    st.write(f"📡 Fetching data for {len(tickers)} Tech companies...")
    data = yf.download(tickers, period="260d", interval="1d", group_by='column')
    
    if data.empty:
        st.error("Yahoo returned zero data. Check internet or try again.")
        return

    close_prices = data['Close']
    volumes = data['Volume']

    # 3. COUNTERS FOR DIAGNOSIS
    stats = {
        "Total Tech Tickers": len(tickers),
        "Dropped: No Data/New Listing": 0,
        "Dropped: Low Liquidity (<$100k/day)": 0,
        "Dropped: Negative Trend (Below MA200)": 0,
        "Dropped: No Pullback (Not -8% yet)": 0,
        "PASSED ALL FILTERS": 0
    }

    final_results = []

    for ticker in tickers:
        try:
            p = close_prices[ticker].dropna()
            v = volumes[ticker].dropna()

            # Filter 1: Data Integrity
            if len(p) < 205:
                stats["Dropped: No Data/New Listing"] += 1
                continue

            # Filter 2: Liquidity ($ Turnover)
            turnover = (p * v).tail(20).mean()
            if turnover < 100_000:
                stats["Dropped: Low Liquidity (<$100k/day)"] += 1
                continue

            # Filter 3: The Trend (MA200 Slope)
            ma200 = p.rolling(200).mean()
            slope = (ma200.iloc[-1] - ma200.iloc[-6]) / ma200.iloc[-6]
            if slope < 0:
                stats["Dropped: Negative Trend (Below MA200)"] += 1
                continue

            # Filter 4: The Pullback (-8%)
            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            pullback = (ma20.iloc[-1] / ma50.iloc[-1]) - 1
            
            if pullback > -0.08:
                stats["Dropped: No Pullback (Not -8% yet)"] += 1
                continue

            # SUCCESS
            stats["PASSED ALL FILTERS"] += 1
            final_results.append({
                "Ticker": ticker,
                "Price": round(p.iloc[-1], 2),
                "Pullback": f"{round(pullback*100,1)}%",
                "Turnover": f"${int(turnover/1000)}k"
            })
        except:
            continue

    # --- DISPLAY DIAGNOSTICS ---
    st.subheader("📊 Funnel Breakdown")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        for label, count in stats.items():
            st.metric(label, count)

    with col2:
        if final_results:
            st.success("Matches Found!")
            st.dataframe(pd.DataFrame(final_results))
        else:
            st.warning("The funnel reached zero. Look at the 'Dropped' metrics above to see which filter is too tight.")

if st.button('Run Diagnostic Scan'):
    run_diagnostic()
