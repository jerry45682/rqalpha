def build_equal_weight_targets(
    scored,
    current_positions,
    holding_count,
    buffer_count,
    total_exposure=1.0,
):
    ranked = list(scored.sort_values("score", ascending=False).index)
    buy_zone = ranked[: int(holding_count)]
    hold_zone = set(ranked[: int(buffer_count)])

    targets = []
    for stock in current_positions:
        if stock in hold_zone and stock not in targets:
            targets.append(stock)
        if len(targets) >= int(holding_count):
            break

    for stock in buy_zone:
        if len(targets) >= int(holding_count):
            break
        if stock not in targets:
            targets.append(stock)

    if not targets:
        return {}

    weight = float(total_exposure) / len(targets)
    return {stock: weight for stock in targets}
