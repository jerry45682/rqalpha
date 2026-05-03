import pandas as pd

from rqalpha_factor_framework.data.cache import CsvCache
from rqalpha_factor_framework.data.factor_store import FactorStore


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
