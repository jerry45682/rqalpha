from pathlib import Path

from rqalpha.apis import (
    get_factor,
    history_bars,
    index_components,
    logger,
    order_target_percent,
)

from rqalpha.examples.multi_factor_strategy.config import load_config
from rqalpha.examples.multi_factor_strategy.factors import (
    add_momentum_factor,
    build_factor_scores,
    fetch_fundamental_factors,
)
from rqalpha.examples.multi_factor_strategy.filters import filter_tradeable, resolve_stock_pool
from rqalpha.examples.multi_factor_strategy.portfolio import build_equal_weight_targets
from rqalpha.examples.multi_factor_strategy.rebalancer import execute_rebalance, plan_rebalance_orders


def init(context):
    from rqalpha.api import market_open, scheduler

    config_path = getattr(context, "multi_factor_config", None)
    context.multi_factor_config = load_config(config_path)

    rebalance_config = context.multi_factor_config["rebalance"]
    frequency = rebalance_config.get("frequency", "monthly")
    if frequency != "monthly":
        raise ValueError("Only monthly rebalancing is supported by this example")

    scheduler.run_monthly(
        rebalance,
        tradingday=int(rebalance_config.get("tradingday", 1)),
        time_rule=market_open(minute=1),
    )
    logger.info("multi-factor strategy initialized with %s", Path(config_path or __file__).name)


def rebalance(context, bar_dict):
    config = context.multi_factor_config
    today = context.now.date() if hasattr(context, "now") else None
    logger.info("rebalance date: %s", today)

    stock_pool = resolve_stock_pool(config, index_components=index_components)
    stock_pool = filter_tradeable(
        stock_pool,
        is_suspended=lambda order_book_id: bar_dict[order_book_id].is_suspended,
    )
    logger.info("stock pool size after filters: %d", len(stock_pool))

    factors = fetch_fundamental_factors(stock_pool, get_factor)
    factors = add_momentum_factor(factors, history_bars)
    scored = build_factor_scores(
        factors,
        weights=config["factors"]["weights"],
        winsorize_quantiles=tuple(config["factors"]["winsorize_quantiles"]),
    )
    targets = build_equal_weight_targets(scored, config["portfolio"]["size"])
    logger.info("target stocks: %s", list(targets.keys()))

    for order_book_id in targets:
        row = scored.loc[order_book_id]
        logger.info(
            "factor score %s total=%.6f pe=%.6f pb=%.6f roe=%.6f momentum_60=%.6f",
            order_book_id,
            row["score"],
            row.get("pe_score", 0.0),
            row.get("pb_score", 0.0),
            row.get("roe_score", 0.0),
            row.get("momentum_60_score", 0.0),
        )

    current_positions = [
        order_book_id for order_book_id, position in context.portfolio.positions.items()
        if position.quantity > 0
    ]
    orders = plan_rebalance_orders(current_positions, targets)
    execute_rebalance(order_target_percent, orders, logger)


def handle_bar(context, bar_dict):
    pass
