import numpy as np
import pandas as pd

from .base import build_factor_frame, nan_row, sorted_frame


FACTOR_COLUMNS = ["pe_ttm", "pb", "ps_ttm", "pcf_ncf_ttm"]


def _numeric_value(value):
    return pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]


def calculate_valuation_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        data = sorted_frame(frame)
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        if not data.empty:
            latest = data.iloc[-1]
            row["pe_ttm"] = _numeric_value(latest.get("peTTM", np.nan))
            row["pb"] = _numeric_value(latest.get("pbMRQ", np.nan))
            row["ps_ttm"] = _numeric_value(latest.get("psTTM", np.nan))
            row["pcf_ncf_ttm"] = _numeric_value(latest.get("pcfNcfTTM", np.nan))
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
