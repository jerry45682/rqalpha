import pandas as pd


def filter_by_avg_amount(frame, min_avg_amount):
    if frame.empty:
        return frame.copy()
    if "avg_amount_20" not in frame.columns:
        return frame.iloc[0:0].copy()
    amount = pd.to_numeric(frame["avg_amount_20"], errors="coerce").fillna(0.0)
    return frame[amount >= float(min_avg_amount)]
