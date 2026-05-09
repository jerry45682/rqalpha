import numpy as np
import pandas as pd

from .base import build_factor_frame, latest_financial_numeric, nan_row, numeric_value


FACTOR_COLUMNS = [
    "roe",
    "roa",
    "gross_margin",
    "debt_to_asset",
    "asset_turnover",
    "inventory_turnover",
    "receivables_turnover",
]


def calculate_quality_factors(financial_data):
    rows = []
    for order_book_id, tables in financial_data.items():
        profit = tables.get("profit", pd.DataFrame())
        balance = tables.get("balance", pd.DataFrame())
        dupont = tables.get("dupont", pd.DataFrame())
        operation = tables.get("operation", pd.DataFrame())
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["roe"] = latest_financial_numeric(profit, "roe")
        row["roa"] = latest_financial_numeric(profit, "roa")
        if pd.isna(row["roa"]):
            row["roa"] = _dupont_roa(dupont)
        row["gross_margin"] = latest_financial_numeric(profit, "gross_margin")
        row["debt_to_asset"] = latest_financial_numeric(balance, "debt_to_asset")
        row["asset_turnover"] = latest_financial_numeric(operation, "asset_turnover")
        if pd.isna(row["asset_turnover"]):
            row["asset_turnover"] = latest_financial_numeric(dupont, "asset_turnover")
        row["inventory_turnover"] = latest_financial_numeric(
            operation, "inventory_turnover"
        )
        row["receivables_turnover"] = latest_financial_numeric(
            operation, "receivables_turnover"
        )
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)


def _dupont_roa(frame):
    roa = latest_financial_numeric(frame, "roa")
    if pd.notna(roa):
        return roa

    roe = latest_financial_numeric(frame, "dupontROE")
    asset_to_equity = latest_financial_numeric(frame, "dupontAssetStoEquity")
    if pd.isna(roe) or pd.isna(asset_to_equity) or asset_to_equity == 0:
        return np.nan
    return numeric_value(roe) / numeric_value(asset_to_equity)
