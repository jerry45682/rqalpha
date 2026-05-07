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

    def daily_path_for(self, order_book_id, adjustflag):
        directory = self._cache_dir / "daily"
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "{}_{}.csv".format(_safe_name(order_book_id), adjustflag)

    def read_daily(self, order_book_id, adjustflag):
        path = self.daily_path_for(order_book_id, adjustflag)
        if not path.exists():
            return None
        try:
            return pd.read_csv(path, dtype=str)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    def write_daily(self, order_book_id, adjustflag, data):
        path = self.daily_path_for(order_book_id, adjustflag)
        frame = _normalize_daily_frame(data)
        frame.to_csv(path, index=False, encoding="utf-8")

    def load_daily_range(
        self,
        order_book_id,
        start_date,
        end_date,
        adjustflag,
        fetcher,
        required_columns=None,
        trading_dates=None,
    ):
        cached = self.read_daily(order_book_id, adjustflag)
        if _covers_date_range(
            cached, start_date, end_date, trading_dates
        ) and _has_required_columns(cached, required_columns):
            return _slice_daily_range(cached, start_date, end_date)

        legacy = self.read(order_book_id, start_date, end_date, adjustflag)
        if _covers_date_range(
            legacy, start_date, end_date, trading_dates
        ) and _has_required_columns(legacy, required_columns):
            if cached is None or cached.empty:
                self.write_daily(order_book_id, adjustflag, legacy)
            return _slice_daily_range(legacy, start_date, end_date)

        if fetcher is None:
            if cached is None or not _has_required_columns(cached, required_columns):
                return None
            return _slice_daily_range(cached, start_date, end_date)

        if _has_required_columns(cached, required_columns):
            missing_ranges = _missing_daily_ranges(
                cached, start_date, end_date, trading_dates
            )
        else:
            missing_ranges = [(start_date, end_date)]
        pieces = [cached] if cached is not None and not cached.empty else []
        for missing_start, missing_end in missing_ranges:
            fetched = fetcher(order_book_id, missing_start, missing_end, adjustflag)
            if fetched is not None and not fetched.empty:
                pieces.append(fetched)

        if pieces:
            merged = _merge_daily_frames(pieces)
        else:
            merged = pd.DataFrame()
        self.write_daily(order_book_id, adjustflag, merged)
        stored = self.read_daily(order_book_id, adjustflag)
        return _slice_daily_range(stored, start_date, end_date)

    def financial_path_for(self, order_book_id, table):
        directory = self._cache_dir / "financial_{}".format(_safe_name(table))
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "{}.csv".format(_safe_name(order_book_id))

    def read_financial(self, order_book_id, table):
        path = self.financial_path_for(order_book_id, table)
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()

    def write_financial(self, order_book_id, table, data):
        path = self.financial_path_for(order_book_id, table)
        frame = _normalize_financial_frame(data, order_book_id)
        frame.to_csv(path, index=False, encoding="utf-8-sig")

    def update_financial_quarters(self, order_book_id, table, year_quarters, fetcher):
        cached = self.read_financial(order_book_id, table)
        existing = _existing_quarters(cached)
        pieces = [cached] if not cached.empty else []

        for year, quarter in year_quarters:
            key = (int(year), int(quarter))
            if key in existing:
                continue
            fetched = fetcher(order_book_id, table, key[0], key[1])
            frame = _normalize_financial_frame(fetched, order_book_id, key[0], key[1])
            if not frame.empty:
                pieces.append(frame)

        merged = _merge_financial_frames(pieces)
        self.write_financial(order_book_id, table, merged)
        return merged


def _safe_name(value):
    return (
        str(value)
        .replace(".", "_")
        .replace("/", "_")
        .replace("\\", "_")
        .replace(":", "_")
    )


def _normalize_daily_frame(data):
    frame = pd.DataFrame() if data is None else pd.DataFrame(data).copy()
    if frame.empty:
        return frame
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime(
            "%Y-%m-%d"
        )
        frame = frame.dropna(subset=["date"]).sort_values("date")
        frame = frame.drop_duplicates(subset=["date"], keep="last")
    return frame.reset_index(drop=True)


def _daily_dates(frame):
    if frame is None or frame.empty or "date" not in frame.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(frame["date"], errors="coerce").dropna()


def _covers_date_range(frame, start_date, end_date, trading_dates=None):
    return not _missing_daily_ranges(frame, start_date, end_date, trading_dates)


def _has_required_columns(frame, required_columns):
    if not required_columns:
        return True
    if frame is None:
        return False
    return set(required_columns).issubset(frame.columns)


def _missing_daily_ranges(frame, start_date, end_date, trading_dates=None):
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    expected = _expected_daily_dates(start, end, trading_dates)
    if expected.empty:
        return []

    dates = _daily_dates(frame)
    if dates.empty:
        return [(
            expected[0].strftime("%Y-%m-%d"),
            expected[-1].strftime("%Y-%m-%d"),
        )]

    available = set(dates.dt.normalize())
    ranges = []
    missing_start = None
    last_missing = None
    for current in expected:
        if current in available:
            if missing_start is not None:
                ranges.append((
                    missing_start.strftime("%Y-%m-%d"),
                    last_missing.strftime("%Y-%m-%d"),
                ))
                missing_start = None
                last_missing = None
            continue
        if missing_start is None:
            missing_start = current
        last_missing = current
    if missing_start is not None:
        ranges.append((
            missing_start.strftime("%Y-%m-%d"),
            last_missing.strftime("%Y-%m-%d"),
        ))
    return ranges


def _expected_daily_dates(start, end, trading_dates=None):
    if trading_dates is None:
        return pd.date_range(start, end, freq="B")

    dates = pd.to_datetime(pd.DatetimeIndex(trading_dates), errors="coerce")
    dates = pd.DatetimeIndex(dates.dropna()).normalize().unique().sort_values()
    left = dates.searchsorted(start)
    right = dates.searchsorted(end, side="right")
    return dates[left:right]


def _merge_daily_frames(frames):
    non_empty = [pd.DataFrame(frame) for frame in frames if frame is not None and not pd.DataFrame(frame).empty]
    if not non_empty:
        return pd.DataFrame()
    return _normalize_daily_frame(pd.concat(non_empty, ignore_index=True, sort=False))


def _slice_daily_range(frame, start_date, end_date):
    frame = _normalize_daily_frame(frame)
    if frame.empty or "date" not in frame.columns:
        return frame
    dates = pd.to_datetime(frame["date"], errors="coerce")
    mask = (dates >= pd.Timestamp(start_date)) & (dates <= pd.Timestamp(end_date))
    return frame.loc[mask].reset_index(drop=True)


def _normalize_financial_frame(data, order_book_id, year=None, quarter=None):
    frame = pd.DataFrame() if data is None else pd.DataFrame(data).copy()
    if frame.empty:
        return frame
    if "order_book_id" not in frame.columns:
        frame["order_book_id"] = order_book_id
    if year is not None and "year" not in frame.columns:
        frame["year"] = int(year)
    if quarter is not None and "quarter" not in frame.columns:
        frame["quarter"] = int(quarter)
    return frame.reset_index(drop=True)


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


def _merge_financial_frames(frames):
    non_empty = [pd.DataFrame(frame) for frame in frames if frame is not None and not pd.DataFrame(frame).empty]
    if not non_empty:
        return pd.DataFrame()
    merged = pd.concat(non_empty, ignore_index=True, sort=False)
    subset = [column for column in ("order_book_id", "year", "quarter", "code") if column in merged.columns]
    if subset:
        merged = merged.drop_duplicates(subset=subset, keep="last")
    sort_columns = [column for column in ("year", "quarter", "pubDate", "pub_date") if column in merged.columns]
    if sort_columns:
        merged = merged.sort_values(sort_columns)
    return merged.reset_index(drop=True)

