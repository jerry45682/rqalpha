from pathlib import Path

import pandas as pd

from .cache import CsvCache


class FactorStore:
    def __init__(self, cache_dir, client=None):
        self.cache_dir = Path(cache_dir)
        self.cache = CsvCache(self.cache_dir)
        self.client = client

    def get_daily(self, order_book_id, start_date, end_date):
        path = self.cache.path_for("daily", order_book_id)
        if self.client is None and not path.exists():
            raise RuntimeError("data client is required when daily cache is missing")

        return self.cache.load_or_fetch(
            "daily",
            order_book_id,
            lambda: self.client.query_daily(order_book_id, start_date, end_date),
        )

    def write_financial(self, order_book_id, table, frame):
        path = self.cache.path_for(f"financial_{table}", order_book_id)
        frame.to_csv(path, index=False, encoding="utf-8-sig")

    def read_financial(self, order_book_id, table):
        path = self.cache.path_for(f"financial_{table}", order_book_id)
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    def get_latest_financial(self, order_book_ids, table, date, fields):
        as_of_date = pd.Timestamp(date)
        rows = []
        index = []

        for order_book_id in order_book_ids:
            frame = self.read_financial(order_book_id, table)
            rows.append(self._latest_financial_values(frame, as_of_date, fields))
            index.append(order_book_id)

        return pd.DataFrame(rows, index=index, columns=fields)

    @staticmethod
    def _latest_financial_values(frame, as_of_date, fields):
        values = {field: pd.NA for field in fields}
        if frame.empty or "pub_date" not in frame.columns:
            return values

        dated = frame.copy()
        dated["pub_date"] = pd.to_datetime(dated["pub_date"], errors="coerce")
        dated = dated[dated["pub_date"] <= as_of_date].sort_values("pub_date")
        if dated.empty:
            return values

        latest = dated.iloc[-1]
        for field in fields:
            if field in latest.index:
                values[field] = latest[field]
        return values
