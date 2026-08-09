import streamlit as st
from data_fetch import get_option_chain, get_price_data, get_sensex_spot
from analysis import calculate_pcr, calculate_max_pain, get_oi_walls, calculate_bollinger_bands, generate_setup_summary, classify_trend, get_volatility_context, historical_next_day_distribution, get_momentum_reading
import pandas as pd
import datetime

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

    st.subheader("Option Chain (near ATM)")
    atm_range = chain_df[
        (chain_df["strike"] > spot_price - 1000) &
        (chain_df["strike"] < spot_price + 1000)
    ]
    st.dataframe(atm_range, use_container_width=True)

    st.subheader("Intraday Trend (as of now)")
    trend_info = classify_trend(price_df)
    st.metric("Current Classification", trend_info["trend"])
    st.write(f"Bullish signals: {trend_info.get('bullish_signals', 'N/A')}")
    st.write(f"Price vs short-term average: {trend_info.get('price_vs_short_sma', 'N/A')}")
    st.write(f"Price vs long-term average: {trend_info.get('price_vs_long_sma', 'N/A')}")
    st.caption("This describes the current price structure — it is not a prediction of future direction.")

    st.subheader("Momentum Indicators")
    momentum = get_momentum_reading(price_df)
    mcol1, mcol2 = st.columns(2)
    mcol1.metric("RSI (14)", momentum.get("rsi", "N/A"), momentum.get("rsi_read", ""))
    mcol2.metric("MACD Signal", momentum.get("macd_read", "N/A"))
    st.caption("RSI and MACD describe current momentum — not a prediction of future direction.")

    st.subheader("Trend History (This Session)")
    if "trend_log" not in st.session_state:
        st.session_state.trend_log = []
    current_time = datetime.datetime.now().strftime("%H:%M")
    if not st.session_state.trend_log or st.session_state.trend_log[-1]["time"] != current_time:
        st.session_state.trend_log.append({
            "time": current_time,
            "spot": round(spot_price, 0),
            "trend": trend_info["trend"],
            "rsi": momentum.get("rsi", "N/A"),
        })
    trend_log_df = pd.DataFrame(st.session_state.trend_log)
    st.dataframe(trend_log_df, use_container_width=True)
    st.caption("Builds up as you keep this tab open through the day. Resets if the tab is closed or the app restarts.")

    st.subheader("Volatility Context")
    vol = get_volatility_context(price_df)
    vcol1, vcol2, vcol3 = st.columns(3)
    vcol1.metric("ATR (14-period)", f"{vol['atr']:,.1f}" if vol['atr'] else "N/A")
    vcol2.metric("Today's Range So Far", f"{vol['today_range']:,.1f}" if vol['today_range'] else "N/A")
    vcol3.metric("Avg Daily Range (recent)", f"{vol['avg_range']:,.1f}" if vol['avg_range'] else "N/A")
    if vol['today_range'] and vol['avg_range']:
        pct_of_avg = (vol['today_range'] / vol['avg_range']) * 100
        st.write(f"Today's range is **{pct_of_avg:.0f}%** of the recent average daily range.")
    st.write(f"Current Bollinger Band width: {vol['band_width']:,.1f}" if vol['band_width'] else "Band width: N/A")
    st.caption("These are historical/current measures of how much the index has typically moved — not a forecast of today's remaining movement.")

    st.subheader("Historical Next-Day Move Distribution")
    hist_dist = historical_next_day_distribution(price_df)
    hist_rows = []
    for bucket, stats in hist_dist.items():
        hist_rows.append({
            "Yesterday's Setup": bucket,
            "Days Observed": stats["days_observed"],
            "Avg Next-Day %": round(stats["avg_next_day_pct"], 2),
            "% Days Up": round(stats["pct_days_up"], 0),
            "Min %": round(stats["min_pct"], 2),
            "Max %": round(stats["max_pct"], 2),
        })
    hist_df = pd.DataFrame(hist_rows)
    st.dataframe(hist_df, use_container_width=True)
    st.caption("This shows how price has historically moved the day after similar setups — it is a distribution of past outcomes, not a prediction for tomorrow. Small sample sizes can be misleading.")

    st.caption("⚠️ Data and analysis only — not investment advice. Consult a SEBI-registered advisor before trading.")

except Exception as e:
    st.error(f"Error loading data: {e}")
    st.info("Check that your Kite API credentials are correctly set in Streamlit secrets, and that today's access token hasn't expired.")
