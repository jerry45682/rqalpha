from numbers import Real

import pandas as pd


def _validate_non_negative_number(value, label):
    if not isinstance(value, Real) or pd.isna(value) or value < 0:
        raise ValueError(f"{label} weights must be non-negative numbers")
    return float(value)


def _metadata_categories(metadata):
    categories = {}
    factor_categories = {}
    for factor, meta in metadata.items():
        categories.setdefault(meta.category, []).append(factor)
        factor_categories[factor] = meta.category
    return categories, factor_categories


def _validate_category_weights(category_weights, known_categories, active_categories):
    validated = {}
    for category, weight in category_weights.items():
        if category not in known_categories:
            raise ValueError(f"category_weights contains unknown category: {category}")
        validated[category] = _validate_non_negative_number(weight, "category_weights")

    for category in active_categories:
        if category not in validated:
            raise ValueError(f"category_weights missing weight for category: {category}")

    return validated


def _validate_factor_weights(factor_weights, known_categories, factor_categories):
    validated = {}
    for category, weights in factor_weights.items():
        if category not in known_categories:
            raise ValueError(f"factor_weights contains unknown category: {category}")

        validated[category] = {}
        for factor, weight in weights.items():
            if factor_categories.get(factor) != category:
                raise ValueError(f"factor_weights contains unknown factor: {factor}")
            validated[category][factor] = _validate_non_negative_number(
                weight, "factor_weights"
            )

    return validated


def _normalized_weights(category, factors, configured_weights=None):
    if configured_weights is not None:
        raw_weights = pd.Series(
            {factor: configured_weights.get(factor, 0.0) for factor in factors},
            dtype="float64",
        )
        total = raw_weights.sum()
        if total == 0:
            raise ValueError(
                f"factor_weights for category {category} must have positive total"
            )
        return raw_weights / total
    return pd.Series(1.0 / len(factors), index=factors, dtype="float64")


def build_factor_scores(processed_factors, metadata, category_weights, factor_weights=None):
    factor_weights = factor_weights or {}
    known_categories, factor_categories = _metadata_categories(metadata)
    result = pd.DataFrame(index=processed_factors.index)
    category_columns = []

    active_categories = {}
    for factor, meta in metadata.items():
        if factor in processed_factors.columns:
            active_categories.setdefault(meta.category, []).append(factor)

    validated_category_weights = _validate_category_weights(
        category_weights,
        known_categories,
        active_categories,
    )
    validated_factor_weights = _validate_factor_weights(
        factor_weights,
        known_categories,
        factor_categories,
    )

    for category, factors in active_categories.items():
        weights = _normalized_weights(
            category,
            factors,
            validated_factor_weights.get(category),
        )
        score_column = f"{category}_score"
        result[score_column] = processed_factors[factors].mul(weights, axis=1).sum(axis=1)
        category_columns.append((score_column, validated_category_weights[category]))

    if not category_columns:
        result["score"] = 0.0
    else:
        weights = pd.Series(dict(category_columns), dtype="float64")
        result["score"] = result[weights.index].mul(weights, axis=1).sum(axis=1)

    return result.sort_values("score", ascending=False)
