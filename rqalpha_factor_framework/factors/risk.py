import numpy as np

from .base import build_factor_frame, nan_row, numeric_series, sorted_frame


FACTOR_COLUMNS = ["volatility_60", "max_drawdown_120"]


def _max_drawdown(close, window):
    if len(close) < 2:
        return np.nan
    values = close.tail(window)
    running_max = values.cummax()
    drawdown = values / running_max - 1.0
    return drawdown.min()


def calculate_risk_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        data = sorted_frame(frame)
        close = numeric_series(data, "close")
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        returns = close.pct_change().dropna()
        if len(returns) >= 60:
            row["volatility_60"] = returns.tail(60).std()
        row["max_drawdown_120"] = _max_drawdown(close, 120)
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
