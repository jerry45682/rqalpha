from contextlib import contextmanager

import pandas as pd


DAILY_FIELDS = [
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turn",
    "tradestatus",
    "peTTM",
    "pbMRQ",
    "psTTM",
    "isST",
]


PROFIT_FIELD_ALIASES = {
    "roeAvg": "roe",
    "ROA": "roa",
    "roa": "roa",
    "gpMargin": "gross_margin",
}

BALANCE_FIELD_ALIASES = {
    "liabilityToAsset": "debt_to_asset",
    "assetLiabRatio": "debt_to_asset",
}

GROWTH_FIELD_ALIASES = {
    "YOYRevenue": "revenue_growth_yoy",
    "YOYOperatingRevenue": "revenue_growth_yoy",
    "operating_revenue_yoy": "revenue_growth_yoy",
    "YOYNI": "net_profit_growth_yoy",
    "YOYPNI": "net_profit_growth_yoy",
    "net_profit_yoy": "net_profit_growth_yoy",
}


def rqalpha_to_baostock(order_book_id):
    code, exchange = order_book_id.split(".")
    if exchange == "XSHG":
        return f"sh.{code}"
    if exchange == "XSHE":
        return f"sz.{code}"
    raise ValueError(f"unsupported exchange: {exchange}")


def baostock_to_rqalpha(code):
    exchange, symbol = code.split(".")
    if exchange == "sh":
        return f"{symbol}.XSHG"
    if exchange == "sz":
        return f"{symbol}.XSHE"
    raise ValueError(f"unsupported exchange: {exchange}")


@contextmanager
def baostock_session():
    import baostock as bs

    result = bs.login()
    if getattr(result, "error_code", "0") != "0":
        raise RuntimeError(getattr(result, "error_msg", "baostock login failed"))

    try:
        yield bs
    finally:
        bs.logout()


class BaostockClient:
    def __init__(self, adjustflag="2"):
        self.adjustflag = adjustflag

    def query_daily(self, order_book_id, start_date, end_date):
        baostock_code = rqalpha_to_baostock(order_book_id)
        fields = ",".join(DAILY_FIELDS)
        with baostock_session() as bs:
            result = bs.query_history_k_data_plus(
                baostock_code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=self.adjustflag,
            )
            frame = _result_to_frame(result)

        if "code" in frame.columns:
            frame["order_book_id"] = frame["code"].map(baostock_to_rqalpha)
        return frame

    def query_profit_data(self, order_book_id, year, quarter):
        with baostock_session() as bs:
            result = bs.query_profit_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), PROFIT_FIELD_ALIASES)

    def query_balance_data(self, order_book_id, year, quarter):
        with baostock_session() as bs:
            result = bs.query_balance_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), BALANCE_FIELD_ALIASES)

    def query_growth_data(self, order_book_id, year, quarter):
        with baostock_session() as bs:
            result = bs.query_growth_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), GROWTH_FIELD_ALIASES)


def _result_to_frame(result):
    if getattr(result, "error_code", "0") != "0":
        raise RuntimeError(getattr(result, "error_msg", "baostock query failed"))

    rows = []
    while result.next():
        rows.append(result.get_row_data())
    return pd.DataFrame(rows, columns=result.fields)


def _normalize_fields(frame, aliases):
    for source, target in aliases.items():
        if source in frame.columns and target not in frame.columns:
            frame[target] = frame[source]
    return frame
