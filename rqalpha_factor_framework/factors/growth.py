import pandas as pd

from .base import build_factor_frame, latest_financial_numeric, nan_row


FACTOR_COLUMNS = [
    "revenue_growth_yoy",
    "net_profit_growth_yoy",
    "operating_cashflow_growth_yoy",
]


def calculate_growth_factors(financial_data):
    rows = []
    for order_book_id, tables in financial_data.items():
        growth = tables.get("growth", pd.DataFrame())
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        row["revenue_growth_yoy"] = latest_financial_numeric(
            growth, "revenue_growth_yoy"
        )
        row["net_profit_growth_yoy"] = latest_financial_numeric(
            growth, "net_profit_growth_yoy"
        )
        row["operating_cashflow_growth_yoy"] = latest_financial_numeric(
            growth, "operating_cashflow_growth_yoy"
        )
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
