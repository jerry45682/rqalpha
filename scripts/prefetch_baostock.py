"""
Standalone baostock prefetch script — warms the daily + financial cache
without running a full backtest.

Usage:
    # Prefetch HS300 stocks (default)
    .venv/Scripts/python.exe scripts/prefetch_baostock.py

    # Prefetch with custom config
    .venv/Scripts/python.exe scripts/prefetch_baostock.py -c rqalpha_factor_framework/config/multi_factor_config_aggressive.yaml

    # Prefetch specific stocks
    .venv/Scripts/python.exe scripts/prefetch_baostock.py -s 600000.XSHG,000001.XSHE,600519.XSHG

    # Parallel prefetch with 4 workers
    .venv/Scripts/python.exe scripts/prefetch_baostock.py -w 4
"""

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def resolve_symbols(index="000300.XSHG", symbols=None, bundle_path="bundle/bundle",
                    all_stocks=False):
    """Resolve stock pool from index, explicit list, or all A-shares."""
    from rqalpha.data.base_data_source.data_source import BaseDataSource

    stock_list = _as_list(symbols) if symbols else []

    if all_stocks:
        print("Fetching all A-share stocks from baostock...")
        from rqalpha.mod.rqalpha_mod_baostock.data_source import (
            baostock_session, _result_to_frame,
            baostock_to_rqalpha,
        )
        with baostock_session() as bs:
            result = bs.query_all_stock(day="2024-01-02")
            frame = _result_to_frame(result, "query_all_stock failed")
            if "code" in frame.columns:
                stock_list = [baostock_to_rqalpha(c) for c in frame["code"].dropna()]
            else:
                stock_list = []
        print(f"  got {len(stock_list)} stocks")
    elif not stock_list and index:
        print(f"Resolving {index} components...")
        from rqalpha.mod.rqalpha_mod_baostock.data_source import (
            fetch_baostock_index_components,
        )
        try:
            stock_list = fetch_baostock_index_components(index)
            print(f"  got {len(stock_list)} symbols")
        except (ValueError, AttributeError) as e:
            print(f"  ERROR: {e}")
            print("  Hint: this index is not supported by baostock API.")
            print("  Use --all for all stocks, or -s to provide symbols manually.")
            return []

    if not stock_list:
        print("ERROR: no symbols to prefetch")
        return []

    # Filter against bundle
    base_ds = BaseDataSource(SimpleNamespace(data_bundle_path=bundle_path))
    try:
        instruments = base_ds.get_instruments(stock_list)
    except Exception:
        print("Warning: could not validate symbols against bundle, using all")
        return stock_list

    valid = {
        instrument.order_book_id
        for instrument in instruments
        if getattr(instrument, "order_book_id", None)
    }
    filtered = [s for s in stock_list if s in valid]
    skipped = [s for s in stock_list if s not in valid]
    if skipped:
        print(f"  filtered {len(skipped)} symbols not in bundle")
    print(f"  {len(filtered)} valid symbols to prefetch")
    return filtered


def main():
    parser = argparse.ArgumentParser(description="Baostock cache prefetch")
    parser.add_argument("-c", "--config", help="Factor config YAML (reads data section)")
    parser.add_argument("-s", "--symbols", help="Comma-separated stock list")
    parser.add_argument("-i", "--index", default="000300.XSHG", help="Index for stock pool")
    parser.add_argument("--all", action="store_true", help="Prefetch ALL A-share stocks")
    parser.add_argument("-w", "--workers", type=int, default=1, help="Prefetch workers (1=serial, 2-8=parallel)")
    parser.add_argument("--start-date", default="2024-01-01", help="Data start date")
    parser.add_argument("--end-date", default="2025-12-31", help="Data end date")
    parser.add_argument("--cache-dir", default=".rqalpha_factor_cache", help="Cache directory")
    parser.add_argument("--bundle-path", default="bundle/bundle", help="RQAlpha bundle path")
    parser.add_argument("--tables", default="profit,balance,growth,cash_flow,dupont,operation",
                        help="Financial tables to prefetch")
    args = parser.parse_args()

    # Load config overrides from YAML if provided
    if args.config:
        from rqalpha_factor_framework.config import load_config
        cfg = load_config(args.config)
        data_cfg = cfg.get("data", {})
        if not args.symbols:
            stock_cfg = cfg.get("stock_pool", {})
            args.index = stock_cfg.get("index", args.index)
        args.start_date = data_cfg.get("start_date", args.start_date)
        args.cache_dir = data_cfg.get("cache_dir", args.cache_dir)
        if data_cfg.get("prefetch_workers"):
            args.workers = data_cfg["prefetch_workers"]

    # Resolve symbols
    symbols = resolve_symbols(
        index=args.index,
        symbols=args.symbols.split(",") if args.symbols else None,
        bundle_path=args.bundle_path,
        all_stocks=args.all,
    )
    if not symbols:
        return 1

    tables = [t.strip() for t in args.tables.split(",") if t.strip()]

    # Build data source
    from rqalpha.mod.rqalpha_mod_baostock.data_source import BaostockDataSource

    base_config = SimpleNamespace(
        end_date=args.end_date,
        data_bundle_path=args.bundle_path,
    )
    mod_config = SimpleNamespace(
        cache_dir=args.cache_dir,
        adjustflag="2",
        start_date=args.start_date,
        end_date=args.end_date,
        prefetch=True,
        prefetch_workers=args.workers,
        symbols=[],
        index_symbols=[],
        runtime_fetch=True,
        financial_tables=tables,
    )

    ds = BaostockDataSource(base_config, mod_config)
    print(f"\nStarting prefetch: {len(symbols)} stocks, {len(tables)} tables, "
          f"{args.workers} workers")
    print(f"Date range: {args.start_date} ~ {args.end_date}")
    print()

    import time
    t0 = time.perf_counter()
    ds.prepare_data(symbols)
    elapsed = time.perf_counter() - t0

    print(f"\nPrefetch complete in {elapsed:.1f}s")


if __name__ == "__main__":
    raise SystemExit(main())
