import streamlit as st
from data_fetch import get_option_chain, get_price_data, get_sensex_spot
from analysis import calculate_pcr, calculate_max_pain, get_oi_walls, calculate_bollinger_bands, generate_setup_summary, backtest_bollinger_multi_lookahead, backtest_baseline_drift
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(page_title="Sensex Expiry Dashboard", layout="wide")
st.title("📊 Sensex Expiry Day Dashboard")

@st.cache_data(ttl=60)
def load_data():
    chain = get_option_chain()
    price_df = get_price_data()
    spot = get_sensex_spot()
    return chain, price_df, spot

try:
    with st.spinner("Fetching live data..."):
        chain_df, price_df, spot_price = load_data()

    pcr = calculate_pcr(chain_df)
    max_pain, _ = calculate_max_pain(chain_df)
    oi_walls = get_oi_walls(chain_df)
    price_df = calculate_bollinger_bands(price_df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Spot Price", f"{spot_price:,.2f}")
    col2.metric("Max Pain", f"{max_pain:,.0f}")
    col3.metric("PCR", round(pcr, 2))
    col4.metric("Top OI Wall", f"{oi_walls[0]:,.0f}")

    st.subheader("Setup Summary")
    summary_lines = generate_setup_summary(spot_price, max_pain, pcr, oi_walls, price_df)
    for line in summary_lines:
        st.write(f"• {line}")
    st.caption("This is a descriptive summary of the data above — not a trade recommendation.")

    st.subheader("Price Action with Bollinger Bands")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=price_df["date"], open=price_df["open"], high=price_df["high"],
        low=price_df["low"], close=price_df["close"], name="Sensex"
    ))
    fig.add_trace(go.Scatter(x=price_df["date"], y=price_df["upper_band"],
                              line=dict(color="rgba(250,0,0,0.4)"), name="Upper Band"))
    fig.add_trace(go.Scatter(x=price_df["date"], y=price_df["lower_band"],
                              line=dict(color="rgba(0,0,250,0.4)"), name="Lower Band",
                              fill="tonexty", fillcolor="rgba(200,200,200,0.1)"))
    fig.add_trace(go.Scatter(x=price_df["date"], y=price_df["sma"],
                              line=dict(color="orange", width=1), name="SMA 20"))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Option Chain (near ATM)")
    atm_range = chain_df[
        (chain_df["strike"] > spot_price - 1000) &
        (chain_df["strike"] < spot_price + 1000)
    ]
    st.dataframe(atm_range, use_container_width=True)

    st.subheader("Backtest: Bollinger Band Touches (Multiple Windows)")
    multi_bt = backtest_bollinger_multi_lookahead(price_df)
    rows = []
    for window, res in multi_bt.items():
        rows.append({
            "Window": window,
            "Upper Touch Count": res["upper_touch"]["count"],
            "Upper Avg %": round(res["upper_touch"]["avg_pct_change"], 3),
            "Upper % Up": round(res["upper_touch"]["pct_positive"], 0),
            "Lower Touch Count": res["lower_touch"]["count"],
            "Lower Avg %": round(res["lower_touch"]["avg_pct_change"], 3),
            "Lower % Up": round(res["lower_touch"]["pct_positive"], 0),
        })
    bt_df = pd.DataFrame(rows)
    st.dataframe(bt_df, use_container_width=True)

    st.subheader("Baseline: Average Drift (All Periods, No Condition)")
    baseline = backtest_baseline_drift(price_df)
    baseline_rows = []
    for window, res in baseline.items():
        baseline_rows.append({
            "Window": window,
            "Baseline Avg %": round(res["avg_pct_change"], 3),
            "Baseline % Up": round(res["pct_positive"], 0),
        })
    baseline_df = pd.DataFrame(baseline_rows)
    st.dataframe(baseline_df, use_container_width=True)
    st.caption("Compare this to the touch-specific table above — if the numbers are similar, the band-touch pattern is likely just general market drift, not a distinct signal.")

    st.caption("⚠️ Data and analysis only — not investment advice. Consult a SEBI-registered advisor before trading.")

except Exception as e:
    st.error(f"Error loading data: {e}")
    st.info("Check that your Kite API credentials are correctly set in Streamlit secrets, and that today's access token hasn't expired.")
