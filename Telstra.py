import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="ASX Alpha Dashboard", layout="wide")
st.title("🎯 ASX Alpha: Professional Visualization")

def run_strategy():
    # 1. FETCH & FILTER TICKERS
    url = "https://www.asx.com.au/asx/research/ASXListedCompanies.csv"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        df_asx = pd.read_csv(io.StringIO(res.text), skiprows=2)
        df_asx.columns = df_asx.columns.str.strip()
        
        target_groups = [
            'Software & Services', 'Technology Hardware & Equipment', 
            'Semiconductors & Semiconductor Equipment', 'Capital Goods',
            'Commercial & Professional Services'
        ]
        
        sec_col = [c for c in df_asx.columns if 'industry' in c.lower()][0]
        cod_col = [c for c in df_asx.columns if 'code' in c.lower()][0]
        
        filtered_df = df_asx[df_asx[sec_col].isin(target_groups)]
        tickers = [f"{c}.AX" for c in filtered_df[cod_col]]
    except Exception as e:
        st.error(f"ASX Load Error: {e}")
        return

    # 2. BATCH DOWNLOAD
    st.info(f"Scanning {len(tickers)} companies...")
    data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=False)
    
    close_prices = data['Close']
    volumes = data['Volume']
    final_results = []
    found_data = {}

    # 3. ANALYSIS LOOP
    for ticker in tickers:
        try:
            p = close_prices[ticker].dropna()
            v = volumes[ticker].dropna()
            if len(p) < 205: continue

            turnover = (p * v).tail(20).mean()
            if turnover < 50_000: continue

            ma20 = p.rolling(20).mean()
            ma50 = p.rolling(50).mean()
            ma200 = p.rolling(200).mean()
            
            # Spread Calculation (Left Axis)
            spread = (ma20 / ma50) - 1
            
            slope = (ma200.iloc[-1] - ma200.iloc[-6]) / ma200.iloc[-6]
            if slope < 0: continue

            pullback_val = spread.iloc[-1]
            # Curl Logic
            is_curling = spread.iloc[-1] > spread.iloc[-2]

            if pullback_val < -0.04 and is_curling:
                sector_label = filtered_df[filtered_df[cod_col] == ticker.replace('.AX','')][sec_col].values[0]
                
                final_results.append({
                    "Ticker": ticker,
                    "Sector": sector_label,
                    "Price": round(p.iloc[-1], 2),
                    "Pullback %": round(pullback_val * 100, 2),
                    "Daily Turnover": f"${round(turnover/1000)}k",
                    "Trend": "Rising" if slope > 0.001 else "Stable"
                })
                found_data[ticker] = pd.DataFrame({
                    'Close': p, 'MA20': ma20, 'MA50': ma50, 
                    'MA200': ma200, 'Spread': spread
                })
        except:
            continue

    # 4. RESULTS & ADVANCED CHARTING
    if final_results:
        df_final = pd.DataFrame(final_results).sort_values("Pullback %")
        st.success(f"Found {len(df_final)} setups!")
        st.dataframe(df_final, use_container_width=True)

        st.divider()
        st.subheader("📊 Dark Technical Analysis")
        selected_ticker = st.selectbox("Select Ticker", df_final['Ticker'].tolist())
        
        if selected_ticker:
            df_plot = found_data[selected_ticker].tail(120)
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])

            # --- SPREAD % (LEFT AXIS - LIME) ---
            fig.add_trace(go.Scatter(
                x=df_plot.index, y=df_plot['Spread'] * 100, 
                name='Spread % (Pullback)', 
                line=dict(color='lime', width=1.5),
                fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.05)'
            ), secondary_y=True)

            # --- PRICE & MAs (RIGHT AXIS) ---
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name='Price', line=dict(color='white', width=2.5)), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], name='MA20 (Yellow)', line=dict(color='yellow', width=1.5)), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA50'], name='MA50 (Blue)', line=dict(color='royalblue', width=1.5)), secondary_y=False)
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA200'], name='MA200 (Safety)', line=dict(color='#ff4b4b', width=2, dash='dot')), secondary_y=False)

            # --- DARK THEME OVERRIDES ---
            fig.update_layout(
                paper_bgcolor='black', # External background
                plot_bgcolor='black',  # Internal chart area
                font=dict(color='white'),
                title=f"{selected_ticker}: Price vs Squeeze",
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                height=700,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis=dict(
                    title="Price ($)", 
                    side="right", 
                    gridcolor='#333333', 
                    showgrid=True
                ),
                yaxis2=dict(
                    title="Spread %", 
                    side="left", 
                    showgrid=False, 
                    zeroline=True, 
                    zerolinecolor='white', 
                    zerolinewidth=1,
                    ticksuffix="%"
                ),
                xaxis=dict(gridcolor='#333333')
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No matches currently meet the criteria.")

if st.button('🚀 Run Master Scan'):
    run_strategy()
