import inspect
from types import SimpleNamespace

import pandas as pd
import pytest

from rqalpha_factor_framework.data.cache import CsvCache
from rqalpha_factor_framework.data.factor_store import FactorStore
from rqalpha_factor_framework.data.baostock_client import BaostockClient


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


def test_baostock_client_query_financial_table_supports_operation(monkeypatch):
    from rqalpha_factor_framework.data import baostock_client

    captured = {}

    class FakeResult:
        error_code = "0"
        fields = [
            "code",
            "pubDate",
            "NRTurnRatio",
            "INVTurnRatio",
            "AssetTurnRatio",
        ]

        def __init__(self):
            self._rows = iter(
                [["sh.600000", "2026-04-30", "7.1", "5.2", "0.8"]]
            )
            self._current = None

        def next(self):
            try:
                self._current = next(self._rows)
                return True
            except StopIteration:
                return False

        def get_row_data(self):
            return self._current

    class FakeSession:
        def __enter__(self):
            def query_operation_data(**kwargs):
                captured["kwargs"] = kwargs
                return FakeResult()

            return SimpleNamespace(query_operation_data=query_operation_data)

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(baostock_client, "baostock_session", lambda: FakeSession())

    result = BaostockClient().query_financial_table(
        "600000.XSHG", "operation", 2026, 1
    )

    assert captured["kwargs"] == {"code": "sh.600000", "year": 2026, "quarter": 1}
    assert result.loc[0, "receivables_turnover"] == "7.1"
    assert result.loc[0, "inventory_turnover"] == "5.2"
    assert result.loc[0, "asset_turnover"] == "0.8"


def test_baostock_client_query_stock_industry_maps_codes(monkeypatch):
    from rqalpha_factor_framework.data import baostock_client

    captured = {}

    class FakeResult:
        error_code = "0"
        fields = ["code", "code_name", "industry", "industryClassification"]

        def __init__(self):
            self._rows = iter(
                [
                    ["sh.600000", "PF Bank", "银行", "申万一级"],
                    ["sz.000001", "PA Bank", "银行", "申万一级"],
                ]
            )
            self._current = None

        def next(self):
            try:
                self._current = next(self._rows)
                return True
            except StopIteration:
                return False

        def get_row_data(self):
            return self._current

    class FakeSession:
        def __enter__(self):
            def query_stock_industry(**kwargs):
                captured["kwargs"] = kwargs
                return FakeResult()

            return SimpleNamespace(query_stock_industry=query_stock_industry)

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(baostock_client, "baostock_session", lambda: FakeSession())

    result = BaostockClient().query_stock_industry(date="2026-01-31")

    assert captured["kwargs"] == {"code": "", "date": "2026-01-31"}
    assert result["order_book_id"].tolist() == ["600000.XSHG", "000001.XSHE"]


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

    assert set(client.tables) == {
        "profit",
        "balance",
        "growth",
        "cash_flow",
        "dupont",
        "operation",
    }


def test_factor_store_get_industry_map_fetches_and_reuses_cache(tmp_path):
    class IndustryClient:
        def __init__(self):
            self.calls = []

        def query_stock_industry(self, code="", date=""):
            self.calls.append((code, date))
            return pd.DataFrame(
                {
                    "code": ["sh.600000", "sz.000001"],
                    "order_book_id": ["600000.XSHG", "000001.XSHE"],
                    "industry": ["bank", "broker"],
                }
            )

    client = IndustryClient()
    store = FactorStore(tmp_path, client=client)

    first = store.get_industry_map(
        ["600000.XSHG", "000001.XSHE", "000002.XSHE"], "2026-01-31"
    )
    second = store.get_industry_map(["600000.XSHG"], "2026-01-31")

    assert client.calls == [("", "2026-01-31")]
    assert first == {"600000.XSHG": "bank", "000001.XSHE": "broker"}
    assert second == {"600000.XSHG": "bank"}
