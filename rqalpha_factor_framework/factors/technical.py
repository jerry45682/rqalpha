import numpy as np

from .base import build_factor_frame, nan_row, numeric_series, sorted_frame


FACTOR_COLUMNS = ["macd_hist", "obv_trend"]


def _macd_hist(close):
    if len(close) < 26:
        return np.nan
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return (macd - signal).iloc[-1]


def _obv_trend(close, volume, window=20):
    if len(close) < window + 1 or len(volume) < window + 1:
        return np.nan
    aligned = close.to_frame("close").join(volume.to_frame("volume"), how="inner")
    if len(aligned) < window + 1:
        return np.nan
    direction = np.sign(aligned["close"].diff()).fillna(0)
    obv = (direction * aligned["volume"]).cumsum()
    return obv.iloc[-1] - obv.iloc[-window - 1]


def calculate_technical_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        data = sorted_frame(frame)
        close = numeric_series(data, "close")
        volume = numeric_series(data, "volume")
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["macd_hist"] = _macd_hist(close)
        row["obv_trend"] = _obv_trend(close, volume)
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
