from datetime import date, datetime

import numpy as np
import pandas as pd

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
    "isST",
]

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

    def _fetch_baostock(self, order_book_id, start_date, end_date, adjustflag):
        return fetch_baostock_daily_data(order_book_id, start_date, end_date, adjustflag)

    def _all_baostock_day_bars(self, order_book_id):
        data = self._cache.load_or_fetch(
            order_book_id,
            self._start_date,
            self._end_date,
            self._adjustflag,
            self._fetch_baostock,
        )
        return dataframe_to_bars(data)

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
