from datetime import date, datetime

import numpy as np
import pandas as pd

from rqalpha.const import TRADING_CALENDAR_TYPE
from rqalpha.data.base_data_source.data_source import BaseDataSource
from rqalpha.utils.datetime_func import convert_date_to_int
from rqalpha.utils.exception import RQInvalidArgument

from .cache import BaostockCache
from .code_map import rqalpha_to_baostock


BAOSTOCK_FIELDS = [
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

FINANCIAL_TABLES = ("profit", "balance", "growth", "cash_flow", "dupont")
FINANCIAL_FIELD_ALIASES = {
    "profit": {
        "roeAvg": "roe",
        "ROA": "roa",
        "roa": "roa",
        "gpMargin": "gross_margin",
    },
    "balance": {
        "liabilityToAsset": "debt_to_asset",
        "assetLiabRatio": "debt_to_asset",
    },
    "growth": {
        "YOYRevenue": "revenue_growth_yoy",
        "YOYOperatingRevenue": "revenue_growth_yoy",
        "operating_revenue_yoy": "revenue_growth_yoy",
        "YOYNI": "net_profit_growth_yoy",
        "YOYPNI": "net_profit_growth_yoy",
        "net_profit_yoy": "net_profit_growth_yoy",
    },
    "cash_flow": {
        "CFOToOR": "operating_cashflow_to_revenue",
        "CFOToNP": "operating_cashflow_to_net_profit",
    },
    "dupont": {
        "dupontAssetStoEquity": "asset_to_equity",
        "dupontAssetTurn": "asset_turnover",
    },
}

BAR_DTYPE = np.dtype([
    ("datetime", "<u8"),
    ("open", "<f8"),
    ("high", "<f8"),
    ("low", "<f8"),
    ("close", "<f8"),
    ("volume", "<f8"),
    ("total_turnover", "<f8"),
    ("amount", "<f8"),
    ("turn", "<f8"),
    ("tradestatus", "<i4"),
    ("peTTM", "<f8"),
    ("pbMRQ", "<f8"),
    ("psTTM", "<f8"),
    ("isST", "<i4"),
])


def fetch_baostock_daily_data(order_book_id, start_date, end_date, adjustflag):
    try:
        import baostock as bs
    except ImportError:
        raise RuntimeError("未安装 baostock，请先执行 pip install baostock")

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError("Baostock 登录失败: {}".format(lg.error_msg))
    try:
        rs = bs.query_history_k_data_plus(
            rqalpha_to_baostock(order_book_id),
            ",".join(BAOSTOCK_FIELDS),
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag=adjustflag,
        )
        if rs.error_code != "0":
            raise RuntimeError("Baostock 查询失败: {}".format(rs.error_msg))
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        return pd.DataFrame(rows, columns=rs.fields)
    finally:
        bs.logout()


def fetch_baostock_financial_data(order_book_id, table, year, quarter):
    try:
        import baostock as bs
    except ImportError:
        raise RuntimeError("未安装 baostock，请先执行 pip install baostock")

    query_name = {
        "profit": "query_profit_data",
        "balance": "query_balance_data",
        "growth": "query_growth_data",
        "cash_flow": "query_cash_flow_data",
        "dupont": "query_dupont_data",
    }.get(table)
    if query_name is None:
        raise ValueError("unsupported baostock financial table: {}".format(table))

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError("Baostock 登录失败: {}".format(lg.error_msg))
    try:
        query = getattr(bs, query_name)
        rs = query(code=rqalpha_to_baostock(order_book_id), year=year, quarter=quarter)
        if rs.error_code != "0":
            raise RuntimeError("Baostock 财务查询失败: {}".format(rs.error_msg))
        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        frame = pd.DataFrame(rows, columns=rs.fields)
    finally:
        bs.logout()

    return normalize_financial_data(frame, order_book_id, table, year, quarter)


def normalize_financial_data(frame, order_book_id, table, year=None, quarter=None):
    frame = pd.DataFrame() if frame is None else pd.DataFrame(frame).copy()
    if frame.empty:
        return frame
    aliases = FINANCIAL_FIELD_ALIASES.get(table, {})
    for source, target in aliases.items():
        if source in frame.columns and target not in frame.columns:
            frame[target] = frame[source]
    frame = _derive_financial_fields(frame, table)
    if "pubDate" in frame.columns and "pub_date" not in frame.columns:
        frame["pub_date"] = frame["pubDate"]
    if "statDate" in frame.columns and "stat_date" not in frame.columns:
        frame["stat_date"] = frame["statDate"]
    if "order_book_id" not in frame.columns:
        frame["order_book_id"] = order_book_id
    if year is not None and "year" not in frame.columns:
        frame["year"] = int(year)
    if quarter is not None and "quarter" not in frame.columns:
        frame["quarter"] = int(quarter)
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


def _to_float(value):
    if value in ("", None):
        return np.nan
    return float(value)


def _to_int(value):
    if value in ("", None):
        return 0
    return int(float(value))


def dataframe_to_bars(data):
    rows = []
    if data is None or len(data) == 0:
        return np.array([], dtype=BAR_DTYPE)

    for _, row in data.sort_values("date").iterrows():
        rows.append((
            np.uint64(convert_date_to_int(pd.Timestamp(row["date"]).date())),
            _to_float(row.get("open")),
            _to_float(row.get("high")),
            _to_float(row.get("low")),
            _to_float(row.get("close")),
            _to_float(row.get("volume")),
            _to_float(row.get("amount")),
            _to_float(row.get("amount")),
            _to_float(row.get("turn")),
            _to_int(row.get("tradestatus")),
            _to_float(row.get("peTTM")),
            _to_float(row.get("pbMRQ")),
            _to_float(row.get("psTTM")),
            _to_int(row.get("isST")),
        ))
    return np.array(rows, dtype=BAR_DTYPE)


class BaostockDataSource(BaseDataSource):
    def __init__(self, base_config, mod_config):
        super(BaostockDataSource, self).__init__(base_config)
        self._cache = BaostockCache(mod_config.cache_dir)
        self._adjustflag = str(mod_config.adjustflag)
        self._start_date = str(mod_config.start_date)
        end_date = mod_config.end_date
        self._end_date = str(end_date) if end_date else str(base_config.end_date)
        self._runtime_fetch = bool(getattr(mod_config, "runtime_fetch", True))
        self._financial_tables = tuple(
            getattr(mod_config, "financial_tables", FINANCIAL_TABLES) or ()
        )

    def _fetch_baostock(self, order_book_id, start_date, end_date, adjustflag):
        return fetch_baostock_daily_data(order_book_id, start_date, end_date, adjustflag)

    def _fetch_baostock_financial(self, order_book_id, table, year, quarter):
        return fetch_baostock_financial_data(order_book_id, table, year, quarter)

    def _cn_stock_trading_dates(self):
        try:
            return self.get_trading_calendars()[TRADING_CALENDAR_TYPE.CN_STOCK]
        except (AttributeError, KeyError):
            return None

    def _all_baostock_day_bars(self, order_book_id):
        runtime_fetch = getattr(self, "_runtime_fetch", True)
        if hasattr(self._cache, "load_daily_range"):
            data = self._cache.load_daily_range(
                order_book_id,
                self._start_date,
                self._end_date,
                self._adjustflag,
                self._fetch_baostock if runtime_fetch else None,
                required_columns=BAOSTOCK_FIELDS,
                trading_dates=self._cn_stock_trading_dates(),
            )
        else:
            data = self._cache.load_or_fetch(
                order_book_id,
                self._start_date,
                self._end_date,
                self._adjustflag,
                self._fetch_baostock,
            )
        if data is None:
            data = pd.DataFrame()
        return dataframe_to_bars(data)

    def prepare_data(self, symbols=None):
        symbols = list(symbols or [])
        for order_book_id in symbols:
            self._cache.load_daily_range(
                order_book_id,
                self._start_date,
                self._end_date,
                self._adjustflag,
                self._fetch_baostock,
                required_columns=BAOSTOCK_FIELDS,
                trading_dates=self._cn_stock_trading_dates(),
            )
            year_quarters = _financial_year_quarters(self._start_date, self._end_date)
            for table in self._financial_tables:
                self._cache.update_financial_quarters(
                    order_book_id,
                    table,
                    year_quarters,
                    self._fetch_baostock_financial,
                )

    def get_bar(self, instrument, dt, frequency):
        if frequency != "1d":
            raise NotImplementedError("BaostockDataSource 只支持 A 股日线")

        bars = self._all_baostock_day_bars(instrument.order_book_id)
        if len(bars) == 0:
            return None
        dt_int = np.uint64(convert_date_to_int(dt))
        pos = bars["datetime"].searchsorted(dt_int)
        if pos >= len(bars) or bars["datetime"][pos] != dt_int:
            return None
        return bars[pos]

    @staticmethod
    def _are_fields_valid(fields, valid_fields):
        if fields is None:
            return True
        if isinstance(fields, str):
            return fields in valid_fields
        return all(field in valid_fields for field in fields)

    def history_bars(
        self,
        instrument,
        bar_count,
        frequency,
        fields,
        dt,
        skip_suspended=True,
        include_now=False,
        adjust_type="pre",
        adjust_orig=None,
    ):
        if frequency != "1d":
            raise NotImplementedError("BaostockDataSource 只支持 A 股日线")

        bars = self._all_baostock_day_bars(instrument.order_book_id)
        if not self._are_fields_valid(fields, bars.dtype.names):
            raise RQInvalidArgument("invalid fields: {}".format(fields))
        if skip_suspended:
            bars = bars[bars["tradestatus"] == 1]
        if len(bars) == 0:
            return bars if fields is None else bars[fields]

        dt_int = np.uint64(convert_date_to_int(dt))
        right = bars["datetime"].searchsorted(dt_int, side="right")
        left = 0 if bar_count is None else max(0, right - bar_count)
        result = bars[left:right]
        return result if fields is None else result[fields]

    def available_data_range(self, frequency):
        if frequency != "1d":
            raise NotImplementedError("BaostockDataSource 只支持 A 股日线")
        return (
            datetime.strptime(self._start_date, "%Y-%m-%d").date(),
            datetime.strptime(self._end_date, "%Y-%m-%d").date(),
        )


def _financial_year_quarters(start_date, end_date):
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    start_year = start.year - 1
    quarters = []
    for year in range(start_year, end.year + 1):
        for quarter in range(1, 5):
            quarter_start_month = (quarter - 1) * 3 + 1
            quarter_start = pd.Timestamp(year=year, month=quarter_start_month, day=1)
            if quarter_start <= end:
                quarters.append((year, quarter))
    return quarters
