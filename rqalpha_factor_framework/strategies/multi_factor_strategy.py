from rqalpha.apis import index_components, logger

from rqalpha_factor_framework.config import load_config


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


def rebalance(context, bar_dict):
    config = context.factor_config
    stock_pool = _resolve_stock_pool(config)
    logger.info("stock pool size: {}".format(len(stock_pool)))
    logger.info("first version expects integration in Task 8; no orders submitted")


def handle_bar(context, bar_dict):
    pass
