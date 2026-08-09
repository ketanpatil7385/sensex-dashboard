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


def calculate_atr(price_df, period=14):
    df = price_df.copy()
    df["prev_close"] = df["close"].shift(1)
    df["tr"] = df.apply(lambda row: max(
        row["high"] - row["low"],
        abs(row["high"] - row["prev_close"]) if pd.notna(row["prev_close"]) else 0,
        abs(row["low"] - row["prev_close"]) if pd.notna(row["prev_close"]) else 0,
    ), axis=1)
    df["atr"] = df["tr"].rolling(window=period).mean()
    return df["atr"].iloc[-1] if len(df.dropna()) > 0 else None


def get_volatility_context(price_df):
    df = price_df.dropna(subset=["close", "high", "low"]).copy()
    if len(df) < 20:
        return {"atr": None, "today_range": None, "avg_range": None, "band_width": None}

    atr = calculate_atr(df)

    df["date_only"] = pd.to_datetime(df["date"]).dt.date
    today = df["date_only"].max()
    today_df = df[df["date_only"] == today]
    today_range = today_df["high"].max() - today_df["low"].min() if len(today_df) > 0 else None

    daily_ranges = df.groupby("date_only").apply(lambda g: g["high"].max() - g["low"].min())
    avg_range = daily_ranges.mean() if len(daily_ranges) > 0 else None

    band_width = None
    if "upper_band" in df.columns and "lower_band" in df.columns:
        last = df.iloc[-1]
        if pd.notna(last.get("upper_band")) and pd.notna(last.get("lower_band")):
            band_width = last["upper_band"] - last["lower_band"]

    return {
        "atr": atr,
        "today_range": today_range,
        "avg_range": avg_range,
        "band_width": band_width,
    }
