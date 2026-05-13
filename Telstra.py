import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- APP CONFIG ---
st.set_page_config(page_title="ASX Momentum Tracker", layout="wide")
st.title("📈 ASX Tech & Industrials: 4-Day Momentum")

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
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    ticker_count = len(tickers)
    
    for i, ticker in enumerate(tickers):
        progress_bar.progress((i + 1) / ticker_count)
        status_text.info(f"🔍 Processing {i+1}/{ticker_count}: **{ticker}**")
        
        try:
            # Fetch data
            df = yf.download(ticker, period="1y", progress=False, interval="1d")
            
            if df.empty or len(df) < 55: continue
                
            p = df['Close'].dropna()

            # Technical Calculations
            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            log_spread = np.log(ma20 / ma50)
            
            # Check 4-day positive progression
            diff = log_spread.diff()
            recent_diffs = diff.tail(4)
            
            has_progression = (recent_diffs > 0).all()
            
            results.append({
                "Ticker": ticker,
                "Price": round(float(p.iloc[-1]), 3),
                "Log Spread": round(float(log_spread.iloc[-1]), 4),
                "4D Progression": "Yes" if has_progression else "No"
            })
            
            temp_charts[ticker] = pd.DataFrame({
                'Close': p, 'MA20': ma20, 'MA50': ma50, 'LogSpread': log_spread
            }).tail(80)
            
        except Exception:
            continue

    if results:
        status_text.success(f"✅ Scan Complete! Analyzed {len(results)} shares.")
        st.session_state.all_data = pd.DataFrame(results)
        st.session_state.charts = temp_charts
    else:
        status_text.warning("⚠️ No valid data retrieved.")
        st.session_state.all_data = None

# --- EXECUTION ---
if st.button('🚀 Start Real-Time ASX Scan'):
    run_tracker()

# --- DISPLAY TABLE ---
if st.session_state.all_data is not None and not st.session_state.all_data.empty:
    st.divider()
    
    filter_choice = st.radio("Filter by Progression:", ["All", "Yes Only", "No Only"], horizontal=True)
    
    df_to_show = st.session_state.all_data.copy()
    if filter_choice == "Yes Only":
        df_to_show = df_to_show[df_to_show["4D Progression"] == "Yes"]
    elif filter_choice == "No Only":
        df_to_show = df_to_show[df_to_show["4D Progression"] == "No"]

    st.subheader(f"Results ({len(df_to_show)} shares)")
    
    # Simple table display without Market Cap
    st.dataframe(
        df_to_show[["Ticker", "Price", "Log Spread", "4D Progression"]], 
        use_container_width=True, 
        height=500
    )

    # --- CHARTING ---
    st.divider()
    st.subheader("Visual Momentum Chart")
    ticker_list = df_to_show['Ticker'].tolist()
    if ticker_list:
        selected_ticker = st.selectbox("Select a Ticker for detail:", ticker_list)
        
        if selected_ticker and selected_ticker in st.session_state.charts:
            df_plot = st.session_state.charts[selected_ticker]
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Momentum Line
            fig.add_trace(go.Scatter(
                x=df_plot.index, y=df_plot['LogSpread'], name="Log(MA20/MA50)", 
                line=dict(color='#00ff00', width=3), fill='tozeroy'
            ), secondary_y=True)

            # Price and MAs
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name="Price", line=dict(color='white')), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], name="MA20", line=dict(color='#FFFF00', dash='dot')), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA50'], name="MA50", line=dict(color='#4169E1', dash='dot')), secondary_y=False)

            # DARK MODE STYLING
            fig.update_layout(
                paper_bgcolor='black',
                plot_bgcolor='black',
                font=dict(color='white'),
                height=600,
                hovermode="x unified",
                legend=dict(font=dict(color='white')),
                xaxis=dict(
                    showgrid=True, gridcolor='#333333', 
                    tickfont=dict(color='white'), titlefont=dict(color='white')
                ),
                yaxis=dict(
                    showgrid=True, gridcolor='#333333', 
                    tickfont=dict(color='white'), titlefont=dict(color='white'),
                    title="Price ($)"
                ),
                yaxis2=dict(
                    showgrid=False, 
                    tickfont=dict(color='white'), titlefont=dict(color='white'),
                    title="Log Momentum"
                )
            )
            st.plotly_chart(fig, use_container_width=True)
