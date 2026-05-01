def build_equal_weight_targets(scores, portfolio_size):
    ranked = scores.sort_values("score", ascending=False).head(int(portfolio_size))
    if ranked.empty:
        return {}
    weight = 1.0 / len(ranked)
    return {order_book_id: weight for order_book_id in ranked.index}

