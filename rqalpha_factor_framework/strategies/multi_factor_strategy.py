import pandas as pd
from pandas.api.types import is_datetime64_any_dtype
from rqalpha.apis import (
    get_positions,
    history_bars,
    index_components,
    logger,
    order_target_percent,
)

from rqalpha_factor_framework.config import load_config
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
    apply_stock_weight_cap,
    build_equal_weight_targets,
    build_score_weight_targets,
    market_timing_exposure,
)
from rqalpha_factor_framework.scoring import build_factor_scores, preprocess_factors


HISTORY_BAR_COUNT = 130
HISTORY_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "turn",
    "tradestatus",
    "peTTM",
    "pbMRQ",
    "isST",
]
FINANCIAL_TABLES = ("profit", "balance", "growth")


def init(context):
    from rqalpha.api import market_open, scheduler

    config_path = getattr(context, "factor_config_path", None)
    config = load_config(config_path)
    context.factor_config = config

    scheduler.run_monthly(
        rebalance,
        tradingday=int(config["rebalance"]["tradingday"]),
        time_rule=market_open(minute=1),
    )
    logger.info("factor framework strategy initialized")


def _resolve_stock_pool(config):
    stock_pool = config["stock_pool"]
    symbols = stock_pool.get("symbols") or []
    if symbols:
        return list(symbols)
    return list(index_components(stock_pool["index"]))


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


def _fetch_daily_data(stock_pool):
    daily_data = {}
    for order_book_id in stock_pool:
        try:
            bars = history_bars(
                order_book_id,
                HISTORY_BAR_COUNT,
                "1d",
                HISTORY_FIELDS,
                skip_suspended=False,
                include_now=True,
                adjust_type="pre",
            )
        except Exception as exc:  # pragma: no cover - depends on live data backend
            logger.warning(
                "failed to fetch history bars for {}: {}".format(order_book_id, exc)
            )
            continue

        frame = _bars_to_frame(bars, order_book_id)
        if frame.empty:
            logger.warning("history bars empty for {}".format(order_book_id))
            continue
        daily_data[order_book_id] = frame
    return daily_data


def _resolve_financial_data(context, stock_pool):
    supplied = getattr(context, "financial_data", None)
    financial_data = {}
    for order_book_id in stock_pool:
        tables = {}
        if isinstance(supplied, dict):
            tables = supplied.get(order_book_id, {}) or {}
        financial_data[order_book_id] = {
            table: tables.get(table, pd.DataFrame()) for table in FINANCIAL_TABLES
        }
    return financial_data


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


def _close_series_from_bars(bars):
    if bars is None:
        return pd.Series(dtype="float64")
    if isinstance(bars, pd.DataFrame):
        frame = bars
        if "close" in frame.columns:
            return pd.to_numeric(frame["close"], errors="coerce").dropna()
        return pd.Series(dtype="float64")

    frame = pd.DataFrame(bars)
    if "close" in frame.columns:
        return pd.to_numeric(frame["close"], errors="coerce").dropna()
    if frame.shape[1] == 1:
        return pd.to_numeric(frame.iloc[:, 0], errors="coerce").dropna()
    return pd.to_numeric(pd.Series(bars), errors="coerce").dropna()


def _resolve_total_exposure(config):
    risk_config = config.get("risk", {})
    timing_config = risk_config.get("market_timing", {})
    full_exposure = timing_config.get("full_exposure", 1.0)

    if not timing_config.get("enabled", False):
        return float(full_exposure)

    try:
        bars = history_bars(
            timing_config["index"],
            250,
            "1d",
            "close",
            skip_suspended=False,
            include_now=True,
            adjust_type="pre",
        )
    except Exception as exc:  # pragma: no cover - depends on live data backend
        logger.warning(
            "failed to fetch market timing index bars; using full exposure: {}".format(
                exc
            )
        )
        return float(full_exposure)

    close = _close_series_from_bars(bars)
    if len(close) < 120:
        logger.warning("market timing data is insufficient; using full exposure")
        return float(full_exposure)

    return market_timing_exposure(
        close,
        full_exposure=full_exposure,
        ma120_exposure=timing_config.get("ma120_exposure", full_exposure),
        ma250_exposure=timing_config.get("ma250_exposure", full_exposure),
    )


def _build_targets(scored, current_positions, config):
    portfolio_config = config["portfolio"]
    risk_config = config.get("risk", {})
    holding_count = portfolio_config["holding_count"]
    total_exposure = _resolve_total_exposure(config)

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
        return apply_stock_weight_cap(targets, risk_config["max_stock_weight"])
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
    stock_pool = _resolve_stock_pool(config)
    logger.info("stock pool size: {}".format(len(stock_pool)))

    daily_data = _fetch_daily_data(stock_pool)
    if not daily_data:
        logger.warning("no daily data available; clearing non-target positions")
        _order_to_targets({})
        return

    financial_data = _resolve_financial_data(context, daily_data.keys())
    raw_factors = _calculate_raw_factors(daily_data, financial_data)
    filtered_factors = _apply_filters(raw_factors, daily_data, config)
    if filtered_factors.empty:
        logger.warning("no stocks passed factor filters; clearing non-target positions")
        _order_to_targets({})
        return

    factor_columns = _enabled_factor_columns(filtered_factors, config)
    processed = preprocess_factors(
        filtered_factors[factor_columns],
        FACTOR_METADATA,
        winsorize_quantiles=tuple(
            config.get("scoring", {}).get("winsorize_quantiles", (0.01, 0.99))
        ),
        missing=config.get("scoring", {}).get("missing", "median"),
    )
    scored = build_factor_scores(
        processed,
        FACTOR_METADATA,
        config["factors"]["category_weights"],
        factor_weights=config["factors"].get("factor_weights"),
    )
    targets = _build_targets(scored, _current_positions(), config)

    logger.info("target stocks: {}".format(list(targets)))
    for order_book_id in targets:
        score_row = scored.loc[order_book_id]
        logger.info(_score_log_message(order_book_id, score_row, config))
    _order_to_targets(targets)


def handle_bar(context, bar_dict):
    pass
