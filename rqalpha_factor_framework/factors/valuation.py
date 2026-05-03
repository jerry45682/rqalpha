import numpy as np

from .base import build_factor_frame, nan_row, sorted_frame


FACTOR_COLUMNS = ["pe_ttm", "pb", "ps_ttm"]


def calculate_valuation_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        data = sorted_frame(frame)
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        if not data.empty:
            latest = data.iloc[-1]
            row["pe_ttm"] = latest.get("peTTM", np.nan)
            row["pb"] = latest.get("pbMRQ", np.nan)
            row["ps_ttm"] = latest.get("psTTM", np.nan)
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
