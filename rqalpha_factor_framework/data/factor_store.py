from pathlib import Path

import pandas as pd

from .baostock_client import rqalpha_to_baostock
from .cache import CsvCache

FINANCIAL_TABLES = ("profit", "balance", "growth", "cash_flow", "dupont", "operation")


class FactorStore:
    def __init__(self, cache_dir, client=None):
        self.cache_dir = Path(cache_dir)
        self.cache = CsvCache(self.cache_dir)
        self.client = client

    def get_daily(self, order_book_id, start_date, end_date):
        key = self._daily_key(order_book_id, start_date, end_date)
        path = self.cache.path_for("daily", key)
        if self.client is None and not path.exists():
            raise RuntimeError("data client is required when daily cache is missing")

        return self.cache.load_or_fetch(
            "daily",
            key,
            lambda: self.client.query_daily(order_book_id, start_date, end_date),
        )

    def write_financial(self, order_book_id, table, frame):
        path = self.cache.path_for(f"financial_{table}", order_book_id)
        frame.to_csv(path, index=False, encoding="utf-8-sig")

    def write_industry(self, date, frame):
        path = self.cache.path_for("industry", self._industry_key(date))
        frame.to_csv(path, index=False, encoding="utf-8-sig")

    def read_financial(self, order_book_id, table):
        path = self.cache.path_for(f"financial_{table}", order_book_id)
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    def read_industry(self, date):
        path = self.cache.path_for("industry", self._industry_key(date))
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
            rows.append(
                self._latest_financial_values(
                    frame, order_book_id, as_of_date, fields
                )
            )
            index.append(order_book_id)

        return pd.DataFrame(rows, index=index, columns=fields)

    def prepare_financials(self, order_book_ids, start_date, end_date, tables=None):
        if self.client is None:
            raise RuntimeError("data client is required when financial cache is missing")

        tables = tuple(tables or FINANCIAL_TABLES)
        year_quarters = _financial_year_quarters(start_date, end_date)

        # Use a shared baostock session when the client supports it,
        # otherwise fall back to per-query sessions (e.g. mock clients in tests).
        bs = None
        try:
            bs = self.client.login()
        except AttributeError:
            pass

        try:
            for order_book_id in order_book_ids:
                for table in tables:
                    self._update_financial_quarters(
                        order_book_id, table, year_quarters, bs=bs
                    )
        finally:
            if bs is not None:
                self.client.logout(bs)

    def prepare_industry(self, date):
        if self.client is None:
            raise RuntimeError("data client is required when industry cache is missing")
        key = self._industry_key(date)
        frame = self.client.query_stock_industry(code="", date=key)
        frame = _normalize_industry_frame(frame)
        self.write_industry(key, frame)
        return frame

    def get_industry_map(self, order_book_ids, date):
        frame = self.read_industry(date)
        if frame.empty and self.client is not None:
            frame = self.prepare_industry(date)
        if frame.empty:
            return {}
        frame = _normalize_industry_frame(frame)
        industry_column = _industry_column(frame)
        if industry_column is None or "order_book_id" not in frame.columns:
            return {}

        wanted = set(order_book_ids)
        industry_map = {}
        for _, row in frame.iterrows():
            order_book_id = row.get("order_book_id")
            industry = row.get(industry_column)
            if (
                order_book_id in wanted
                and pd.notna(industry)
                and str(industry).strip()
            ):
                industry_map[order_book_id] = str(industry)
        return industry_map

    def get_financial_tables(self, order_book_ids, date, tables=None):
        tables = tuple(tables or FINANCIAL_TABLES)
        as_of_date = pd.Timestamp(date)
        result = {}

        # Lazily build an in-memory cache to avoid repeated CSV reads across
        # rebalance cycles.  Financial data is historical — it does not change
        # between rebalances, only the as-of-date filter differs.
        if not hasattr(self, "_financial_mem_cache"):
            self._financial_mem_cache = {}

        for order_book_id in order_book_ids:
            stock_tables = {}
            for table in tables:
                cache_key = (order_book_id, table)
                frame = self._financial_mem_cache.get(cache_key)
                if frame is None:
                    frame = self.read_financial(order_book_id, table)
                    self._financial_mem_cache[cache_key] = frame
                stock_tables[table] = _filter_financial_by_pub_date(
                    frame, as_of_date
                )
            result[order_book_id] = stock_tables
        return result

    def _update_financial_quarters(self, order_book_id, table, year_quarters, bs=None):
        cached = self.read_financial(order_book_id, table)
        existing = _existing_quarters(cached)
        pieces = [cached] if not cached.empty else []

        for year, quarter in year_quarters:
            key = (int(year), int(quarter))
            if key in existing:
                continue
            if bs is not None:
                fetched = self.client.query_financial_table(
                    order_book_id, table, key[0], key[1], bs=bs
                )
            else:
                fetched = self.client.query_financial_table(
                    order_book_id, table, key[0], key[1]
                )
            frame = _normalize_financial_frame(fetched, order_book_id, key[0], key[1])
            if not frame.empty:
                pieces.append(frame)

        merged = _merge_financial_frames(pieces)
        self.write_financial(order_book_id, table, merged)
        return merged

    @staticmethod
    def _daily_key(order_book_id, start_date, end_date):
        return f"{order_book_id}_{start_date}_{end_date}"

    @staticmethod
    def _industry_key(date):
        return str(pd.Timestamp(date).date())

    @staticmethod
    def _latest_financial_values(frame, order_book_id, as_of_date, fields):
        values = {field: pd.NA for field in fields}
        if frame.empty or "pub_date" not in frame.columns:
            return values

        dated = frame.copy()
        if "order_book_id" in dated.columns:
            dated = dated[dated["order_book_id"] == order_book_id]
        if "code" in dated.columns:
            dated = dated[
                dated["code"].isin({order_book_id, rqalpha_to_baostock(order_book_id)})
            ]
        if dated.empty:
            return values

        dated["pub_date"] = pd.to_datetime(dated["pub_date"], errors="coerce")
        dated = dated[dated["pub_date"] <= as_of_date].sort_values("pub_date")
        if dated.empty:
            return values

        latest = dated.iloc[-1]
        for field in fields:
            if field in latest.index:
                values[field] = latest[field]
        return values


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


def _publication_date_series(frame):
    for column in ("pub_date", "pubDate", "date"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], errors="coerce")
    return pd.Series(pd.NaT, index=frame.index)


def _stat_date_series(frame):
    for column in ("stat_date", "statDate"):
        if column in frame.columns:
            return pd.to_datetime(frame[column], errors="coerce")
    return pd.Series(pd.NaT, index=frame.index)


def _filter_financial_by_pub_date(frame, as_of_date):
    if frame.empty:
        return frame
    dated = frame.copy()
    pub_dates = _publication_date_series(dated)
    if pub_dates.notna().any():
        dated = dated[pub_dates <= as_of_date]
    else:
        stat_dates = _stat_date_series(dated)
        if stat_dates.notna().any():
            dated = dated[stat_dates <= as_of_date]
    sort_columns = [
        column
        for column in ("pub_date", "pubDate", "stat_date", "statDate", "year", "quarter")
        if column in dated.columns
    ]
    if sort_columns:
        dated = dated.sort_values(sort_columns)
    return dated.reset_index(drop=True)


def _existing_quarters(frame):
    if frame.empty or "year" not in frame.columns or "quarter" not in frame.columns:
        return set()
    years = pd.to_numeric(frame["year"], errors="coerce")
    quarters = pd.to_numeric(frame["quarter"], errors="coerce")
    return {
        (int(year), int(quarter))
        for year, quarter in zip(years, quarters)
        if pd.notna(year) and pd.notna(quarter)
    }


def _normalize_financial_frame(frame, order_book_id, year=None, quarter=None):
    frame = pd.DataFrame() if frame is None else pd.DataFrame(frame).copy()
    if frame.empty:
        return frame
    if "order_book_id" not in frame.columns:
        frame["order_book_id"] = order_book_id
    if year is not None and "year" not in frame.columns:
        frame["year"] = int(year)
    if quarter is not None and "quarter" not in frame.columns:
        frame["quarter"] = int(quarter)
    return frame.reset_index(drop=True)


def _normalize_industry_frame(frame):
    frame = pd.DataFrame() if frame is None else pd.DataFrame(frame).copy()
    if frame.empty:
        return frame
    if "order_book_id" not in frame.columns and "code" in frame.columns:
        frame["order_book_id"] = frame["code"].map(_safe_baostock_to_rqalpha)
    return frame.reset_index(drop=True)


def _safe_baostock_to_rqalpha(code):
    if not isinstance(code, str) or "." not in code:
        return code
    exchange, symbol = code.split(".", 1)
    if exchange == "sh":
        return f"{symbol}.XSHG"
    if exchange == "sz":
        return f"{symbol}.XSHE"
    return code


def _industry_column(frame):
    for column in ("industry", "industry_name", "industryClassification"):
        if column in frame.columns:
            return column
    return None


def _merge_financial_frames(frames):
    non_empty = [
        pd.DataFrame(frame)
        for frame in frames
        if frame is not None and not pd.DataFrame(frame).empty
    ]
    if not non_empty:
        return pd.DataFrame()
    merged = pd.concat(non_empty, ignore_index=True, sort=False)
    subset = [
        column
        for column in ("order_book_id", "year", "quarter", "code")
        if column in merged.columns
    ]
    if subset:
        merged = merged.drop_duplicates(subset=subset, keep="last")
    sort_columns = [
        column
        for column in ("year", "quarter", "pub_date", "pubDate")
        if column in merged.columns
    ]
    if sort_columns:
        merged = merged.sort_values(sort_columns)
    return merged.reset_index(drop=True)
