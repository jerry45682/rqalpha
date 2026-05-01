from pathlib import Path

import pandas as pd


class BaostockCache(object):
    def __init__(self, cache_dir):
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, order_book_id, start_date, end_date, adjustflag):
        name = "{}_{}_{}_{}.csv".format(
            order_book_id.replace(".", "_"),
            start_date.replace("-", ""),
            end_date.replace("-", ""),
            adjustflag,
        )
        return self._cache_dir / name

    def read(self, order_book_id, start_date, end_date, adjustflag):
        path = self.path_for(order_book_id, start_date, end_date, adjustflag)
        if not path.exists():
            return None
        return pd.read_csv(path, dtype=str)

    def write(self, order_book_id, start_date, end_date, adjustflag, data):
        path = self.path_for(order_book_id, start_date, end_date, adjustflag)
        data.to_csv(path, index=False, encoding="utf-8")

    def load_or_fetch(self, order_book_id, start_date, end_date, adjustflag, fetcher):
        cached = self.read(order_book_id, start_date, end_date, adjustflag)
        if cached is not None:
            return cached
        data = fetcher(order_book_id, start_date, end_date, adjustflag)
        self.write(order_book_id, start_date, end_date, adjustflag, data)
        return data

