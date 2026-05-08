import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="ASX Log-Recovery Alpha", layout="wide")
st.title("🚀 ASX Alpha: High-Vol Recovery Scanner")

# --- MEMORY ---
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None
if 'found_data' not in st.session_state:
    st.session_state.found_data = {}

def run_strategy():
    # 1. FETCH TICKERS
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        
        target_groups = ['Software & Services', 'Technology Hardware & Equipment', 
                         'Semiconductors & Semiconductor Equipment', 'Capital Goods',
                         'Commercial & Professional Services']
        
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    status_text = st.empty()
    status_text.info(f"⚡ Batch downloading {len(tickers)} tickers...")
    
    data = yf.download(tickers, period="300d", interval="1d", group_by='column', progress=False)
    close_prices = data['Close']
    volumes = data['Volume']
    
    final_results = []
    temp_found_data = {}

    for i, ticker in enumerate(tickers):
        try:
            p = close_prices[ticker].dropna()
            if len(p) < 60: continue

            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            log_spread = np.log(ma20 / ma50)
            
            # Use the slider value for the streak
            diff = log_spread.diff() 
            recent_diffs = diff.tail(streak) # <--- SENSITIVITY ADJUSTMENT
            
            # LOGIC: Is it rising for 'X' days?
            if (recent_diffs > 0).all():
        
            
            # Condition: Narrowing the gap (recovering) for 4 straight days
            # We keep the condition that it must still be a 'pullback' (log_spread < 0)
            if log_spread.iloc[-1] < 0 and (recent_diffs > 0).all():
                
                # 4. Market Cap Filter ($50M - $500M)
                info = yf.Ticker(ticker).fast_info
                mcap = info.get('market_cap', 0)
                
                if 50_000_000 <= mcap <= 500_000_000:
                    turnover = (p * v).tail(20).mean()
                    sector_label = filtered_df[filtered_df[cod_col] == ticker.replace('.AX','')][sec_col].values[0]
                    
                    # We still calculate MA200 just for the chart, but don't filter by it
                    ma200 = p.rolling(200).mean()
                    
                    final_results.append({
                        "Ticker": ticker,
                        "Sector": sector_label,
                        "Price": round(p.iloc[-1], 3),
                        "Mkt Cap": f"${int(mcap/1_000_000)}M",
                        "Log Gap": round(log_spread.iloc[-1], 4),
                        "Turnover": f"${int(turnover/1000)}k"
                    })
                    temp_found_data[ticker] = pd.DataFrame({
                        'Close': p, 'MA20': ma20, 'MA50': ma50, 'MA200': ma200, 'LogSpread': log_spread
                    })
        except: continue

    status_text.empty()
    st.session_state.scan_results = pd.DataFrame(final_results) if final_results else None
    st.session_state.found_data = temp_found_data

# --- UI ---
if st.button('🚀 Execute Unlimited Recovery Scan'):
    run_strategy()

if st.session_state.scan_results is not None:
    df_final = st.session_state.scan_results.sort_values("Log Gap")
    st.success(f"Found {len(df_final)} setups with 4 days of positive log-momentum!")
    st.dataframe(df_final, use_container_width=True)

    st.divider()
    selected_ticker = st.selectbox("Select Ticker", df_final['Ticker'].tolist())
    
    if selected_ticker and selected_ticker in st.session_state.found_data:
        df_plot = st.session_state.found_data[selected_ticker].tail(120)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['LogSpread'], name='Log Gap', 
                                 line=dict(color='lime', width=1.5), fill='tozeroy', 
                                 fillcolor='rgba(0, 255, 0, 0.1)'), secondary_y=True)

        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name='Price', line=dict(color='white', width=2)), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], name='MA20', line=dict(color='yellow', width=1.5)), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA50'], name='MA50', line=dict(color='royalblue', width=1.5)), secondary_y=False)
        
        # We keep the MA200 line on the chart so you can see where it is, even if we don't filter
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA200'], name='MA200', line=dict(color='#ff4b4b', width=2, dash='dot')), secondary_y=False)

        fig.update_layout(
            paper_bgcolor='black', plot_bgcolor='black', font=dict(color='white'),
            xaxis_rangeslider_visible=False, height=700,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="Price ($)", side="right", gridcolor='#333333'),
            yaxis2=dict(title="Log Gap", side="left", showgrid=False, zeroline=True, zerolinecolor='white'),
            xaxis=dict(gridcolor='#333333')
        )
        st.plotly_chart(fig, use_container_width=True)
