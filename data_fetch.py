from kiteconnect import KiteConnect
import pandas as pd
from datetime import datetime, timedelta
import os

API_KEY = os.environ.get("KITE_API_KEY")
ACCESS_TOKEN = os.environ.get("KITE_ACCESS_TOKEN")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)

SENSEX_TOKEN = 265


def get_sensex_spot():
    data = kite.quote(["BSE:SENSEX"])
    return data["BSE:SENSEX"]["last_price"]


def get_bse_instruments():
    instruments = kite.instruments("BFO")
    df = pd.DataFrame(instruments)
    sensex_opts = df[
        (df["name"] == "SENSEX") &
        (df["instrument_type"].isin(["CE", "PE"]))
    ]
    return sensex_opts


def get_nearest_expiry(instruments_df):
    instruments_df = instruments_df.copy()
    instruments_df["expiry"] = pd.to_datetime(instruments_df["expiry"])
    today = pd.Timestamp(datetime.now().date())
    future_expiries = instruments_df[instruments_df["expiry"] >= today]
    return future_expiries["expiry"].min()


def build_option_chain(instruments_df, expiry):
    instruments_df = instruments_df.copy()
    instruments_df["expiry"] = pd.to_datetime(instruments_df["expiry"])
    chain_df = instruments_df[instruments_df["expiry"] == expiry].copy()

    symbols = ["BFO:" + s for s in chain_df["tradingsymbol"]]
    all_quotes = {}
    for i in range(0, len(symbols), 250):
        batch = symbols[i:i + 250]
        quotes = kite.quote(batch)
        all_quotes.update(quotes)

    chain_df["oi"] = chain_df["tradingsymbol"].apply(
        lambda x: all_quotes.get(f"BFO:{x}", {}).get("oi", 0)
    )
    chain_df["ltp"] = chain_df["tradingsymbol"].apply(
        lambda x: all_quotes.get(f"BFO:{x}", {}).get("last_price", 0)
    )
    chain_df["volume"] = chain_df["tradingsymbol"].apply(
        lambda x: all_quotes.get(f"BFO:{x}", {}).get("volume", 0)
    )
    return chain_df


def get_option_chain():
    instruments = get_bse_instruments()
    expiry = get_nearest_expiry(instruments)
    chain = build_option_chain(instruments, expiry)

    ce = chain[chain["instrument_type"] == "CE"][["strike", "oi", "ltp", "volume"]]
    pe = chain[chain["instrument_type"] == "PE"][["strike", "oi", "ltp", "volume"]]

    merged = ce.merge(pe, on="strike", suffixes=("_call", "_put"))
    merged = merged.rename(columns={
        "oi_call": "call_oi", "oi_put": "put_oi",
        "ltp_call": "call_ltp", "ltp_put": "put_ltp"
    })
    return merged.sort_values("strike").reset_index(drop=True)


def get_price_data(interval="5minute", days=5):
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)
    data = kite.historical_data(SENSEX_TOKEN, from_date, to_date, interval)
    return pd.DataFrame(data)
