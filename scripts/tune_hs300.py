"""
Three-phase parameter tuning for HS300 multi-factor strategy.
Phase 1 (1-5): Explore   Phase 2 (6-15): Exploit   Phase 3 (16-20): Robust
"""
import copy, json, os, pickle, random, sys, time, yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import rqalpha
from rqalpha_factor_framework.backtest.run_backtest import build_rqalpha_config

BASELINE_PATH = PROJECT_ROOT / "rqalpha_factor_framework/config/multi_factor_config.yaml"
TEMP_CONFIG    = PROJECT_ROOT / "rqalpha_factor_framework/config/_tune_tmp.yaml"
TUNE_LOG       = PROJECT_ROOT / "scripts/_tune_results.json"
STRATEGY_FILE  = PROJECT_ROOT / "rqalpha_factor_framework/strategies/multi_factor_strategy.py"

CATEGORIES = ["growth", "momentum", "quality", "valuation",
              "technical", "reversal", "risk", "liquidity"]

RANGES = {
    "holding_count":      (10, 25),
    "weighting":          ["equal", "score"],
    "buffer_ratio":       (1.5, 3.0),
    "min_avg_amount_20":  (10_000_000, 50_000_000),
    "max_stock_weight":   (0.05, 0.20),
    "market_timing":      [True, False],
}
CAT_RANGES = {
    "growth":     (0.05, 0.40),
    "momentum":   (0.05, 0.35),
    "quality":    (0.05, 0.35),
    "valuation":  (0.05, 0.25),
    "technical":  (0.00, 0.25),
    "reversal":   (0.00, 0.10),
    "risk":       (0.00, 0.15),
    "liquidity":  (0.00, 0.10),
}


def _rand(r):
    """Sample from (lo, hi) or list."""
    if isinstance(r, list):
        return random.choice(r)
    lo, hi = r
    if isinstance(lo, float):
        return random.uniform(lo, hi)
    return random.randint(lo, hi)


def _random_category_weights():
    raw = {c: random.uniform(v[0], v[1]) for c, v in CAT_RANGES.items()}
    total = sum(raw.values())
    cats = list(raw.keys())
    w = {c: raw[c] / total for c in cats[:-1]}
    # Last weight = 1.0 - sum(others), guarantees exact 1.0, no rounding
    w[cats[-1]] = 1.0 - sum(w.values())
    return w


def _build_temp_config(baseline, params):
    """Build a complete YAML config dict with sampled parameters."""
    b = json.loads(json.dumps(baseline))  # deep copy via json

    h = params["holding_count"]
    b["portfolio"]["holding_count"] = h
    b["portfolio"]["buffer_count"] = max(h + 1, int(h * params["buffer_ratio"]))
    b["portfolio"]["weighting"] = params["weighting"]

    w = _random_category_weights()
    b["factors"]["category_weights"] = w

    b["filters"]["min_avg_amount_20"] = params["min_avg_amount_20"]
    b["risk"]["max_stock_weight"] = params["max_stock_weight"]
    b["risk"]["market_timing"]["enabled"] = params["market_timing"]
    b["backtest"]["result_path"] = str(
        PROJECT_ROOT / "rqalpha_factor_framework/backtest/_tune_result.pkl"
    )

    return b, w


def _score(summary):
    ret = summary.get("annualized_returns", 0) or 0
    sharpe = summary.get("sharpe", 0) or 0
    mdd = summary.get("max_drawdown", 1) or 1
    return ret * 0.5 + sharpe * 0.3 - mdd * 0.2


def main():
    random.seed(42)
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = yaml.safe_load(f)

    results, top_params = [], []

    for run in range(1, 21):
        phase = 1 if run <= 5 else 2 if run <= 15 else 3
        label = {1: "EXPLORE", 2: "EXPLOIT", 3: "ROBUST"}[phase]

        # --- sample parameters ---
        if phase == 1:
            params = {k: _rand(v) for k, v in RANGES.items()}
        elif phase == 2:
            # narrow around top-3 + some wide exploration
            top_vals = {k: [] for k in RANGES}
            for tp in top_params[:3]:
                for k in RANGES:
                    if isinstance(RANGES[k], list):
                        top_vals[k].append(tp[k])
                    else:
                        top_vals[k].append(tp.get(k, _rand(RANGES[k])))
            params = {}
            for k, r in RANGES.items():
                if random.random() < 0.3:
                    params[k] = _rand(r)  # 30% random exploration
                elif isinstance(r, list):
                    params[k] = random.choice(top_vals[k])
                else:
                    lo, hi = r
                    center = sum(top_vals[k]) / len(top_vals[k])
                    span = (hi - lo) * 0.3
                    params[k] = _rand((max(lo, center - span), min(hi, center + span)))
            # ensure int
            for k in ["holding_count", "min_avg_amount_20"]:
                params[k] = int(params[k])
        else:
            # Phase 3: lock structure, only perturb weights
            best = top_params[0]
            params = {k: best.get(k, _rand(RANGES[k])) for k in RANGES}

        # --- build config ---
        cfg, weights = _build_temp_config(baseline, params)

        with open(TEMP_CONFIG, "w", encoding="utf-8") as f:
            yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        print(f"\n{'='*55}")
        print(f" Run {run:2d}/20 [{label:7s}] holding={params['holding_count']} "
              f"weight={params['weighting']} timing={params['market_timing']}")
        print(f" growth={weights['growth']:.2f} momentum={weights['momentum']:.2f} "
              f"quality={weights['quality']:.2f} val={weights['valuation']:.2f} "
              f"tech={weights['technical']:.2f}")

        t0 = time.perf_counter()
        try:
            rq_config = build_rqalpha_config(TEMP_CONFIG)
            source = STRATEGY_FILE.read_text(encoding="utf-8")
            rqalpha.run(rq_config, source_code=source)
            elapsed = time.perf_counter() - t0

            with open(cfg["backtest"]["result_path"], "rb") as f:
                s = pickle.load(f)["summary"]
            sc = _score(s)

            entry = {
                "run": run, "phase": label,
                "total_returns": float(s["total_returns"]),
                "annualized_returns": float(s["annualized_returns"]),
                "sharpe": float(s["sharpe"]),
                "max_drawdown": float(s["max_drawdown"]),
                "score": round(sc, 4), "elapsed_s": round(elapsed, 1),
                "params": params, "weights": weights,
            }
            print(f"  => ret={s['annualized_returns']:.2%} sharpe={s['sharpe']:.2f} "
                  f"mdd={s['max_drawdown']:.2%} score={sc:.4f} ({elapsed:.0f}s)")
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            print(f"  FAILED: {exc}")
            entry = {"run": run, "phase": label, "score": -999,
                     "elapsed_s": elapsed, "error": str(exc)}

        results.append(entry)

        # update top-3 params
        valid = [r for r in results if r.get("score", -999) > -999]
        valid.sort(key=lambda r: r["score"], reverse=True)
        top_params = [r["params"] for r in valid[:3]]

        with open(TUNE_LOG, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

    # ---- final ----
    valid = [r for r in results if r.get("score", -999) > -999]
    valid.sort(key=lambda r: r["score"], reverse=True)
    print(f"\n{'='*60}")
    print(f"  FINAL TOP 5")
    for i, r in enumerate(valid[:5]):
        print(f"  #{i+1} run={r['run']:2d} {r['phase']:7s} score={r['score']:.4f} "
              f"ret={r['annualized_returns']:.2%} sharpe={r['sharpe']:.2f} mdd={r['max_drawdown']:.2%}")

    # save best config
    best = valid[0]
    best_all = best["params"].copy()
    best_cfg, _ = _build_temp_config(baseline, best_all)
    best_path = PROJECT_ROOT / "rqalpha_factor_framework/config/_tune_best.yaml"
    with open(best_path, "w", encoding="utf-8") as f:
        yaml.dump(best_cfg, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"\n  Best config -> {best_path}")


if __name__ == "__main__":
    main()
