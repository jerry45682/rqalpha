import pandas as pd


def _positive_column(frame, column):
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce") > 0


def filter_stocks(
    frame,
    min_listed_days=180,
    require_positive_pe_pb=True,
    exclude_st=True,
):
    result = frame.copy()
    if result.empty:
        return result

    if exclude_st and "is_st" in result.columns:
        is_st = pd.to_numeric(result["is_st"], errors="coerce").fillna(0).astype(int)
        result = result[is_st == 0]

    if "listed_days" in result.columns:
        listed_days = pd.to_numeric(result["listed_days"], errors="coerce").fillna(0)
        result = result[listed_days >= int(min_listed_days)]

    if require_positive_pe_pb:
        pe = _positive_column(result, "pe_ttm")
        pb = _positive_column(result, "pb")
        result = result[(pe > 0) & (pb > 0)]

    return result
