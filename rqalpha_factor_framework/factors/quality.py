import pandas as pd

from .base import build_factor_frame, latest_financial_numeric, nan_row


FACTOR_COLUMNS = ["roe", "roa", "gross_margin", "debt_to_asset"]


def calculate_quality_factors(financial_data):
    rows = []
    for order_book_id, tables in financial_data.items():
        profit = tables.get("profit", pd.DataFrame())
        balance = tables.get("balance", pd.DataFrame())
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["roe"] = latest_financial_numeric(profit, "roe")
        row["roa"] = latest_financial_numeric(profit, "roa")
        row["gross_margin"] = latest_financial_numeric(profit, "gross_margin")
        row["debt_to_asset"] = latest_financial_numeric(balance, "debt_to_asset")
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
