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
