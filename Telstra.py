import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- APP CONFIG ---
st.set_page_config(page_title="ASX Log-Momentum Tracker", layout="wide")
st.title("📈 ASX Tech & Industrials: 4-Day Momentum Tracker")
st.markdown("Monitoring the 4-day progression of **Log(MA20/MA50)** across Software, IT, and Capital Goods.")

# --- MEMORY ---
if 'all_data' not in st.session_state:
    st.session_state.all_data = None
if 'charts' not in st.session_state:
    st.session_state.charts = {}

def run_tracker():
    # 1. FETCH TICKERS
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        
        # Filtered List (Removed Materials)
        target_groups = [
            'Software & Services', 
            'Capital Goods', 
            'Technology Hardware & Equipment'
        ]
        
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    # 2. PROGRESSIVE DOWNLOADING & ANALYSIS
    results = []
    temp_charts = {}
    
    # Progress UI
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Process in chunks to keep the UI "moving" and visual
    chunk_size = 10
    total_tickers = len(tickers)
    
    for i in range(0, total_tickers, chunk_size):
        chunk = tickers[i:i + chunk_size]
        
        # Update Visuals
        percent_complete = min(i / total_tickers, 1.0)
        progress_bar.progress(percent_complete)
        status_text.info(f"🔍 Scanning {i}/{total_tickers}: Currently checking {', '.join(chunk[:3])}...")
        
        # Download Chunk
        data = yf.download(chunk, period="150d", interval="1d", group_by='column', progress=False)
        
        if data.empty:
            continue
            
        for ticker in chunk:
            try:
                if ticker not in data['Close']: continue
                
                p = data['Close'][ticker].dropna()
                if len(p) < 60: continue

                # Technical Calculations
                ma20 = p.rolling(20).mean()
                ma50 = p.rolling(50).mean()
                log_spread = np.log(ma20 / ma50)
                
                # Check 4-day positive progression
                diff = log_spread.diff()
                recent_diffs = diff.tail(4)
                
                # Progression is true if all last 4 changes are > 0
                has_progression = (recent_diffs > 0).all()
                
                results.append({
                    "Ticker": ticker,
                    "Price": round(p.iloc[-1], 3),
                    "Log Spread": round(log_spread.iloc[-1], 4),
                    "4D Progression": "✅ YES" if has_progression else "❌ No"
                })
                
                # Save data for the chart if user clicks later
                temp_charts[ticker] = pd.DataFrame({
                    'Close': p, 'MA20': ma20, 'MA50': ma50, 'LogSpread': log_spread
                }).tail(80)
                
            except:
                continue

    status_text.success("✅ Scan Complete!")
    progress_bar.progress(1.0)
    
    st.session_state.all_data = pd.DataFrame(results)
    st.session_state.charts = temp_charts

# --- EXECUTION ---
if st.button('🚀 Start Real-Time ASX Scan'):
    run_tracker()

# --- DISPLAY TABLE ---
if st.session_state.all_data is not None:
    st.subheader("ASX Tracker Results")
    
    # Sort so that the "YES" results are at the top
    display_df = st.session_state.all_data.sort_values("4D Progression", ascending=False)
    
    # Display full table
    st.dataframe(
        display_df, 
        use_container_width=True, 
        height=400,
        column_config={
            "4D Progression": st.column_config.TextColumn("4D Progression", help="Log(MA20/MA50) has risen 4 days in a row")
        }
    )

    # --- CHARTING ---
    st.divider()
    st.subheader("Visual Momentum Chart")
    selected_ticker = st.selectbox("Select a Ticker to view progression details:", display_df['Ticker'].tolist())
    
    if selected_ticker and selected_ticker in st.session_state.charts:
        df_plot = st.session_state.charts[selected_ticker]
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # The Momentum Line (Log Spread)
        fig.add_trace(go.Scatter(
            x=df_plot.index, y=df_plot['LogSpread'], 
            name="Log(MA20/MA50)", 
            line=dict(color='#00ff00', width=3),
            fill='tozeroy'
        ), secondary_y=True)

        # The Price & MAs
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name="Price", line=dict(color='white')), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], name="MA20", line=dict(color='yellow', dash='dot')), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA50'], name="MA50", line=dict(color='royalblue', dash='dot')), secondary_y=False)

        fig.update_layout(
            template="plotly_dark",
            height=600,
            xaxis_title="Date",
            yaxis_title="Price ($)",
            yaxis2_title="Momentum (Log Spread)",
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
