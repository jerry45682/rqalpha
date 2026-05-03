import pandas as pd


def build_score_weight_targets(scored, holding_count, total_exposure=1.0):
    if "score" not in scored.columns:
        return {}

    normalized = scored.copy()
    normalized["score"] = pd.to_numeric(normalized["score"], errors="coerce")
    selected = (
        normalized.dropna(subset=["score"])
        .sort_values("score", ascending=False)
        .head(int(holding_count))
    )
    if selected.empty:
        return {}

    shifted = selected["score"] - selected["score"].min()
    total = shifted.sum()
    if total <= 0:
        weight = float(total_exposure) / len(selected)
        return {stock: weight for stock in selected.index}

    return {
        stock: float(value / total * float(total_exposure))
        for stock, value in shifted.items()
    }
