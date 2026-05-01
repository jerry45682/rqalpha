from datetime import date, datetime
from types import SimpleNamespace

import numpy as np
import pandas as pd

from rqalpha.data.base_data_source.data_source import BaseDataSource
from rqalpha.mod.rqalpha_mod_baostock.cache import BaostockCache
from rqalpha.mod.rqalpha_mod_baostock.code_map import baostock_to_rqalpha, rqalpha_to_baostock
from rqalpha.mod.rqalpha_mod_baostock.data_source import BaostockDataSource, dataframe_to_bars


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
        "isST",
    )
    assert bars[0]["datetime"] == 20260105000000
    assert bars[0]["close"] == 10.5
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


def test_available_data_range_uses_configured_range():
    source = BaostockDataSource.__new__(BaostockDataSource)
    source._start_date = "2026-01-01"
    source._end_date = "2026-01-31"

    assert source.available_data_range("1d") == (date(2026, 1, 1), date(2026, 1, 31))
