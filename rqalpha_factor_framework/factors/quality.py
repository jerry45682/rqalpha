import numpy as np
import pandas as pd

from .base import build_factor_frame, nan_row, sorted_frame


FACTOR_COLUMNS = ["roe", "roa", "gross_margin", "debt_to_asset"]


def _numeric_value(value):
    return pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]


def _latest_numeric(frame, column):
    data = sorted_frame(frame)
    if data.empty or column not in data.columns:
        return np.nan
    return _numeric_value(data.iloc[-1].get(column, np.nan))


def calculate_quality_factors(financial_data):
    rows = []
    for order_book_id, tables in financial_data.items():
        profit = tables.get("profit", pd.DataFrame())
        balance = tables.get("balance", pd.DataFrame())
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["roe"] = _latest_numeric(profit, "roe")
        row["roa"] = _latest_numeric(profit, "roa")
        row["gross_margin"] = _latest_numeric(profit, "gross_margin")
        row["debt_to_asset"] = _latest_numeric(balance, "debt_to_asset")
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
