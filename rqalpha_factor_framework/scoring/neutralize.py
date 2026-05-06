def neutralize_factors(frame, method="none", **kwargs):
    if method == "none":
        return frame
    raise ValueError(f"Unsupported neutralization method: {method}")
