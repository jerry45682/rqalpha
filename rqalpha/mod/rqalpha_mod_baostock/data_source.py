from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from contextlib import contextmanager
from datetime import date, datetime
from functools import lru_cache

import numpy as np
import pandas as pd

from rqalpha.const import TRADING_CALENDAR_TYPE
from rqalpha.data.base_data_source.data_source import BaseDataSource
from rqalpha.utils.logger import user_system_log
from rqalpha.utils.datetime_func import convert_date_to_int
from rqalpha.utils.exception import RQInvalidArgument

from .cache import BaostockCache
from .code_map import baostock_to_rqalpha, rqalpha_to_baostock


BAOSTOCK_FIELDS = [
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

FINANCIAL_TABLES = ("profit", "balance", "growth", "cash_flow", "dupont", "operation")
INDEX_COMPONENT_QUERIES = {
    "000300.XSHG": "query_hs300_stocks",
    "399300.XSHE": "query_hs300_stocks",
    "000016.XSHG": "query_sz50_stocks",
    "000905.XSHG": "query_zz500_stocks",
    "000852.XSHG": None,  # baostock doesn't have CSI 1000 API — fallback to bundle
}
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
    "operation": {
        "NRTurnRatio": "receivables_turnover",
        "NRTurnDays": "receivables_turnover_days",
        "INVTurnRatio": "inventory_turnover",
        "INVTurnDays": "inventory_turnover_days",
        "CATurnRatio": "current_asset_turnover",
        "AssetTurnRatio": "asset_turnover",
    },
}

BAR_DTYPE = np.dtype([
    ("datetime", "<u8"),
    ("open", "<f8"),
    ("high", "<f8"),
    ("low", "<f8"),
    ("close", "<f8"),
    ("preclose", "<f8"),
    ("volume", "<f8"),
    ("total_turnover", "<f8"),
    ("amount", "<f8"),
    ("turn", "<f8"),
    ("tradestatus", "<i4"),
    ("pctChg", "<f8"),
    ("peTTM", "<f8"),
    ("pbMRQ", "<f8"),
    ("psTTM", "<f8"),
    ("pcfNcfTTM", "<f8"),
    ("isST", "<i4"),
])


def _import_baostock():
    try:
        import baostock as bs
    except ImportError:
        raise RuntimeError("baostock is not installed; please run pip install baostock")
    return bs


@contextmanager
def _baostock_session():
    bs = _import_baostock()
    login_result = bs.login()
    if login_result.error_code != "0":
        raise RuntimeError("Baostock login failed: {}".format(login_result.error_msg))
    try:
        yield bs
    finally:
        bs.logout()


def _result_to_frame(result, error_message):
    if result.error_code != "0":
        raise RuntimeError("{}: {}".format(error_message, result.error_msg))
    rows = []
    while result.next():
        rows.append(result.get_row_data())
    return pd.DataFrame(rows, columns=result.fields)


def _query_daily_data(bs, order_book_id, start_date, end_date, adjustflag):
    result = bs.query_history_k_data_plus(
        rqalpha_to_baostock(order_book_id),
        ",".join(BAOSTOCK_FIELDS),
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag=adjustflag,
    )
    return _result_to_frame(result, "Baostock daily query failed")


def fetch_baostock_daily_data(order_book_id, start_date, end_date, adjustflag):
    with _baostock_session() as bs:
        return _query_daily_data(bs, order_book_id, start_date, end_date, adjustflag)


def _query_index_components(bs, index_order_book_id, date=None):
    query_name = INDEX_COMPONENT_QUERIES.get(index_order_book_id)
    if query_name is None:
        raise ValueError(
            "unsupported baostock index components: {}".format(index_order_book_id)
        )

    query = getattr(bs, query_name)
    kwargs = {}
    if date:
        kwargs["date"] = str(date)
    frame = _result_to_frame(
        query(**kwargs),
        "Baostock index components query failed",
    )
    if frame.empty or "code" not in frame.columns:
        return []
    return [baostock_to_rqalpha(code) for code in frame["code"].dropna()]


def fetch_baostock_index_components(index_order_book_id, date=None):
    with _baostock_session() as bs:
        return _query_index_components(bs, index_order_book_id, date=date)


def _query_financial_data(bs, order_book_id, table, year, quarter):
    query_name = {
        "profit": "query_profit_data",
        "balance": "query_balance_data",
        "growth": "query_growth_data",
        "cash_flow": "query_cash_flow_data",
        "dupont": "query_dupont_data",
        "operation": "query_operation_data",
    }.get(table)
    if query_name is None:
        raise ValueError("unsupported baostock financial table: {}".format(table))

    query = getattr(bs, query_name)
    frame = _result_to_frame(
        query(code=rqalpha_to_baostock(order_book_id), year=year, quarter=quarter),
        "Baostock financial query failed",
    )
    return normalize_financial_data(frame, order_book_id, table, year, quarter)


def fetch_baostock_financial_data(order_book_id, table, year, quarter):
    with _baostock_session() as bs:
        return _query_financial_data(bs, order_book_id, table, year, quarter)

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
            _to_float(row.get("preclose")),
            _to_float(row.get("volume")),
            _to_float(row.get("amount")),
            _to_float(row.get("amount")),
            _to_float(row.get("turn")),
            _to_int(row.get("tradestatus")),
            _to_float(row.get("pctChg")),
            _to_float(row.get("peTTM")),
            _to_float(row.get("pbMRQ")),
            _to_float(row.get("psTTM")),
            _to_float(row.get("pcfNcfTTM")),
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
        self._prefetch_workers = _normalize_prefetch_workers(
            getattr(mod_config, "prefetch_workers", 2)
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

    @lru_cache(maxsize=512)
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
        total = len(symbols)
        trading_dates = self._cn_stock_trading_dates()
        listed_dates = self._listed_dates_for_symbols(symbols)
        tasks = []
        completed = 0

        for order_book_id in symbols:
            listed_date = listed_dates.get(order_book_id)
            daily_start_date = _prefetch_daily_start_date(
                self._start_date, listed_date
            )
            year_quarters = _financial_year_quarters(
                self._start_date, self._end_date, min_start_date=listed_date
            )
            if self._is_prefetch_cached(
                order_book_id, year_quarters, trading_dates, daily_start_date
            ):
                completed += 1
                _log_prefetch_progress(completed, total, order_book_id, "cached")
                continue
            tasks.append(
                self._build_prefetch_task(
                    order_book_id, year_quarters, trading_dates, daily_start_date
                )
            )

        if not tasks:
            return

        workers = min(getattr(self, "_prefetch_workers", 1), len(tasks))
        if workers <= 1:
            failed = self._run_prefetch_serial(tasks, completed, total)
        else:
            failed = self._run_prefetch_parallel(tasks, workers, completed, total)

        if failed:
            user_system_log.warn(
                "Baostock prefetch finished with {} failures: {}", len(failed), failed
            )

    def _listed_dates_for_symbols(self, symbols):
        if not hasattr(self, "get_instruments"):
            return {}

        listed_dates = {}
        try:
            for instrument in self.get_instruments(symbols):
                order_book_id = getattr(instrument, "order_book_id", None)
                listed_date = getattr(instrument, "listed_date", None)
                if order_book_id is None or listed_date is None:
                    continue
                listed_dates[order_book_id] = listed_date
        except Exception:
            return {}
        return listed_dates

    def _is_prefetch_cached(
        self, order_book_id, year_quarters, trading_dates, start_date=None
    ):
        if not hasattr(self._cache, "has_daily_range"):
            return False
        if not self._cache.has_daily_range(
            order_book_id,
            start_date or self._start_date,
            self._end_date,
            self._adjustflag,
            required_columns=BAOSTOCK_FIELDS,
            trading_dates=trading_dates,
        ):
            return False
        if not hasattr(self._cache, "has_financial_quarters"):
            return False
        # Fast path: check financial file existence before reading content
        for table in self._financial_tables:
            path = self._cache.financial_path_for(order_book_id, table)
            if not path.exists():
                return False
        return all(
            self._cache.has_financial_quarters(order_book_id, table, year_quarters)
            for table in self._financial_tables
        )

    def _build_prefetch_task(
        self, order_book_id, year_quarters, trading_dates, start_date=None
    ):
        cache_dir = getattr(self._cache, "_cache_dir", None)
        return {
            "cache_dir": str(cache_dir) if cache_dir is not None else None,
            "order_book_id": order_book_id,
            "start_date": start_date or self._start_date,
            "end_date": self._end_date,
            "adjustflag": self._adjustflag,
            "financial_tables": self._financial_tables,
            "year_quarters": year_quarters,
            "trading_dates": _serialize_trading_dates(trading_dates),
        }

    def _run_prefetch_serial(self, tasks, completed, total):
        failed = []
        with _baostock_session() as bs:
            for task in tasks:
                try:
                    _prefetch_symbol(task, bs, cache=self._cache)
                    completed += 1
                    _log_prefetch_progress(
                        completed, total, task["order_book_id"], "downloaded"
                    )
                except Exception:
                    user_system_log.warn(
                        "Baostock prefetch failed: {}", task["order_book_id"]
                    )
                    failed.append(task["order_book_id"])
        return failed

    def _run_prefetch_parallel(self, tasks, workers, completed, total):
        failed = []
        executor = ProcessPoolExecutor(max_workers=workers)
        try:
            future_to_task = {
                executor.submit(_prefetch_symbol_worker, task): task
                for task in tasks
            }
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    order_book_id = future.result()
                    completed += 1
                    _log_prefetch_progress(
                        completed, total, order_book_id, "downloaded"
                    )
                except Exception:
                    user_system_log.warn(
                        "Baostock prefetch failed: {}", task["order_book_id"]
                    )
                    failed.append(task["order_book_id"])
        finally:
            executor.shutdown(wait=True)
        return failed

    def get_bar(self, instrument, dt, frequency):
        if frequency != "1d":
            raise NotImplementedError("BaostockDataSource only supports A-share daily bars")

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
            raise NotImplementedError("BaostockDataSource only supports A-share daily bars")

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
            raise NotImplementedError("BaostockDataSource only supports A-share daily bars")
        return (
            datetime.strptime(self._start_date, "%Y-%m-%d").date(),
            datetime.strptime(self._end_date, "%Y-%m-%d").date(),
        )


def _financial_year_quarters(start_date, end_date, min_start_date=None):
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    first_quarter_start = pd.Timestamp(year=start.year - 1, month=1, day=1)
    if min_start_date is not None:
        first_quarter_start = max(
            first_quarter_start,
            _quarter_start(pd.Timestamp(min_start_date)),
        )
    quarters = []
    for year in range(first_quarter_start.year, end.year + 1):
        for quarter in range(1, 5):
            quarter_start_month = (quarter - 1) * 3 + 1
            quarter_start = pd.Timestamp(year=year, month=quarter_start_month, day=1)
            if first_quarter_start <= quarter_start <= end:
                quarters.append((year, quarter))
    return quarters


def _quarter_start(value):
    month = ((value.month - 1) // 3) * 3 + 1
    return pd.Timestamp(year=value.year, month=month, day=1)


def _prefetch_daily_start_date(config_start_date, listed_date):
    start = pd.Timestamp(config_start_date)
    if listed_date is not None:
        start = max(start, pd.Timestamp(listed_date))
    return start.strftime("%Y-%m-%d")


def _normalize_prefetch_workers(value):
    workers = max(1, int(value if value is not None else 2))
    if workers > 12:
        user_system_log.warn(
            "Baostock prefetch_workers {} is too high, capped to {}", workers, 12
        )
        return 12
    if workers > 8:
        user_system_log.warn(
            "Baostock prefetch_workers {} may hit rate limits; proceed with caution",
            workers,
        )
    return workers


def _serialize_trading_dates(trading_dates):
    if trading_dates is None:
        return None
    return pd.DatetimeIndex(trading_dates).strftime("%Y-%m-%d").tolist()


def _log_prefetch_progress(index, total, order_book_id, status):
    user_system_log.info(
        "Baostock prefetch progress: {}/{} {} {}",
        index,
        total,
        order_book_id,
        status,
    )


def _prefetch_symbol_worker(task):
    with _baostock_session() as bs:
        return _prefetch_symbol(task, bs)


def _prefetch_symbol(task, bs, cache=None):
    if cache is None:
        cache = BaostockCache(task["cache_dir"])
    order_book_id = task["order_book_id"]
    cache.load_daily_range(
        order_book_id,
        task["start_date"],
        task["end_date"],
        task["adjustflag"],
        lambda *args: _query_daily_data(bs, *args),
        required_columns=BAOSTOCK_FIELDS,
        trading_dates=task["trading_dates"],
    )
    for table in task["financial_tables"]:
        cache.update_financial_quarters(
            order_book_id,
            table,
            task["year_quarters"],
            lambda *args: _query_financial_data(bs, *args),
        )
    return order_book_id
