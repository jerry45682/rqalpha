import pandas as pd
from pandas.api.types import is_datetime64_any_dtype
from rqalpha.apis import (
    get_positions,
    history_bars,
    index_components,
    logger,
    order_target_percent,
)
from rqalpha.environment import Environment

from rqalpha_factor_framework.config import load_config
from rqalpha_factor_framework.data import BaostockClient, FactorStore
from rqalpha_factor_framework.factors import FACTOR_METADATA
from rqalpha_factor_framework.factors.growth import calculate_growth_factors
from rqalpha_factor_framework.factors.liquidity import calculate_liquidity_factors
from rqalpha_factor_framework.factors.momentum import calculate_momentum_factors
from rqalpha_factor_framework.factors.quality import calculate_quality_factors
from rqalpha_factor_framework.factors.reversal import calculate_reversal_factors
from rqalpha_factor_framework.factors.risk import calculate_risk_factors
from rqalpha_factor_framework.factors.technical import calculate_technical_factors
from rqalpha_factor_framework.factors.valuation import calculate_valuation_factors
from rqalpha_factor_framework.filters import filter_by_avg_amount, filter_stocks
from rqalpha_factor_framework.portfolio import (
    apply_industry_weight_cap,
    apply_stock_weight_cap,
    build_equal_weight_targets,
    build_score_weight_targets,
    market_timing_exposure,
)
from rqalpha_factor_framework.scoring import build_factor_scores, preprocess_factors


HISTORY_BAR_COUNT = 130
HISTORY_FIELDS = [
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "preclose",
    "volume",
    "amount",
    "turn",
    "tradestatus",
    "pctChg",
    "peTTM",
    "pbMRQ",
    "psTTM",
    "pcfNcfTTM",
    "isST",
]
FINANCIAL_TABLES = ("profit", "balance", "growth", "cash_flow", "dupont", "operation")


def init(context):
    from rqalpha.api import market_open, scheduler

    config_path = getattr(context, "factor_config_path", None)
    config = load_config(config_path)
    context.factor_config = config

    rebalance_config = config["rebalance"]
    frequency = str(rebalance_config.get("frequency", "monthly")).lower()
    tradingday = int(rebalance_config["tradingday"])
    time_rule = market_open(minute=1)
    if frequency == "weekly":
        scheduler.run_weekly(rebalance, tradingday=tradingday, time_rule=time_rule)
    elif frequency == "monthly":
        scheduler.run_monthly(rebalance, tradingday=tradingday, time_rule=time_rule)
    else:
        raise ValueError("unsupported rebalance frequency: {}".format(frequency))
    logger.info("factor framework strategy initialized")


def _resolve_stock_pool(config, date=None):
    stock_pool = config["stock_pool"]
    symbols = stock_pool.get("symbols") or []
    if symbols:
        return _filter_stock_pool_to_bundle(list(symbols))
    return _filter_stock_pool_to_bundle(
        list(_resolve_index_components(stock_pool["index"], date=date))
    )


def _resolve_index_components(index_order_book_id, date=None):
    try:
        return index_components(index_order_book_id)
    except RuntimeError as exc:
        if "rqdatac is not initialized" not in str(exc):
            raise
        logger.warning(
            "rqdatac is not initialized; using baostock index components for {}".format(
                index_order_book_id
            )
        )
        return _fetch_baostock_index_components(index_order_book_id, date=date)


def _fetch_baostock_index_components(index_order_book_id, date=None):
    from rqalpha.mod.rqalpha_mod_baostock.data_source import (
        fetch_baostock_index_components,
    )

    return fetch_baostock_index_components(index_order_book_id, date=date)


def _filter_stock_pool_to_bundle(symbols):
    try:
        instruments = Environment.get_instance().data_proxy.instruments(symbols)
    except Exception:
        return symbols

    valid = {
        instrument.order_book_id
        for instrument in instruments
        if getattr(instrument, "order_book_id", None)
    }
    filtered = [symbol for symbol in symbols if symbol in valid]
    skipped = [symbol for symbol in symbols if symbol not in valid]
    if skipped:
        logger.warning(
            "filtered {} stock pool symbols missing from bundle: {}".format(
                len(skipped), skipped[:10]
            )
        )
    return filtered


def _position_order_book_id(position):
    if isinstance(position, dict):
        return position.get("order_book_id")
    return getattr(position, "order_book_id", None)


def _position_quantity(position):
    if isinstance(position, dict):
        quantity = position.get("quantity", 0)
    else:
        quantity = getattr(position, "quantity", 0)
    try:
        return float(quantity)
    except (TypeError, ValueError):
        return 0.0


def _current_positions():
    stocks = []
    for position in get_positions():
        order_book_id = _position_order_book_id(position)
        if order_book_id and _position_quantity(position) > 0:
            stocks.append(order_book_id)
    return stocks


def _order_to_targets(targets):
    current = set(_current_positions())
    target_stocks = set(targets)

    for order_book_id in sorted(current - target_stocks):
        logger.info("sell non-target stock: {}".format(order_book_id))
        order_target_percent(order_book_id, 0)

    for order_book_id, weight in targets.items():
        logger.info(
            "order target percent: {} {:.6f}".format(order_book_id, float(weight))
        )
        order_target_percent(order_book_id, float(weight))


def _parse_datetime_value(value):
    if pd.isna(value):
        return pd.NaT

    if isinstance(value, pd.Timestamp):
        return value

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not pd.notna(value):
            return pd.NaT
        text = str(int(value)) if float(value).is_integer() else str(value)
    else:
        text = str(value)

    if text.isdigit():
        if len(text) == 8:
            return pd.to_datetime(text, format="%Y%m%d", errors="coerce")
        if len(text) == 14:
            return pd.to_datetime(text, format="%Y%m%d%H%M%S", errors="coerce")

    return pd.to_datetime(value, errors="coerce")


def _parse_datetime_series(values):
    series = pd.Series(values)
    if is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")
    return series.map(_parse_datetime_value)


def _bars_to_frame(bars, order_book_id):
    if bars is None:
        return pd.DataFrame()
    if isinstance(bars, pd.DataFrame):
        frame = bars.copy()
    else:
        frame = pd.DataFrame(bars)
    if frame.empty:
        return frame

    if "date" not in frame.columns and "datetime" in frame.columns:
        frame["date"] = _parse_datetime_series(frame["datetime"])
    frame["order_book_id"] = order_book_id
    return frame


def _frame_as_of(frame, as_of_date, max_count=None):
    if frame.empty or as_of_date is None or "date" not in frame.columns:
        return frame.tail(max_count) if max_count is not None else frame

    dates = _parse_datetime_series(frame["date"])
    as_of = pd.Timestamp(as_of_date).normalize()
    filtered = frame.loc[dates.dt.normalize() <= as_of]
    if max_count is not None:
        filtered = filtered.tail(max_count)
    return filtered.reset_index(drop=True)


def _fetch_daily_data(stock_pool, as_of_date=None):
    daily_data = {}
    for order_book_id in stock_pool:
        try:
            bars = history_bars(
                order_book_id,
                HISTORY_BAR_COUNT + 1,
                "1d",
                HISTORY_FIELDS,
                skip_suspended=False,
                include_now=False,
                adjust_type="pre",
            )
        except Exception as exc:  # pragma: no cover - depends on live data backend
            logger.warning(
                "failed to fetch history bars for {}: {}".format(order_book_id, exc)
            )
            continue

        frame = _bars_to_frame(bars, order_book_id)
        frame = _frame_as_of(frame, as_of_date, max_count=HISTORY_BAR_COUNT)
        if frame.empty:
            logger.warning("history bars empty for {}".format(order_book_id))
            continue
        daily_data[order_book_id] = frame
    return daily_data


def _context_datetime(context):
    for name in ("now", "current_dt", "trading_dt"):
        value = getattr(context, name, None)
        if value is not None:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.notna(parsed):
                return parsed

    parsed = _environment_datetime()
    if pd.notna(parsed):
        return parsed
    raise ValueError("trading date is unavailable from context or RQAlpha environment")


def _environment_datetime():
    try:
        env = Environment.get_instance()
    except RuntimeError:
        return pd.NaT

    for name in ("trading_dt", "calendar_dt"):
        value = getattr(env, name, None)
        if value is not None:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.notna(parsed):
                return parsed
    return pd.NaT


def _previous_trading_datetime(context):
    try:
        current = _context_datetime(context)
    except ValueError:
        return None
    try:
        env = Environment.get_instance()
        previous = env.data_proxy.get_previous_trading_date(current.date())
        parsed = pd.to_datetime(previous, errors="coerce")
        if pd.notna(parsed):
            return parsed.normalize()
    except Exception:
        pass
    return (current.normalize() - pd.offsets.BDay(1)).normalize()


def _filter_financial_table_as_of(frame, as_of_date):
    from rqalpha_factor_framework.data.factor_store import _filter_financial_by_pub_date

    if frame is None:
        return pd.DataFrame()
    if as_of_date is None:
        return pd.DataFrame(frame)
    return _filter_financial_by_pub_date(pd.DataFrame(frame), pd.Timestamp(as_of_date))


def _resolve_financial_data(context, stock_pool, as_of_date=None):
    supplied = getattr(context, "financial_data", None)
    stock_pool = list(stock_pool)
    data_config = getattr(context, "factor_config", {}).get("data", {})
    financial_tables = list(data_config.get("financial_tables") or FINANCIAL_TABLES)
    if as_of_date is None:
        as_of_date = _previous_trading_datetime(context)
    if isinstance(supplied, dict) and supplied:
        financial_data = {}
        for order_book_id in stock_pool:
            tables = supplied.get(order_book_id, {}) or {}
            financial_data[order_book_id] = {
                table: _filter_financial_table_as_of(
                    tables.get(table, pd.DataFrame()), as_of_date
                )
                for table in financial_tables
            }
        return financial_data

    cache_dir = data_config.get("cache_dir")
    if cache_dir:
        client = None
        if data_config.get("runtime_fetch_financial", False):
            client = BaostockClient(adjustflag=data_config.get("adjustflag", "2"))
        store = FactorStore(cache_dir, client=client)
        start_date = data_config.get("start_date")
        end_date = data_config.get("end_date") or as_of_date
        if client is not None:
            try:
                store.prepare_financials(
                    stock_pool,
                    start_date or as_of_date,
                    end_date,
                    tables=financial_tables,
                )
            except Exception as exc:  # pragma: no cover - depends on live baostock
                logger.warning("failed to update baostock financial cache: {}".format(exc))
        if as_of_date is None:
            as_of_date = _context_datetime(context)
        return store.get_financial_tables(stock_pool, as_of_date, tables=financial_tables)

    financial_data = {}
    for order_book_id in stock_pool:
        tables = {}
        if isinstance(supplied, dict):
            tables = supplied.get(order_book_id, {}) or {}
        financial_data[order_book_id] = {
            table: tables.get(table, pd.DataFrame()) for table in financial_tables
        }
    return financial_data


def _resolve_industry_map(context, stock_pool, as_of_date=None):
    supplied = getattr(context, "industry_map", None)
    stock_pool = list(stock_pool)
    if isinstance(supplied, dict) and supplied:
        return {
            order_book_id: supplied[order_book_id]
            for order_book_id in stock_pool
            if order_book_id in supplied
        }

    data_config = getattr(context, "factor_config", {}).get("data", {})
    cache_dir = data_config.get("cache_dir")
    if not cache_dir:
        return {}

    client = None
    if data_config.get("runtime_fetch_industry", True):
        client = BaostockClient(adjustflag=data_config.get("adjustflag", "2"))
    store = FactorStore(cache_dir, client=client)
    if as_of_date is None:
        as_of_date = _previous_trading_datetime(context)
    try:
        return store.get_industry_map(stock_pool, as_of_date)
    except Exception as exc:  # pragma: no cover - depends on live baostock
        logger.warning("failed to update baostock industry cache: {}".format(exc))
        return {}


def _calculate_raw_factors(daily_data, financial_data):
    factor_frames = [
        calculate_valuation_factors(daily_data),
        calculate_quality_factors(financial_data),
        calculate_growth_factors(financial_data),
        calculate_momentum_factors(daily_data),
        calculate_reversal_factors(daily_data),
        calculate_risk_factors(daily_data),
        calculate_liquidity_factors(daily_data),
        calculate_technical_factors(daily_data),
    ]
    raw_factors = pd.concat(factor_frames, axis=1)
    return raw_factors.loc[:, ~raw_factors.columns.duplicated()]


def _latest_filter_fields(daily_data):
    rows = {}
    for order_book_id, frame in daily_data.items():
        if frame.empty:
            rows[order_book_id] = {
                "is_st": 0,
                "listed_days": 9999,
                "tradestatus": 1,
            }
            continue

        data = frame.sort_values("date") if "date" in frame.columns else frame
        latest = data.iloc[-1]
        rows[order_book_id] = {
            "is_st": latest.get("is_st", latest.get("isST", 0)),
            "listed_days": latest.get("listed_days", 9999),
            "tradestatus": latest.get("tradestatus", 1),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def _apply_filters(raw_factors, daily_data, config):
    filtered = raw_factors.join(_latest_filter_fields(daily_data), how="left")
    filtered["is_st"] = filtered["is_st"].fillna(0)
    filtered["listed_days"] = filtered["listed_days"].fillna(9999)
    filtered["tradestatus"] = filtered["tradestatus"].fillna(1)

    filters_config = config.get("filters", {})
    if filters_config.get("exclude_suspended", False):
        tradestatus = pd.to_numeric(filtered["tradestatus"], errors="coerce").fillna(1)
        filtered = filtered[tradestatus == 1]

    filtered = filter_stocks(
        filtered,
        min_listed_days=filters_config.get("min_listed_days", 180),
        require_positive_pe_pb=filters_config.get("require_positive_pe_pb", True),
        exclude_st=filters_config.get("exclude_st", True),
    )
    return filter_by_avg_amount(
        filtered,
        filters_config.get("min_avg_amount_20", 0),
    )


def _close_series_from_bars(bars, as_of_date=None, max_count=None):
    if bars is None:
        return pd.Series(dtype="float64")
    if isinstance(bars, pd.DataFrame):
        frame = bars.copy()
    else:
        frame = pd.DataFrame(bars)
    if "date" not in frame.columns and "datetime" in frame.columns:
        frame["date"] = _parse_datetime_series(frame["datetime"])
    frame = _frame_as_of(frame, as_of_date, max_count=max_count)
    if "close" in frame.columns:
        return pd.to_numeric(frame["close"], errors="coerce").dropna()
    if frame.shape[1] == 1:
        return pd.to_numeric(frame.iloc[:, 0], errors="coerce").dropna()
    return pd.to_numeric(pd.Series(bars), errors="coerce").dropna()


def _resolve_total_exposure(config, as_of_date=None):
    risk_config = config.get("risk", {})
    timing_config = risk_config.get("market_timing", {})
    full_exposure = timing_config.get("full_exposure", 1.0)

    if not timing_config.get("enabled", False):
        return float(full_exposure)

    try:
        bars = history_bars(
            timing_config["index"],
            251,
            "1d",
            ["datetime", "close"],
            skip_suspended=False,
            include_now=False,
            adjust_type="pre",
        )
    except Exception as exc:  # pragma: no cover - depends on live data backend
        logger.warning(
            "failed to fetch market timing index bars; using full exposure: {}".format(
                exc
            )
        )
        return float(full_exposure)

    close = _close_series_from_bars(bars, as_of_date=as_of_date, max_count=250)
    if len(close) < 120:
        logger.warning("market timing data is insufficient; using full exposure")
        return float(full_exposure)

    return market_timing_exposure(
        close,
        full_exposure=full_exposure,
        ma120_exposure=timing_config.get("ma120_exposure", full_exposure),
        ma250_exposure=timing_config.get("ma250_exposure", full_exposure),
    )


def _build_targets(
    scored, current_positions, config, industry_map=None, as_of_date=None
):
    portfolio_config = config["portfolio"]
    risk_config = config.get("risk", {})
    holding_count = portfolio_config["holding_count"]
    if as_of_date is None:
        total_exposure = _resolve_total_exposure(config)
    else:
        total_exposure = _resolve_total_exposure(config, as_of_date=as_of_date)

    if portfolio_config.get("weighting") == "score":
        targets = build_score_weight_targets(
            scored,
            holding_count=holding_count,
            total_exposure=total_exposure,
        )
    else:
        targets = build_equal_weight_targets(
            scored,
            current_positions=current_positions,
            holding_count=holding_count,
            buffer_count=portfolio_config["buffer_count"],
            total_exposure=total_exposure,
        )

    if "max_stock_weight" in risk_config:
        targets = apply_stock_weight_cap(targets, risk_config["max_stock_weight"])
    if "max_industry_weight" in risk_config:
        if industry_map:
            targets = apply_industry_weight_cap(
                targets,
                industry_map,
                risk_config["max_industry_weight"],
            )
        else:
            logger.warning("industry map unavailable; skipping industry weight cap")
    return targets


def _score_value(score_row, column):
    value = score_row.get(column, 0.0)
    if pd.isna(value):
        return 0.0
    return float(value)


def _enabled_factor_columns(frame, config):
    enabled_categories = config.get("factors", {}).get("enabled_categories")
    if enabled_categories is None:
        enabled_categories = {meta.category for meta in FACTOR_METADATA.values()}
    else:
        enabled_categories = set(enabled_categories)

    return [
        column
        for column in frame.columns
        if column in FACTOR_METADATA
        and FACTOR_METADATA[column].category in enabled_categories
    ]


def _factor_columns_with_min_coverage(frame, factor_columns, min_coverage=0.0):
    if not factor_columns:
        return []
    if min_coverage is None:
        min_coverage = 0.0
    min_coverage = float(min_coverage)
    retained = []
    for column in factor_columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().mean() >= min_coverage:
            retained.append(column)
    return retained


def _factor_weights_for_columns(factor_weights, factor_columns):
    if not factor_weights:
        return None

    retained = set(factor_columns)
    pruned = {}
    for category, weights in factor_weights.items():
        category_weights = {
            factor: weight for factor, weight in weights.items() if factor in retained
        }
        if category_weights:
            pruned[category] = category_weights
    return pruned or None


def _ordered_enabled_categories(config):
    ordered_categories = []
    for meta in FACTOR_METADATA.values():
        if meta.category not in ordered_categories:
            ordered_categories.append(meta.category)

    enabled_categories = config.get("factors", {}).get("enabled_categories")
    if enabled_categories is None:
        return ordered_categories

    enabled_categories = set(enabled_categories)
    return [
        category for category in ordered_categories if category in enabled_categories
    ]


def _score_log_message(order_book_id, score_row, config):
    parts = [
        "target factor score: {} total={:.6f}".format(
            order_book_id,
            _score_value(score_row, "score"),
        )
    ]
    for category in _ordered_enabled_categories(config):
        score_column = f"{category}_score"
        if score_column in score_row.index:
            parts.append(
                "{}={:.6f}".format(
                    category,
                    _score_value(score_row, score_column),
                )
            )
    return " ".join(parts)


def rebalance(context, bar_dict):
    config = context.factor_config
    signal_dt = _previous_trading_datetime(context)
    stock_pool = _resolve_stock_pool(
        config, date=signal_dt.date() if signal_dt is not None else None
    )
    logger.info("stock pool size: {}".format(len(stock_pool)))

    daily_data = _fetch_daily_data(stock_pool, as_of_date=signal_dt)
    if not daily_data:
        logger.warning("no daily data available; clearing non-target positions")
        _order_to_targets({})
        return

    financial_data = _resolve_financial_data(
        context, daily_data.keys(), as_of_date=signal_dt
    )
    raw_factors = _calculate_raw_factors(daily_data, financial_data)
    filtered_factors = _apply_filters(raw_factors, daily_data, config)
    if filtered_factors.empty:
        logger.warning("no stocks passed factor filters; clearing non-target positions")
        _order_to_targets({})
        return

    factor_columns = _enabled_factor_columns(filtered_factors, config)
    factor_columns = _factor_columns_with_min_coverage(
        filtered_factors,
        factor_columns,
        min_coverage=config.get("scoring", {}).get("min_factor_coverage", 0.0),
    )
    if not factor_columns:
        logger.warning(
            "no enabled factor columns passed coverage filter; "
            "clearing non-target positions"
        )
        _order_to_targets({})
        return
    processed = preprocess_factors(
        filtered_factors[factor_columns],
        FACTOR_METADATA,
        winsorize_quantiles=tuple(
            config.get("scoring", {}).get("winsorize_quantiles", (0.01, 0.99))
        ),
        missing=config.get("scoring", {}).get("missing", "median"),
    )
    factor_weights = _factor_weights_for_columns(
        config["factors"].get("factor_weights"),
        factor_columns,
    )
    scored = build_factor_scores(
        processed,
        FACTOR_METADATA,
        config["factors"]["category_weights"],
        factor_weights=factor_weights,
    )
    industry_map = _resolve_industry_map(context, scored.index, as_of_date=signal_dt)
    targets = _build_targets(
        scored,
        _current_positions(),
        config,
        industry_map=industry_map,
        as_of_date=signal_dt,
    )

    logger.info("target stocks: {}".format(list(targets)))
    for order_book_id in targets:
        score_row = scored.loc[order_book_id]
        logger.info(_score_log_message(order_book_id, score_row, config))
    _order_to_targets(targets)


def handle_bar(context, bar_dict):
    pass
