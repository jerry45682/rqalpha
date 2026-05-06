import numpy as np

from .base import build_factor_frame, nan_row, numeric_series, sorted_frame


FACTOR_COLUMNS = ["return_20", "return_60", "return_120", "price_ma60_strength"]


def _period_return(close, window):
    if len(close) < window + 1:
        return np.nan
    base = close.iloc[-window - 1]
    if base == 0:
        return np.nan
    return close.iloc[-1] / base - 1.0


def calculate_momentum_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        data = sorted_frame(frame)
        close = numeric_series(data, "close")
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["return_20"] = _period_return(close, 20)
        row["return_60"] = _period_return(close, 60)
        row["return_120"] = _period_return(close, 120)
        if len(close) >= 60:
            ma60 = close.tail(60).mean()
            if ma60 != 0:
                row["price_ma60_strength"] = close.iloc[-1] / ma60 - 1.0
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
