import pandas as pd
import yfinance as yf
import streamlit as st
import requests
import io
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- INITIALIZE MEMORY ---
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None
if 'found_data' not in st.session_state:
    st.session_state.found_data = {}

def run_strategy():
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

    st.info(f"Scanning {len(tickers)} companies...")
    data = yf.download(tickers, period="260d", interval="1d", group_by='column', progress=False)
    
    close_prices = data['Close']
    volumes = data['Volume']
    
    final_results = []
    temp_found_data = {}

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
            spread = (ma20 / ma50) - 1
            
            slope = (ma200.iloc[-1] - ma200.iloc[-6]) / ma200.iloc[-6]
            if slope < 0: continue

            if spread.iloc[-1] < -0.04 and spread.iloc[-1] > spread.iloc[-2]:
                sector_label = filtered_df[filtered_df[cod_col] == ticker.replace('.AX','')][sec_col].values[0]
                final_results.append({
                    "Ticker": ticker, "Sector": sector_label, "Price": round(p.iloc[-1], 2),
                    "Pullback %": round(spread.iloc[-1] * 100, 2), "Daily Turnover": f"${round(turnover/1000)}k",
                    "Trend": "Rising" if slope > 0.001 else "Stable"
                })
                temp_found_data[ticker] = pd.DataFrame({'Close': p, 'MA20': ma20, 'MA50': ma50, 'MA200': ma200, 'Spread': spread})
        except: continue

    # SAVE TO SESSION STATE
    st.session_state.scan_results = pd.DataFrame(final_results) if final_results else None
    st.session_state.found_data = temp_found_data

# --- APP LAYOUT ---
if st.button('🚀 Execute Master Scan'):
    run_strategy()

# --- DISPLAY LOGIC (Always check if we have results in memory) ---
if st.session_state.scan_results is not None:
    df_final = st.session_state.scan_results.sort_values("Pullback %")
    st.success(f"Found {len(df_final)} setups!")
    st.dataframe(df_final, use_container_width=True)

    st.divider()
    st.subheader("📊 Dark Technical Analysis")
    selected_ticker = st.selectbox("Select Ticker to Chart", df_final['Ticker'].tolist())
    
    if selected_ticker and selected_ticker in st.session_state.found_data:
        df_plot = st.session_state.found_data[selected_ticker].tail(120)
        
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # SPREAD % (LEFT)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Spread'] * 100, name='Spread %', 
                                 line=dict(color='lime', width=1.5), fill='tozeroy', fillcolor='rgba(0, 255, 0, 0.05)'), secondary_y=True)
        
        # PRICE & MAs (RIGHT)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'], name='Price', line=dict(color='white', width=2.5)), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], name='MA20', line=dict(color='yellow', width=1.5)), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA50'], name='MA50', line=dict(color='royalblue', width=1.5)), secondary_y=False)
        fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA200'], name='MA200', line=dict(color='#ff4b4b', width=2, dash='dot')), secondary_y=False)

        fig.update_layout(
            paper_bgcolor='black', plot_bgcolor='black', font=dict(color='white'),
            xaxis_rangeslider_visible=False, height=700,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="white")),
            yaxis=dict(title="Price ($)", side="right", gridcolor='#333333', tickfont=dict(color="white")),
            yaxis2=dict(title="Spread %", side="left", showgrid=False, zeroline=True, zerolinecolor='white', ticksuffix="%", tickfont=dict(color="white")),
            xaxis=dict(gridcolor='#333333', tickfont=dict(color="white"))
        )
        st.plotly_chart(fig, use_container_width=True)
