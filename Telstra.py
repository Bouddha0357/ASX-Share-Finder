import pandas as pd
import yfinance as yf
import requests
import io
import time

def get_asx_tech_signals():
    # 1. Download official ASX list
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    response = requests.get(url)
    df_asx = pd.read_csv(io.StringIO(response.text), skiprows=1)

    # 2. Filter for Tech
    tech_df = df_asx[df_asx['GICS industry group'] == 'Information Technology']
    tickers = [f"{code}.AX" for code in tech_df['ASX code']]

    final_results = []
    print(f"Scanning {len(tickers)} Tech stocks...")

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            
            # Prefilters: Cap ($50M-$500M)
            fast = stock.fast_info
            mkt_cap = fast.get('market_cap', 0)
            if not (50_000_000 <= mkt_cap <= 500_000_000): continue

            # Get 210 days of data (need extra for MA200 slope)
            hist = stock.history(period="250d")
            if len(hist) < 205: continue

            # Volume Value Check (> $200k)
            avg_val = (hist['Close'] * hist['Volume']).tail(20).mean()
            if avg_val < 200_000: continue

            # Calculate Techncials
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            hist['MA50'] = hist['Close'].rolling(window=50).mean()
            hist['MA200'] = hist['Close'].rolling(window=200).mean()
            
            # Your Core Signal
            hist['Signal'] = (hist['MA20'] / hist['MA50']) - 1
            
            # Slope Calculation (Last 5 days of MA200)
            ma200_now = hist['MA200'].iloc[-1]
            ma200_prev = hist['MA200'].iloc[-6]
            slope_score = ((ma200_now - ma200_prev) / ma200_prev) * 100

            # STRATEGY LOGIC
            recent_signals = hist['Signal'].tail(5)
            # 1. Deep Pullback (-8%)
            # 2. 4-day growth streak
            # 3. MA200 is NOT falling (Slope >= 0)
            if recent_signals.iloc[-1] < -0.08 and \
               all(recent_signals.diff().dropna() > 0) and \
               slope_score >= 0:
                
                final_results.append({
                    'Ticker': ticker,
                    'Price': round(hist['Close'].iloc[-1], 2),
                    'Pullback %': f"{round(recent_signals.iloc[-1] * 100, 2)}%",
                    'Trend Slope': round(slope_score, 4), # Higher is stronger trend
                    'Mkt Cap': f"${round(mkt_cap/1e6)}M"
                })

            time.sleep(0.05)
        except: continue

    # Output sorted by Trend Slope (Strongest trends first)
    return pd.DataFrame(final_results).sort_values(by='Trend Slope', ascending=False)

print(get_asx_tech_signals())
