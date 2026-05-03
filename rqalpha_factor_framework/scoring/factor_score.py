import pandas as pd


def _normalized_weights(factors, configured_weights=None):
    if configured_weights:
        raw_weights = pd.Series(
            {factor: configured_weights.get(factor, 0.0) for factor in factors},
            dtype="float64",
        )
        total = raw_weights.sum()
        if total != 0:
            return raw_weights / total
    return pd.Series(1.0 / len(factors), index=factors, dtype="float64")


def build_factor_scores(processed_factors, metadata, category_weights, factor_weights=None):
    factor_weights = factor_weights or {}
    result = pd.DataFrame(index=processed_factors.index)
    category_columns = []

    categories = {}
    for factor, meta in metadata.items():
        if factor in processed_factors.columns:
            categories.setdefault(meta.category, []).append(factor)

    for category, factors in categories.items():
        weights = _normalized_weights(factors, factor_weights.get(category))
        score_column = f"{category}_score"
        result[score_column] = processed_factors[factors].mul(weights, axis=1).sum(axis=1)
        category_columns.append((category, score_column))

    effective_category_weights = pd.Series(
        {
            column: category_weights.get(category, 0.0)
            for category, column in category_columns
        },
        dtype="float64",
    )
    total_weight = effective_category_weights.sum()
    if total_weight != 0:
        effective_category_weights = effective_category_weights / total_weight

    if len(effective_category_weights) == 0:
        result["score"] = 0.0
    else:
        result["score"] = result[effective_category_weights.index].mul(
            effective_category_weights, axis=1
        ).sum(axis=1)

    return result.sort_values("score", ascending=False)
