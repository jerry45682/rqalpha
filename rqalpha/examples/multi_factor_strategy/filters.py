def resolve_stock_pool(config, index_components):
    pool_config = config.get("stock_pool", {})
    symbols = pool_config.get("symbols") or []
    if symbols:
        return list(symbols)

    index = pool_config.get("index", "000300.XSHG")
    return list(index_components(index))


def filter_tradeable(order_book_ids, is_suspended=None, is_st_stock=None):
    result = []
    for order_book_id in order_book_ids:
        if is_suspended is not None and is_suspended(order_book_id):
            continue
        if is_st_stock is not None and is_st_stock(order_book_id):
            continue
        result.append(order_book_id)
    return result

