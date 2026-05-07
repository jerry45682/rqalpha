from datetime import date, datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd

from rqalpha.data.base_data_source.data_source import BaseDataSource
from rqalpha.const import TRADING_CALENDAR_TYPE
from rqalpha.mod.rqalpha_mod_baostock.cache import BaostockCache
from rqalpha.mod.rqalpha_mod_baostock.code_map import baostock_to_rqalpha, rqalpha_to_baostock
from rqalpha.mod.rqalpha_mod_baostock.data_source import (
    BaostockDataSource,
    dataframe_to_bars,
    normalize_financial_data,
)
from rqalpha.mod.rqalpha_mod_baostock.mod import BaostockMod


def test_code_map_converts_between_rqalpha_and_baostock_codes():
    assert rqalpha_to_baostock("600000.XSHG") == "sh.600000"
    assert rqalpha_to_baostock("000001.XSHE") == "sz.000001"
    assert baostock_to_rqalpha("sh.600000") == "600000.XSHG"
    assert baostock_to_rqalpha("sz.000001") == "000001.XSHE"


def test_dataframe_to_bars_maps_baostock_fields_to_rqalpha_dtype():
    df = pd.DataFrame(
        [
            {
                "date": "2026-01-05",
                "open": "10.1",
                "high": "10.8",
                "low": "9.9",
                "close": "10.5",
                "volume": "10000",
                "amount": "105000",
                "turn": "1.2",
                "tradestatus": "1",
                "peTTM": "8.5",
                "pbMRQ": "0.9",
                "psTTM": "1.8",
                "isST": "0",
            }
        ]
    )

    bars = dataframe_to_bars(df)

    assert bars.dtype.names == (
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "total_turnover",
        "amount",
        "turn",
        "tradestatus",
        "peTTM",
        "pbMRQ",
        "psTTM",
        "isST",
    )
    assert bars[0]["datetime"] == 20260105000000
    assert bars[0]["close"] == 10.5
    assert bars[0]["psTTM"] == 1.8
    assert bars[0]["total_turnover"] == 105000


def test_cache_reads_existing_csv_without_fetching(tmp_path):
    cache = BaostockCache(tmp_path)
    expected = pd.DataFrame({"date": ["2026-01-05"], "close": ["10.5"]})
    cache.write("600000.XSHG", "2026-01-01", "2026-01-31", "2", expected)

    def fetcher(*args, **kwargs):
        raise AssertionError("不应该在缓存命中时请求 Baostock")

    result = cache.load_or_fetch("600000.XSHG", "2026-01-01", "2026-01-31", "2", fetcher)

    pd.testing.assert_frame_equal(result, expected)


def test_cache_fetches_and_writes_when_missing(tmp_path):
    cache = BaostockCache(tmp_path)
    fetched = pd.DataFrame({"date": ["2026-01-05"], "close": ["10.5"]})

    result = cache.load_or_fetch(
        "600000.XSHG",
        "2026-01-01",
        "2026-01-31",
        "2",
        lambda *args, **kwargs: fetched,
    )

    pd.testing.assert_frame_equal(result, fetched)
    assert cache.path_for("600000.XSHG", "2026-01-01", "2026-01-31", "2").exists()


def test_daily_cache_updates_missing_tail_without_refetching_covered_dates(tmp_path):
    cache = BaostockCache(tmp_path)
    calls = []

    def fetcher(order_book_id, start_date, end_date, adjustflag):
        calls.append((order_book_id, start_date, end_date, adjustflag))
        dates = pd.date_range(start_date, end_date, freq="D")
        return pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "close": range(len(dates)),
            }
        )

    first = cache.load_daily_range(
        "600000.XSHG", "2026-01-01", "2026-01-02", "2", fetcher
    )
    second = cache.load_daily_range(
        "600000.XSHG", "2026-01-01", "2026-01-05", "2", fetcher
    )
    third = cache.load_daily_range(
        "600000.XSHG", "2026-01-01", "2026-01-05", "2", fetcher
    )

    assert calls == [
        ("600000.XSHG", "2026-01-01", "2026-01-02", "2"),
        ("600000.XSHG", "2026-01-05", "2026-01-05", "2"),
    ]
    assert first["date"].tolist() == ["2026-01-01", "2026-01-02"]
    assert second["date"].tolist() == [
        "2026-01-01",
        "2026-01-02",
        "2026-01-05",
    ]
    pd.testing.assert_frame_equal(second, third)


def test_daily_cache_reads_legacy_exact_range_cache_without_fetching(tmp_path):
    cache = BaostockCache(tmp_path)
    legacy = pd.DataFrame(
        {
            "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "close": ["10.1", "10.2", "10.3"],
        }
    )
    cache.write("600000.XSHG", "2026-01-01", "2026-01-03", "2", legacy)

    def fetcher(*args, **kwargs):
        raise AssertionError("legacy exact-range cache should avoid baostock fetch")

    result = cache.load_daily_range(
        "600000.XSHG", "2026-01-01", "2026-01-03", "2", fetcher
    )

    pd.testing.assert_frame_equal(result, legacy)


def test_daily_cache_refetches_covered_cache_missing_required_columns(tmp_path):
    cache = BaostockCache(tmp_path)
    cache.write_daily(
        "600000.XSHG",
        "2",
        pd.DataFrame(
            {
                "date": ["2026-01-01", "2026-01-02"],
                "close": ["10.1", "10.2"],
            }
        ),
    )
    calls = []

    def fetcher(order_book_id, start_date, end_date, adjustflag):
        calls.append((order_book_id, start_date, end_date, adjustflag))
        return pd.DataFrame(
            {
                "date": ["2026-01-01", "2026-01-02"],
                "close": ["10.1", "10.2"],
                "psTTM": ["1.5", "1.6"],
            }
        )

    result = cache.load_daily_range(
        "600000.XSHG",
        "2026-01-01",
        "2026-01-02",
        "2",
        fetcher,
        required_columns=["date", "close", "psTTM"],
    )

    assert calls == [("600000.XSHG", "2026-01-01", "2026-01-02", "2")]
    assert result["psTTM"].tolist() == ["1.5", "1.6"]


def test_daily_cache_fetches_missing_middle_weekday_gap(tmp_path):
    cache = BaostockCache(tmp_path)
    cache.write_daily(
        "600000.XSHG",
        "2",
        pd.DataFrame(
            {
                "date": ["2026-01-02", "2026-01-06"],
                "close": ["10.2", "10.4"],
            }
        ),
    )
    calls = []

    def fetcher(order_book_id, start_date, end_date, adjustflag):
        calls.append((order_book_id, start_date, end_date, adjustflag))
        return pd.DataFrame({"date": [start_date], "close": ["10.3"]})

    result = cache.load_daily_range(
        "600000.XSHG", "2026-01-02", "2026-01-06", "2", fetcher
    )

    assert calls == [("600000.XSHG", "2026-01-05", "2026-01-05", "2")]
    assert result["date"].tolist() == ["2026-01-02", "2026-01-05", "2026-01-06"]


def test_daily_cache_does_not_refetch_known_market_holiday(tmp_path):
    cache = BaostockCache(tmp_path)
    cache.write_daily(
        "600000.XSHG",
        "2",
        pd.DataFrame(
            {
                "date": ["2026-01-02", "2026-01-06"],
                "close": ["10.2", "10.4"],
            }
        ),
    )

    def fetcher(*args):
        raise AssertionError("known market holidays should not be refetched")

    result = cache.load_daily_range(
        "600000.XSHG",
        "2026-01-02",
        "2026-01-06",
        "2",
        fetcher,
        trading_dates=pd.DatetimeIndex(["2026-01-02", "2026-01-06"]),
    )

    assert result["date"].tolist() == ["2026-01-02", "2026-01-06"]


def test_daily_cache_returns_none_when_runtime_fetch_is_disabled_and_cache_missing(tmp_path):
    cache = BaostockCache(tmp_path)

    result = cache.load_daily_range(
        "600000.XSHG", "2026-01-01", "2026-01-04", "2", fetcher=None
    )

    assert result is None


def test_financial_cache_updates_only_missing_quarters(tmp_path):
    cache = BaostockCache(tmp_path)
    calls = []

    def fetcher(order_book_id, table, year, quarter):
        calls.append((order_book_id, table, year, quarter))
        return pd.DataFrame(
            {
                "code": ["sh.600000"],
                "pubDate": [f"{year}-{quarter * 3:02d}-30"],
                "roe": [quarter / 100],
            }
        )

    cache.update_financial_quarters(
        "600000.XSHG", "profit", [(2025, 4), (2026, 1)], fetcher
    )
    result = cache.update_financial_quarters(
        "600000.XSHG", "profit", [(2025, 4), (2026, 1), (2026, 2)], fetcher
    )

    assert calls == [
        ("600000.XSHG", "profit", 2025, 4),
        ("600000.XSHG", "profit", 2026, 1),
        ("600000.XSHG", "profit", 2026, 2),
    ]
    assert result[["year", "quarter"]].drop_duplicates().values.tolist() == [
        [2025, 4],
        [2026, 1],
        [2026, 2],
    ]


def test_normalize_dupont_financial_data_derives_roa():
    frame = pd.DataFrame(
        [
            {
                "code": "sh.600000",
                "pubDate": "2026-04-30",
                "statDate": "2026-03-31",
                "dupontROE": "0.12",
                "dupontAssetStoEquity": "4.0",
            }
        ]
    )

    result = normalize_financial_data(frame, "600000.XSHG", "dupont", 2026, 1)

    assert result.loc[0, "roa"] == 0.03
    assert result.loc[0, "asset_to_equity"] == "4.0"


def test_baostock_data_source_inherits_base_data_source():
    assert issubclass(BaostockDataSource, BaseDataSource)


def test_get_bar_and_history_bars_read_cached_daily_data():
    source = BaostockDataSource.__new__(BaostockDataSource)
    source._adjustflag = "2"
    source._start_date = "2026-01-01"
    source._end_date = "2026-01-31"
    source._cache = SimpleNamespace(
        load_or_fetch=lambda *args, **kwargs: pd.DataFrame(
            [
                {"date": "2026-01-05", "open": "10", "high": "11", "low": "9", "close": "10.5", "volume": "100", "amount": "1050", "turn": "1", "tradestatus": "1", "peTTM": "8", "pbMRQ": "1", "isST": "0"},
                {"date": "2026-01-06", "open": "11", "high": "12", "low": "10", "close": "11.5", "volume": "200", "amount": "2300", "turn": "2", "tradestatus": "1", "peTTM": "9", "pbMRQ": "1.1", "isST": "0"},
            ]
        )
    )
    source._fetch_baostock = lambda *args, **kwargs: None
    instrument = SimpleNamespace(order_book_id="600000.XSHG")

    bar = source.get_bar(instrument, date(2026, 1, 6), "1d")
    history = source.history_bars(instrument, 1, "1d", ["close", "peTTM"], datetime(2026, 1, 6))

    assert bar["close"] == 11.5
    assert history.tolist() == [(11.5, 9.0)]


def test_data_source_reads_prepared_daily_cache_without_runtime_fetch(tmp_path):
    cache = BaostockCache(tmp_path)
    cache.load_daily_range(
        "600000.XSHG",
        "2026-01-01",
        "2026-01-31",
        "2",
        lambda *args: pd.DataFrame(
            [
                {"date": "2026-01-05", "code": "sh.600000", "open": "10", "high": "11", "low": "9", "close": "10.5", "volume": "100", "amount": "1050", "turn": "1", "tradestatus": "1", "peTTM": "8", "pbMRQ": "1", "psTTM": "2", "isST": "0"},
            ]
        ),
    )
    source = BaostockDataSource.__new__(BaostockDataSource)
    source._adjustflag = "2"
    source._start_date = "2026-01-01"
    source._end_date = "2026-01-31"
    source._cache = BaostockCache(tmp_path)
    source._runtime_fetch = False
    source._fetch_baostock = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("runtime fetch should not be used when cache exists")
    )

    bar = source.get_bar(SimpleNamespace(order_book_id="600000.XSHG"), date(2026, 1, 5), "1d")

    assert bar["close"] == 10.5


def test_data_source_refetches_prepared_daily_cache_missing_required_fields(tmp_path):
    cache = BaostockCache(tmp_path)
    cache.load_daily_range(
        "600000.XSHG",
        "2026-01-01",
        "2026-01-31",
        "2",
        lambda *args: pd.DataFrame(
            [
                {"date": "2026-01-05", "code": "sh.600000", "open": "10", "high": "11", "low": "9", "close": "10.5", "volume": "100", "amount": "1050", "turn": "1", "tradestatus": "1", "peTTM": "8", "pbMRQ": "1", "isST": "0"},
            ]
        ),
    )
    source = BaostockDataSource.__new__(BaostockDataSource)
    source._adjustflag = "2"
    source._start_date = "2026-01-01"
    source._end_date = "2026-01-31"
    source._cache = BaostockCache(tmp_path)
    source._runtime_fetch = True
    calls = []

    def fetcher(*args):
        calls.append(args)
        return pd.DataFrame(
            [
                {"date": "2026-01-05", "code": "sh.600000", "open": "10", "high": "11", "low": "9", "close": "10.5", "volume": "100", "amount": "1050", "turn": "1", "tradestatus": "1", "peTTM": "8", "pbMRQ": "1", "psTTM": "2", "isST": "0"},
            ]
        )

    source._fetch_baostock = fetcher

    history = source.history_bars(
        SimpleNamespace(order_book_id="600000.XSHG"),
        1,
        "1d",
        ["close", "psTTM"],
        date(2026, 1, 5),
    )

    assert calls == [("600000.XSHG", "2026-01-01", "2026-01-31", "2")]
    assert history.tolist() == [(10.5, 2.0)]


def test_data_source_prepare_data_passes_cn_stock_trading_calendar():
    source = BaostockDataSource.__new__(BaostockDataSource)
    source._adjustflag = "2"
    source._start_date = "2026-01-01"
    source._end_date = "2026-01-31"
    source._financial_tables = ()
    source._fetch_baostock = lambda *args: pd.DataFrame()
    captured = {}

    class FakeCache:
        def load_daily_range(self, *args, **kwargs):
            captured["trading_dates"] = kwargs.get("trading_dates")
            return pd.DataFrame()

    source._cache = FakeCache()
    source.get_trading_calendars = lambda: {
        TRADING_CALENDAR_TYPE.CN_STOCK: pd.DatetimeIndex(["2026-01-05"])
    }

    source.prepare_data(["600000.XSHG"])

    assert list(captured["trading_dates"]) == [pd.Timestamp("2026-01-05")]


def test_baostock_mod_prefetches_configured_symbols(monkeypatch, tmp_path):
    from rqalpha.mod.rqalpha_mod_baostock import mod as baostock_mod

    prepared = []

    class FakeDataSource:
        def __init__(self, base_config, mod_config):
            self.base_config = base_config
            self.mod_config = mod_config

        def prepare_data(self, symbols=None):
            prepared.extend(symbols)

    monkeypatch.setattr(baostock_mod, "BaostockDataSource", FakeDataSource)
    env = SimpleNamespace(
        config=SimpleNamespace(
            base=SimpleNamespace(
                end_date=date(2026, 1, 31),
            )
        ),
        set_data_source=lambda data_source: None,
    )

    BaostockMod().start_up(
        env,
        SimpleNamespace(
            cache_dir=tmp_path,
            adjustflag="2",
            start_date="2026-01-01",
            end_date="2026-01-31",
            prefetch=True,
            symbols=["600000.XSHG", "000001.XSHE"],
            runtime_fetch=False,
            financial_tables=["profit"],
        ),
    )

    assert prepared == ["600000.XSHG", "000001.XSHE"]


def test_available_data_range_uses_configured_range():
    source = BaostockDataSource.__new__(BaostockDataSource)
    source._start_date = "2026-01-01"
    source._end_date = "2026-01-31"

    assert source.available_data_range("1d") == (date(2026, 1, 1), date(2026, 1, 31))
