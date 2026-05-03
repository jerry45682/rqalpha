import numpy as np
import pandas as pd

from .base import build_factor_frame, nan_row, sorted_frame


FACTOR_COLUMNS = [
    "revenue_growth_yoy",
    "net_profit_growth_yoy",
    "operating_cashflow_growth_yoy",
]


def _numeric_value(value):
    return pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]


def _latest_numeric(frame, column):
    data = sorted_frame(frame)
    if data.empty or column not in data.columns:
        return np.nan
    return _numeric_value(data.iloc[-1].get(column, np.nan))


def calculate_growth_factors(financial_data):
    rows = []
    for order_book_id, tables in financial_data.items():
        growth = tables.get("growth", pd.DataFrame())
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["revenue_growth_yoy"] = _latest_numeric(growth, "revenue_growth_yoy")
        row["net_profit_growth_yoy"] = _latest_numeric(growth, "net_profit_growth_yoy")
        row["operating_cashflow_growth_yoy"] = _latest_numeric(
            growth, "operating_cashflow_growth_yoy"
        )
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
