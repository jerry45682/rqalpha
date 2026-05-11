from contextlib import contextmanager

import pandas as pd


DAILY_FIELDS = [
    "date",
    "code",
    "open",
    "high",
    "low",
    "close",
    "preclose",
    "volume",
    "amount",
    "turn",
    "tradestatus",
    "pctChg",
    "peTTM",
    "pbMRQ",
    "psTTM",
    "pcfNcfTTM",
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

CASH_FLOW_FIELD_ALIASES = {
    "CFOToOR": "operating_cashflow_to_revenue",
    "CFOToNP": "operating_cashflow_to_net_profit",
}

DUPONT_FIELD_ALIASES = {
    "dupontAssetStoEquity": "asset_to_equity",
    "dupontAssetTurn": "asset_turnover",
}

OPERATION_FIELD_ALIASES = {
    "NRTurnRatio": "receivables_turnover",
    "NRTurnDays": "receivables_turnover_days",
    "INVTurnRatio": "inventory_turnover",
    "INVTurnDays": "inventory_turnover_days",
    "CATurnRatio": "current_asset_turnover",
    "AssetTurnRatio": "asset_turnover",
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

    # ------------------------------------------------------------------
    # Session management helpers (reuse one session across many queries)
    # ------------------------------------------------------------------

    @staticmethod
    def login():
        import baostock as bs

        result = bs.login()
        if getattr(result, "error_code", "0") != "0":
            raise RuntimeError(getattr(result, "error_msg", "baostock login failed"))
        return bs

    @staticmethod
    def logout(bs):
        if bs is not None:
            bs.logout()

    # ------------------------------------------------------------------
    # Query methods – pass bs=None to auto-create a session,
    # or pass a shared bs to reuse an existing login.
    # ------------------------------------------------------------------

    def query_daily(self, order_book_id, start_date, end_date, bs=None):
        baostock_code = rqalpha_to_baostock(order_book_id)
        fields = ",".join(DAILY_FIELDS)
        if bs is not None:
            result = bs.query_history_k_data_plus(
                baostock_code,
                fields,
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=self.adjustflag,
            )
            frame = _result_to_frame(result)
        else:
            with baostock_session() as session:
                result = session.query_history_k_data_plus(
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

    def query_profit_data(self, order_book_id, year, quarter, bs=None):
        if bs is not None:
            result = bs.query_profit_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), PROFIT_FIELD_ALIASES)
        with baostock_session() as session:
            result = session.query_profit_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), PROFIT_FIELD_ALIASES)

    def query_balance_data(self, order_book_id, year, quarter, bs=None):
        if bs is not None:
            result = bs.query_balance_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), BALANCE_FIELD_ALIASES)
        with baostock_session() as session:
            result = session.query_balance_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), BALANCE_FIELD_ALIASES)

    def query_growth_data(self, order_book_id, year, quarter, bs=None):
        if bs is not None:
            result = bs.query_growth_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), GROWTH_FIELD_ALIASES)
        with baostock_session() as session:
            result = session.query_growth_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), GROWTH_FIELD_ALIASES)

    def query_cash_flow_data(self, order_book_id, year, quarter, bs=None):
        if bs is not None:
            result = bs.query_cash_flow_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), CASH_FLOW_FIELD_ALIASES)
        with baostock_session() as session:
            result = session.query_cash_flow_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), CASH_FLOW_FIELD_ALIASES)

    def query_dupont_data(self, order_book_id, year, quarter, bs=None):
        if bs is not None:
            result = bs.query_dupont_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _derive_financial_fields(
                _normalize_fields(_result_to_frame(result), DUPONT_FIELD_ALIASES),
                "dupont",
            )
        with baostock_session() as session:
            result = session.query_dupont_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _derive_financial_fields(
                _normalize_fields(_result_to_frame(result), DUPONT_FIELD_ALIASES),
                "dupont",
            )

    def query_operation_data(self, order_book_id, year, quarter, bs=None):
        if bs is not None:
            result = bs.query_operation_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), OPERATION_FIELD_ALIASES)
        with baostock_session() as session:
            result = session.query_operation_data(
                code=rqalpha_to_baostock(order_book_id),
                year=year,
                quarter=quarter,
            )
            return _normalize_fields(_result_to_frame(result), OPERATION_FIELD_ALIASES)

    def query_stock_industry(self, code="", date="", bs=None):
        baostock_code = rqalpha_to_baostock(code) if code else ""
        query_date = "" if date in (None, "") else str(pd.Timestamp(date).date())
        if bs is not None:
            result = bs.query_stock_industry(
                code=baostock_code,
                date=query_date,
            )
            frame = _result_to_frame(result)
        else:
            with baostock_session() as session:
                result = session.query_stock_industry(
                    code=baostock_code,
                    date=query_date,
                )
                frame = _result_to_frame(result)

        if "code" in frame.columns:
            frame["order_book_id"] = frame["code"].map(baostock_to_rqalpha)
        return frame

    def query_financial_table(self, order_book_id, table, year, quarter, bs=None):
        query = {
            "profit": self.query_profit_data,
            "balance": self.query_balance_data,
            "growth": self.query_growth_data,
            "cash_flow": self.query_cash_flow_data,
            "dupont": self.query_dupont_data,
            "operation": self.query_operation_data,
        }.get(table)
        if query is None:
            raise ValueError(f"unsupported baostock financial table: {table}")

        frame = query(order_book_id, year, quarter, bs=bs)
        if frame.empty:
            return frame
        if "pubDate" in frame.columns and "pub_date" not in frame.columns:
            frame["pub_date"] = frame["pubDate"]
        if "statDate" in frame.columns and "stat_date" not in frame.columns:
            frame["stat_date"] = frame["statDate"]
        if "order_book_id" not in frame.columns:
            frame["order_book_id"] = order_book_id
        frame["year"] = int(year)
        frame["quarter"] = int(quarter)
        return frame


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


def _derive_financial_fields(frame, table):
    if frame.empty or table != "dupont" or "roa" in frame.columns:
        return frame
    if "dupontROE" not in frame.columns or "dupontAssetStoEquity" not in frame.columns:
        return frame

    roe = pd.to_numeric(frame["dupontROE"], errors="coerce")
    asset_to_equity = pd.to_numeric(frame["dupontAssetStoEquity"], errors="coerce")
    frame["roa"] = roe / asset_to_equity.replace(0, pd.NA)
    return frame
