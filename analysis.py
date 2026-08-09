import pandas as pd


def calculate_pcr(option_chain):
    total_call_oi = option_chain['call_oi'].sum()
    total_put_oi = option_chain['put_oi'].sum()
    return total_put_oi / total_call_oi if total_call_oi > 0 else 0


def calculate_max_pain(option_chain):
    strikes = option_chain['strike'].unique()
    pain = {}

    for settle_price in strikes:
        total_loss = 0
        for _, row in option_chain.iterrows():
            strike = row['strike']
            if settle_price > strike:
                total_loss += (settle_price - strike) * row['call_oi']
            if settle_price < strike:
                total_loss += (strike - settle_price) * row['put_oi']
        pain[settle_price] = total_loss

    max_pain_strike = min(pain, key=pain.get)
    return max_pain_strike, pain


def get_oi_walls(option_chain, top_n=3):
    df = option_chain.copy()
    df['total_oi'] = df['call_oi'] + df['put_oi']
    walls = df.nlargest(top_n, 'total_oi')['strike'].tolist()
    return walls


def calculate_bollinger_bands(price_df, window=20, num_std=2):
    df = price_df.copy()
    df["sma"] = df["close"].rolling(window=window).mean()
    df["std"] = df["close"].rolling(window=window).std()
    df["upper_band"] = df["sma"] + (num_std * df["std"])
    df["lower_band"] = df["sma"] - (num_std * df["std"])
    return df


def generate_setup_summary(spot_price, max_pain, pcr, oi_walls, price_df):
    lines = []

    diff = spot_price - max_pain
    if abs(diff) < 100:
        lines.append(f"Spot ({spot_price:,.0f}) is sitting very close to max pain ({max_pain:,.0f}).")
    elif diff > 0:
        lines.append(f"Spot ({spot_price:,.0f}) is {diff:,.0f} points above max pain ({max_pain:,.0f}).")
    else:
        lines.append(f"Spot ({spot_price:,.0f}) is {abs(diff):,.0f} points below max pain ({max_pain:,.0f}).")

    if pcr > 1.2:
        lines.append(f"PCR is {pcr:.2f} — put OI significantly exceeds call OI.")
    elif pcr < 0.8:
        lines.append(f"PCR is {pcr:.2f} — call OI significantly exceeds put OI.")
    else:
        lines.append(f"PCR is {pcr:.2f} — fairly balanced positioning between calls and puts.")

    resistance = [w for w in oi_walls if w > spot_price]
    support = [w for w in oi_walls if w < spot_price]
    if resistance:
        lines.append(f"Nearest heavy OI above spot (possible resistance): {min(resistance):,.0f}")
    if support:
        lines.append(f"Nearest heavy OI below spot (possible support): {max(support):,.0f}")

    if "upper_band" in price_df.columns and len(price_df.dropna()) > 0:
        last = price_df.dropna().iloc[-1]
        if last["close"] >= last["upper_band"]:
            lines.append("Price is at or above the upper Bollinger Band — potentially overextended on the upside.")
        elif last["close"] <= last["lower_band"]:
            lines.append("Price is at or below the lower Bollinger Band — potentially overextended on the downside.")
        else:
            lines.append("Price is trading within the Bollinger Bands — no extreme currently.")

    return lines


def backtest_bollinger_multi_lookahead(price_df, lookaheads=[3, 6, 12, 24]):
    df = price_df.dropna().reset_index(drop=True)
    all_results = {}
    for lookahead in lookaheads:
        results = {"upper_touch": [], "lower_touch": []}
        for i in range(len(df) - lookahead):
            row = df.iloc[i]
            future_price = df.iloc[i + lookahead]["close"]
            pct_change = (future_price - row["close"]) / row["close"] * 100
            if row["close"] >= row["upper_band"]:
                results["upper_touch"].append(pct_change)
            elif row["close"] <= row["lower_band"]:
                results["lower_touch"].append(pct_change)
        summary = {}
        for key, changes in results.items():
            if changes:
                summary[key] = {"count": len(changes), "avg_pct_change": sum(changes) / len(changes), "pct_positive": sum(1 for c in changes if c > 0) / len(changes) * 100}
            else:
                summary[key] = {"count": 0, "avg_pct_change": 0, "pct_positive": 0}
        minutes = lookahead * 5
        all_results[f"{minutes} min"] = summary
    return all_results


def backtest_baseline_drift(price_df, lookaheads=[3, 6, 12, 24]):
    df = price_df.dropna().reset_index(drop=True)
    baseline = {}
    for lookahead in lookaheads:
        changes = []
        for i in range(len(df) - lookahead):
            row = df.iloc[i]
            future_price = df.iloc[i + lookahead]["close"]
            pct_change = (future_price - row["close"]) / row["close"] * 100
            changes.append(pct_change)
        minutes = lookahead * 5
        if changes:
            baseline[f"{minutes} min"] = {
                "avg_pct_change": sum(changes) / len(changes),
                "pct_positive": sum(1 for c in changes if c > 0) / len(changes) * 100,
            }
        else:
            baseline[f"{minutes} min"] = {"avg_pct_change": 0, "pct_positive": 0}
    return baseline
    
def classify_trend(price_df, short_window=9, long_window=21):
    df = price_df.copy()
    df["sma_short"] = df["close"].rolling(window=short_window).mean()
    df["sma_long"] = df["close"].rolling(window=long_window).mean()
    df = df.dropna()

    if len(df) < 5:
        return {"trend": "Insufficient data", "strength": "N/A"}

    last = df.iloc[-1]
    prev = df.iloc[-5]

    price_above_short = last["close"] > last["sma_short"]
    price_above_long = last["close"] > last["sma_long"]
    short_above_long = last["sma_short"] > last["sma_long"]
    sma_short_rising = last["sma_short"] > prev["sma_short"]

    recent = df.tail(20)
    higher_highs = recent["high"].iloc[-10:].max() > recent["high"].iloc[:10].max()
    higher_lows = recent["low"].iloc[-10:].min() > recent["low"].iloc[:10].min()

    bullish_signals = sum([price_above_short, price_above_long, short_above_long, sma_short_rising, higher_highs, higher_lows])

    if bullish_signals >= 5:
        trend = "Strong Uptrend"
    elif bullish_signals >= 4:
        trend = "Mild Uptrend"
    elif bullish_signals <= 1:
        trend = "Strong Downtrend"
    elif bullish_signals <= 2:
        trend = "Mild Downtrend"
    else:
        trend = "Sideways / No Clear Trend"

    return {
        "trend": trend,
        "bullish_signals": f"{bullish_signals}/6",
        "price_vs_short_sma": "Above" if price_above_short else "Below",
        "price_vs_long_sma": "Above" if price_above_long else "Below",
        "higher_highs": higher_highs,
        "higher_lows": higher_lows,
    }
