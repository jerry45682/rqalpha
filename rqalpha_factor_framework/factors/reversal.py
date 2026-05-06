import numpy as np

from .base import build_factor_frame, nan_row, numeric_series, sorted_frame
from .momentum import _period_return


FACTOR_COLUMNS = ["return_5", "rsi"]


def _rsi(close, window=14):
    if len(close) < window + 1:
        return np.nan
    delta = close.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.tail(window).mean()
    avg_loss = losses.tail(window).mean()
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else np.nan
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calculate_reversal_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        data = sorted_frame(frame)
        close = numeric_series(data, "close")
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["return_5"] = _period_return(close, 5)
        row["rsi"] = _rsi(close)
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
