from .base import build_factor_frame, nan_row, numeric_series, sorted_frame


FACTOR_COLUMNS = ["avg_amount_20", "avg_turnover_20"]


def calculate_liquidity_factors(daily_data):
    rows = []
    for order_book_id, frame in daily_data.items():
        data = sorted_frame(frame)
        amount = numeric_series(data, "amount")
        turnover = numeric_series(data, "turn")
        row = nan_row(order_book_id, FACTOR_COLUMNS)
        if len(amount) >= 20:
            row["avg_amount_20"] = amount.tail(20).mean()
        if len(turnover) >= 20:
            row["avg_turnover_20"] = turnover.tail(20).mean()
        rows.append(row)
    return build_factor_frame(rows, FACTOR_COLUMNS)
