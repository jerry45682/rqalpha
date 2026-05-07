import inspect

import pandas as pd
import pytest

from rqalpha_factor_framework.data.cache import CsvCache
from rqalpha_factor_framework.data.factor_store import FactorStore


class DummyClient:
    def __init__(self):
        self.calls = []

    def query_daily(self, order_book_id, start_date, end_date):
        self.calls.append((order_book_id, start_date, end_date))
        return pd.DataFrame(
            {
                "date": [start_date],
                "order_book_id": [order_book_id],
                "close": [len(self.calls)],
            }
        )


def _assert_relative_to(path, root):
    path.resolve().relative_to(root.resolve())


def test_csv_cache_load_or_fetch_writes_and_reuses_data(tmp_path):
    cache = CsvCache(tmp_path)
    calls = []

    def fetcher():
        calls.append("fetch")
        return pd.DataFrame({"date": ["2023-01-03"], "close": [10.0]})

    first = cache.load_or_fetch("daily", "600000.XSHG", fetcher)
    second = cache.load_or_fetch("daily", "600000.XSHG", fetcher)

    assert calls == ["fetch"]
    assert first.equals(second)
    assert (tmp_path / "daily" / "600000_XSHG.csv").exists()


def test_csv_cache_path_for_sanitizes_names_without_escaping_root(tmp_path):
    cache = CsvCache(tmp_path)

    windows_path = cache.path_for("daily:raw", r"C:\temp\evil")
    parent_escape = cache.path_for("daily", r"..\evil")

    _assert_relative_to(windows_path, tmp_path)
    assert windows_path.parent == tmp_path / "daily_raw"
    assert windows_path.name == "C__temp_evil.csv"
    _assert_relative_to(parent_escape, tmp_path)
    assert parent_escape.parent == tmp_path / "daily"
    assert parent_escape.name == "___evil.csv"


def test_csv_cache_path_for_does_not_require_path_is_relative_to(tmp_path):
    cache = CsvCache(tmp_path)

    path = cache.path_for("daily", "600000.XSHG")

    assert "is_relative_to" not in inspect.getsource(CsvCache.path_for)
    _assert_relative_to(path, tmp_path)
    assert path.name == "600000_XSHG.csv"


def test_csv_cache_load_or_fetch_reads_back_first_fetch(tmp_path):
    cache = CsvCache(tmp_path)

    def fetcher():
        return pd.DataFrame({"date": [pd.Timestamp("2023-01-03")], "close": [10]})

    first = cache.load_or_fetch("daily", "600000.XSHG", fetcher)
    second = cache.load_or_fetch("daily", "600000.XSHG", fetcher)

    assert first.equals(second)
    assert first.loc[0, "date"] == "2023-01-03"


def test_factor_store_get_daily_uses_date_range_in_cache_key(tmp_path):
    client = DummyClient()
    store = FactorStore(tmp_path, client=client)

    store.get_daily("600000.XSHG", "2023-01-01", "2023-01-31")
    store.get_daily("600000.XSHG", "2023-02-01", "2023-02-28")

    assert client.calls == [
        ("600000.XSHG", "2023-01-01", "2023-01-31"),
        ("600000.XSHG", "2023-02-01", "2023-02-28"),
    ]
    assert (
        tmp_path / "daily" / "600000_XSHG_2023-01-01_2023-01-31.csv"
    ).exists()
    assert (
        tmp_path / "daily" / "600000_XSHG_2023-02-01_2023-02-28.csv"
    ).exists()


def test_factor_store_get_daily_requires_client_only_when_cache_missing(tmp_path):
    store = FactorStore(tmp_path)

    with pytest.raises(RuntimeError, match="data client"):
        store.get_daily("600000.XSHG", "2023-01-01", "2023-01-31")

    cached = pd.DataFrame({"date": ["2023-01-03"], "close": [10.0]})
    CsvCache(tmp_path).load_or_fetch(
        "daily",
        "600000.XSHG_2023-01-01_2023-01-31",
        lambda: cached,
    )

    result = store.get_daily("600000.XSHG", "2023-01-01", "2023-01-31")

    assert result.equals(cached)


def test_factor_store_aligns_latest_financial_row_before_date(tmp_path):
    store = FactorStore(tmp_path)
    frame = pd.DataFrame(
        {
            "pub_date": ["2022-12-31", "2023-03-31"],
            "code": ["600000.XSHG", "600000.XSHG"],
            "roe": [0.1, 0.2],
        }
    )
    store.write_financial("600000.XSHG", "profit", frame)

    aligned = store.get_latest_financial(
        ["600000.XSHG"], "profit", "2023-02-01", ["roe"]
    )

    assert aligned.loc["600000.XSHG", "roe"] == 0.1


def test_factor_store_filters_financial_rows_by_order_book_id(tmp_path):
    store = FactorStore(tmp_path)
    frame = pd.DataFrame(
        {
            "pub_date": ["2022-12-31", "2023-01-31"],
            "order_book_id": ["600000.XSHG", "000001.XSHE"],
            "code": ["600000.XSHG", "000001.XSHE"],
            "roe": [0.1, 0.9],
        }
    )
    store.write_financial("600000.XSHG", "profit", frame)

    aligned = store.get_latest_financial(
        ["600000.XSHG", "000001.XSHE"], "profit", "2023-02-01", ["roe"]
    )

    assert aligned.loc["600000.XSHG", "roe"] == 0.1
    assert pd.isna(aligned.loc["000001.XSHE", "roe"])


def test_factor_store_matches_baostock_financial_code(tmp_path):
    store = FactorStore(tmp_path)
    frame = pd.DataFrame(
        {
            "pub_date": ["2022-12-31", "2023-01-31"],
            "code": ["sh.600000", "sz.000001"],
            "roe": [0.1, 0.9],
        }
    )
    store.write_financial("600000.XSHG", "profit", frame)

    aligned = store.get_latest_financial(
        ["600000.XSHG"], "profit", "2023-02-01", ["roe"]
    )

    assert aligned.loc["600000.XSHG", "roe"] == 0.1


def test_factor_store_returns_financial_tables_filtered_by_publication_date(tmp_path):
    store = FactorStore(tmp_path)
    store.write_financial(
        "600000.XSHG",
        "profit",
        pd.DataFrame(
            {
                "pubDate": ["2026-03-31", "2026-04-30"],
                "roe": [0.10, 0.20],
            }
        ),
    )
    store.write_financial(
        "600000.XSHG",
        "balance",
        pd.DataFrame(
            {
                "pubDate": ["2026-03-31"],
                "debt_to_asset": [0.55],
            }
        ),
    )

    result = store.get_financial_tables(
        ["600000.XSHG"], "2026-04-01", tables=("profit", "balance")
    )

    assert result["600000.XSHG"]["profit"]["roe"].tolist() == [0.10]
    assert result["600000.XSHG"]["balance"]["debt_to_asset"].tolist() == [0.55]


def test_factor_store_filters_financial_rows_by_stat_date_when_pub_date_missing(tmp_path):
    store = FactorStore(tmp_path)
    store.write_financial(
        "600000.XSHG",
        "growth",
        pd.DataFrame(
            {
                "statDate": ["2026-03-31", "2026-06-30"],
                "net_profit_growth_yoy": [0.08, 0.20],
            }
        ),
    )

    result = store.get_financial_tables(
        ["600000.XSHG"], "2026-04-01", tables=("growth",)
    )

    assert result["600000.XSHG"]["growth"]["net_profit_growth_yoy"].tolist() == [0.08]


def test_factor_store_prepare_financials_uses_client_for_missing_cache_only(tmp_path):
    class FinancialClient:
        def __init__(self):
            self.calls = []

        def query_financial_table(self, order_book_id, table, year, quarter):
            self.calls.append((order_book_id, table, year, quarter))
            return pd.DataFrame(
                {
                    "pubDate": [f"{year}-{quarter * 3:02d}-28"],
                    "roe": [0.1],
                }
            )

    client = FinancialClient()
    store = FactorStore(tmp_path, client=client)

    store.prepare_financials(
        ["600000.XSHG"], "2026-01-01", "2026-06-30", tables=("profit",)
    )
    store.prepare_financials(
        ["600000.XSHG"], "2026-01-01", "2026-06-30", tables=("profit",)
    )

    assert client.calls == [
        ("600000.XSHG", "profit", 2025, 1),
        ("600000.XSHG", "profit", 2025, 2),
        ("600000.XSHG", "profit", 2025, 3),
        ("600000.XSHG", "profit", 2025, 4),
        ("600000.XSHG", "profit", 2026, 1),
        ("600000.XSHG", "profit", 2026, 2),
    ]


def test_factor_store_prepare_financials_defaults_to_all_supported_tables(tmp_path):
    class FinancialClient:
        def __init__(self):
            self.tables = []

        def query_financial_table(self, order_book_id, table, year, quarter):
            self.tables.append(table)
            return pd.DataFrame(
                {
                    "pubDate": [f"{year}-{quarter * 3:02d}-28"],
                    "year": [year],
                    "quarter": [quarter],
                }
            )

    client = FinancialClient()
    store = FactorStore(tmp_path, client=client)

    store.prepare_financials(["600000.XSHG"], "2026-01-01", "2026-01-01")

    assert set(client.tables) == {"profit", "balance", "growth", "cash_flow", "dupont"}
