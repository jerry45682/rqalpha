def plan_rebalance_orders(current_positions, target_weights):
    current = set(current_positions)
    target = set(target_weights)
    orders = []

    for order_book_id in sorted(current - target):
        orders.append((order_book_id, 0.0))
    for order_book_id in sorted(target):
        orders.append((order_book_id, float(target_weights[order_book_id])))
    return orders


def execute_rebalance(order_func, orders, logger):
    for order_book_id, target_weight in orders:
        logger.info("order_target_percent {} {:.4f}".format(order_book_id, target_weight))
        order_func(order_book_id, target_weight)
