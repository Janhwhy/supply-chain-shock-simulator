"""learn_weights.py — Fits the resilience-score weights to data instead of
hand-picking them, and evaluates the learned scorecard on held-out seeds
against every baseline from eval_harness.py.

Motivation (see evaluation/results/ from eval_harness.py):
The default hand-set weights (0.40 / 0.25 / 0.20 / 0.15 over dependency /
geographic / reliability / substitutability) rank suppliers *worse* than a
single concentration metric (dependency_only) when measured against realized
P95 revenue-at-risk from the Monte Carlo simulation. A follow-up "noise
ceiling" check (evaluation/ceiling_check.py) showed the ground-truth ranking
is highly stable across independent simulation draws (~0.98 Precision@10
self-consistency), meaning the low scores above reflect a real, closeable
gap rather than inherent randomness in the task.

That motivated adding a 5th risk factor, revenue_weighted (supply-share
concentration weighted by the product's actual revenue — unit_cost x
monthly_demand — rather than raw share alone), since the simulator's
ground truth is dominated by revenue-weighted exposure. The functional form
(a convex combination of risk factors) is otherwise kept identical to
src/scoring.py — only the weights (and now this one added factor) are
learned/fit to data.

Method
------
1. Train on seeds [0, n_train): for each seed, bootstrap-resample the
   transaction history, recompute the five raw risk-factor series
   (dependency/geographic/reliability/substitutability/revenue_weighted),
   and run the full Monte Carlo simulation for ground truth (total P95
   exposure per supplier).
2. Optimize weights on the simplex (non-negative, sum to 1) via an exhaustive
   vectorized grid search (step = 1/resolution) that maximizes the mean
   Spearman rank correlation between the weighted composite risk and
   ground-truth exposure, averaged over the training seeds. Grid search is
   used instead of gradient-based optimization because rank correlation is
   piecewise-constant (not differentiable) and the simplex is low-dimensional,
   so exhaustive search is feasible and exact up to the chosen resolution.
3. Evaluate the learned weights, unchanged, on completely disjoint held-out
   seeds [n_train, n_train + n_test) — no leakage — using the same metrics
   and baselines as eval_harness.py (Spearman, Precision@K, NDCG@K, paired
   Wilcoxon signed-rank test against each baseline), plus the standalone
   revenue_weighted_only baseline.

Usage:
    python evaluation/learn_weights.py --n-train 20 --n-test 20 --n-runs 5000 --k 10
"""

import argparse
import itertools
import os
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon

from eval_harness import (
    DATA_DIR,
    METHODS,
    load_base_data,
    precompute_transaction_arrays,
    build_enriched_suppliers,
    compute_ground_truth,
    compute_method_scores,
    compute_revenue_weighted_risk,
    precision_at_k,
    ndcg_at_k,
)
from src import scoring as sc
from src import graph as gr

OUT_DIR = os.path.join(os.path.dirname(__file__), "results")
FACTOR_NAMES = ["dependency", "geographic", "reliability", "substitutability", "revenue_weighted"]
DEFAULT_WEIGHTS_FOR_DISPLAY = {
    "dependency": 0.40,
    "geographic": 0.25,
    "reliability": 0.20,
    "substitutability": 0.15,
    "revenue_weighted": None,  # not present in the original hand-tuned scorecard
}


# ---------------------------------------------------------------------------
# Raw (unweighted) risk-factor matrix — same components as
# src/scoring.py::compute_resilience_scores, exposed individually.
# ---------------------------------------------------------------------------

def compute_risk_factor_matrix(df_suppliers, df_enriched, df_relationships, df_products):
    dependency = sc.compute_dependency_risk(df_relationships)
    geographic = sc.compute_geographic_risk(df_suppliers)
    reliability = sc.compute_reliability_risk(df_enriched)
    substitutability = sc.compute_substitutability_risk(df_relationships)
    revenue_weighted = compute_revenue_weighted_risk(df_relationships, df_products)

    df = pd.DataFrame(
        {
            "dependency": dependency,
            "geographic": geographic,
            "reliability": reliability,
            "substitutability": substitutability,
            "revenue_weighted": revenue_weighted,
        }
    )
    df.index.name = "supplier_id"
    return df.reindex(df_suppliers["supplier_id"]).fillna(0.0)


def build_seed_records(seeds, df_suppliers, df_products, df_relationships,
                        delay_by_supplier, rej_by_supplier, n_runs, label):
    records = []
    for seed in seeds:
        rng = np.random.default_rng(seed)
        df_enriched = build_enriched_suppliers(df_suppliers, delay_by_supplier, rej_by_supplier, rng)
        ground_truth = compute_ground_truth(df_enriched, df_relationships, df_products, n_runs=n_runs, seed=seed)
        factor_matrix = compute_risk_factor_matrix(df_suppliers, df_enriched, df_relationships, df_products)
        records.append({"seed": seed, "df_enriched": df_enriched, "ground_truth": ground_truth, "factors": factor_matrix})
        print(f"  [{label}] seed {seed} prepared "
              f"(ground truth suppliers={len(ground_truth)})")
    return records


def mean_train_spearman(weights, train_records):
    rhos = []
    for rec in train_records:
        factors = rec["factors"]
        gt = rec["ground_truth"].reindex(factors.index).fillna(0.0)
        composite = factors.to_numpy() @ weights
        rho, _ = spearmanr(composite, gt.to_numpy())
        rhos.append(0.0 if np.isnan(rho) else rho)
    return float(np.mean(rhos))


def simplex_grid(n_dims, resolution):
    """All non-negative integer compositions of `resolution` into n_dims parts, scaled to sum to 1."""
    points = []
    for combo in itertools.product(range(resolution + 1), repeat=n_dims - 1):
        if sum(combo) > resolution:
            continue
        last = resolution - sum(combo)
        points.append(combo + (last,))
    return np.array(points, dtype=float) / resolution


def _rank_columns(mat):
    """Fast (no tie-correction) column-wise rank, vectorized across many candidate weight vectors."""
    order = np.argsort(mat, axis=0)
    ranks = np.empty_like(order, dtype=float)
    rows = np.arange(mat.shape[0])[:, None]
    cols = np.arange(mat.shape[1])[None, :]
    ranks[order, cols] = rows
    return ranks


def optimize_weights(train_records, resolution=25):
    """Exhaustive grid search over the 4-dim weight simplex (step = 1/resolution),
    maximizing mean Spearman correlation with ground-truth exposure across train seeds.
    Vectorized: evaluates every grid point against every seed in one shot per seed."""
    candidates = simplex_grid(len(FACTOR_NAMES), resolution)  # (n_candidates, 4)
    total_scores = np.zeros(len(candidates))

    for rec in train_records:
        factors = rec["factors"].to_numpy()  # (n_suppliers, 4)
        gt = rec["ground_truth"].reindex(rec["factors"].index).fillna(0.0).to_numpy()

        composite_matrix = factors @ candidates.T  # (n_suppliers, n_candidates)
        ranks = _rank_columns(composite_matrix)
        gt_ranks = _rank_columns(gt.reshape(-1, 1)).ravel()

        gt_centered = gt_ranks - gt_ranks.mean()
        ranks_centered = ranks - ranks.mean(axis=0, keepdims=True)
        numerator = gt_centered @ ranks_centered
        denom = np.sqrt((gt_centered ** 2).sum() * (ranks_centered ** 2).sum(axis=0))
        denom[denom == 0] = np.nan
        seed_scores = np.nan_to_num(numerator / denom, nan=0.0)
        total_scores += seed_scores

    mean_scores = total_scores / len(train_records)
    best_idx = int(np.argmax(mean_scores))
    best_weights = candidates[best_idx]

    # Report the exact (tie-corrected) scipy Spearman for the chosen point, for honest logging.
    exact_train_spearman = mean_train_spearman(best_weights, train_records)
    return dict(zip(FACTOR_NAMES, best_weights)), exact_train_spearman


# ---------------------------------------------------------------------------
# Evaluation on held-out test seeds
# ---------------------------------------------------------------------------

def evaluate_all_methods_on_record(rec, learned_weights, df_pagerank, df_suppliers,
                                    df_relationships, df_products, k, rng):
    ground_truth = rec["ground_truth"]
    factors = rec["factors"]
    df_enriched = rec["df_enriched"]

    method_scores = compute_method_scores(df_suppliers, df_enriched, df_relationships, df_products, df_pagerank, rng)

    w = np.array([learned_weights[f] for f in FACTOR_NAMES])
    method_scores["composite_learned"] = pd.Series(
        factors.to_numpy() @ w, index=factors.index
    )

    common_ids = ground_truth.index
    true_ranking = ground_truth.sort_values(ascending=False).index.tolist()
    max_exposure = ground_truth.max()
    relevance = (ground_truth / max_exposure).to_dict() if max_exposure > 0 else {}

    rows = []
    for method, series in method_scores.items():
        series = series.reindex(common_ids).fillna(0.0)
        pred_ranking = series.sort_values(ascending=False).index.tolist()
        rho, _ = spearmanr(series.values, ground_truth.values)
        rows.append(
            {
                "method": method,
                "spearman": rho if not np.isnan(rho) else 0.0,
                f"precision_at_{k}": precision_at_k(pred_ranking, true_ranking, k),
                f"ndcg_at_{k}": ndcg_at_k(pred_ranking, relevance, k),
            }
        )
    df = pd.DataFrame(rows)
    df["seed"] = rec["seed"]
    return df


def run(n_train, n_test, n_runs, k, out_dir):
    warnings.filterwarnings("ignore")
    os.makedirs(out_dir, exist_ok=True)

    print("Loading base synthetic data...")
    df_suppliers, df_products, df_relationships, df_transactions = load_base_data()
    delay_by_supplier, rej_by_supplier = precompute_transaction_arrays(df_transactions)

    print("Building dependency graph / PageRank (structure-only)...")
    G = gr.build_dependency_graph(df_relationships, df_suppliers, df_products)
    df_pagerank = gr.compute_pagerank(G)

    train_seeds = list(range(0, n_train))
    test_seeds = list(range(n_train, n_train + n_test))

    print(f"\nPreparing {n_train} TRAIN seeds (weight fitting)...")
    train_records = build_seed_records(train_seeds, df_suppliers, df_products, df_relationships,
                                        delay_by_supplier, rej_by_supplier, n_runs, "train")

    print(f"\nPreparing {n_test} TEST seeds (held-out evaluation, disjoint from train)...")
    test_records = build_seed_records(test_seeds, df_suppliers, df_products, df_relationships,
                                       delay_by_supplier, rej_by_supplier, n_runs, "test")

    print("\nOptimizing weights on TRAIN seeds via exhaustive simplex grid search "
          "(maximize mean Spearman correlation with realized P95 exposure)...")
    learned_weights, train_spearman = optimize_weights(train_records)
    print("Learned weights:")
    for name in FACTOR_NAMES:
        default_val = DEFAULT_WEIGHTS_FOR_DISPLAY[name]
        default_str = f"{default_val:.2f}" if default_val is not None else "n/a (new factor)"
        print(f"  {name:<18} {learned_weights[name]:.4f}  (default: {default_str})")
    print(f"Mean train Spearman achieved: {train_spearman:.4f}")

    pd.DataFrame([learned_weights]).to_csv(os.path.join(out_dir, "learned_weights.csv"), index=False)

    print("\nEvaluating learned weights + all baselines on HELD-OUT test seeds...")
    all_rows = []
    for rec in test_records:
        rng = np.random.default_rng(rec["seed"] + 100000)
        df_metrics = evaluate_all_methods_on_record(
            rec, learned_weights, df_pagerank, df_suppliers, df_relationships, df_products, k, rng
        )
        all_rows.append(df_metrics)

    df_all = pd.concat(all_rows, ignore_index=True)
    df_all.to_csv(os.path.join(out_dir, "learned_weights_test_results.csv"), index=False)

    metric_cols = [c for c in df_all.columns if c not in ("method", "seed")]
    all_methods = METHODS + ["composite_learned"]

    summary_rows = []
    for method in all_methods:
        sub = df_all[df_all["method"] == method]
        row = {"method": method, "n_seeds": len(sub)}
        for col in metric_cols:
            vals = sub[col].to_numpy()
            mean = vals.mean()
            ci95 = 1.96 * vals.std(ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else 0.0
            row[f"{col}_mean"] = mean
            row[f"{col}_ci95"] = ci95
        summary_rows.append(row)
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(os.path.join(out_dir, "learned_weights_summary.csv"), index=False)

    print(f"\n=== Held-out test summary (mean +/- 95% CI over {n_test} seeds) ===")
    for _, row in df_summary.iterrows():
        parts = [f"{row['method']:<20}"]
        for col in metric_cols:
            parts.append(f"{col}={row[f'{col}_mean']:.4f}+/-{row[f'{col}_ci95']:.4f}")
        print("  " + "  ".join(parts))

    print("\n=== composite_learned vs. every baseline on held-out seeds "
          "(% improvement + paired Wilcoxon) ===")
    sig_rows = []
    learned_vals = {
        col: df_all[df_all["method"] == "composite_learned"].sort_values("seed")[col].to_numpy()
        for col in metric_cols
    }
    for method in all_methods:
        if method == "composite_learned":
            continue
        for col in metric_cols:
            base_vals = df_all[df_all["method"] == method].sort_values("seed")[col].to_numpy()
            learn_vals = learned_vals[col]
            base_mean = base_vals.mean()
            pct = (learn_vals.mean() - base_mean) / base_mean * 100 if base_mean != 0 else float("nan")
            try:
                _, p_value = wilcoxon(learn_vals, base_vals)
            except ValueError:
                p_value = float("nan")
            sig_rows.append(
                {"metric": col, "baseline": method, "learned_mean": learn_vals.mean(),
                 "baseline_mean": base_mean, "pct_improvement": pct, "wilcoxon_p": p_value}
            )
            print(f"  [{col}] composite_learned vs {method}: {pct:+.1f}%  (p={p_value:.4g})")

    pd.DataFrame(sig_rows).to_csv(os.path.join(out_dir, "learned_weights_significance.csv"), index=False)
    print(f"\nResults written to {out_dir}/")
    return learned_weights, df_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-train", type=int, default=20)
    parser.add_argument("--n-test", type=int, default=20)
    parser.add_argument("--n-runs", type=int, default=5000)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--out-dir", type=str, default=OUT_DIR)
    args = parser.parse_args()
    run(args.n_train, args.n_test, args.n_runs, args.k, args.out_dir)


if __name__ == "__main__":
    main()
