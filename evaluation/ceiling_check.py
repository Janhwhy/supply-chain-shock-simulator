"""ceiling_check.py — Estimates the "noise ceiling" for the supplier-ranking
task: how much does the *actual* top-10 / ranking of realized P95 exposure
vary from one simulated year to the next, purely from stochastic randomness,
with no scoring method involved at all?

Motivation
----------
eval_harness.py / learn_weights.py found Precision@10 ~= 0.13 for the best
methods (barely above the ~0.10 expected from random guessing over 100
suppliers). Before concluding the methods are weak, we need to know: how
much does ground truth agree with *itself* across two independent simulated
realizations of the same underlying risk? If two honest simulation draws
only agree on ~15-20% of their own top-10 lists, then 0.13 is close to the
best any predictor could possibly achieve — the task itself has a low
ceiling, not the method.

Two ceiling variants are computed:
  A) FULL NOISE CEILING: pairs of seeds where both the bootstrap-resampled
     operational features (avg_delay_days, delay_volatility, rejection_rate)
     AND the Monte Carlo draw vary — apples-to-apples with the seeds used in
     eval_harness.py / learn_weights.py.
  B) PURE SIMULATION-NOISE CEILING: operational features held fixed (single
     bootstrap draw), only the Monte Carlo random seed varies — isolates
     randomness from the disruption simulation alone, without feature
     resampling noise.

For each variant, every pair of independent ground-truth draws is compared
against every other (both directions) using the same Precision@10, NDCG@10,
and Spearman metrics used to evaluate the actual scoring methods.

Usage:
    python evaluation/ceiling_check.py --n-seeds 20 --n-runs 5000 --k 10
"""

import argparse
import itertools
import os
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from eval_harness import (
    load_base_data,
    precompute_transaction_arrays,
    build_enriched_suppliers,
    compute_ground_truth,
    precision_at_k,
    ndcg_at_k,
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "results")


def compare_ground_truths(gt_a, gt_b, k):
    common = gt_a.index
    gt_b = gt_b.reindex(common).fillna(0.0)

    true_ranking = gt_b.sort_values(ascending=False).index.tolist()
    pred_ranking = gt_a.sort_values(ascending=False).index.tolist()
    max_exposure = gt_b.max()
    relevance = (gt_b / max_exposure).to_dict() if max_exposure > 0 else {}

    rho, _ = spearmanr(gt_a.values, gt_b.values)
    return {
        "spearman": 0.0 if np.isnan(rho) else rho,
        f"precision_at_{k}": precision_at_k(pred_ranking, true_ranking, k),
        f"ndcg_at_{k}": ndcg_at_k(pred_ranking, relevance, k),
    }


def pairwise_stats(ground_truths, k, label):
    rows = []
    for i, j in itertools.permutations(range(len(ground_truths)), 2):
        rows.append(compare_ground_truths(ground_truths[i], ground_truths[j], k))
    df = pd.DataFrame(rows)
    print(f"\n=== {label}: {len(ground_truths)} draws, {len(rows)} directed pairs ===")
    summary = {}
    for col in df.columns:
        vals = df[col].to_numpy()
        mean = vals.mean()
        ci95 = 1.96 * vals.std(ddof=1) / np.sqrt(len(vals))
        summary[col] = (mean, ci95)
        print(f"  {col}: {mean:.4f} +/- {ci95:.4f}")
    return df, summary


def run(n_seeds, n_runs, k, out_dir):
    warnings.filterwarnings("ignore")
    os.makedirs(out_dir, exist_ok=True)

    print("Loading base synthetic data...")
    df_suppliers, df_products, df_relationships, df_transactions = load_base_data()
    delay_by_supplier, rej_by_supplier = precompute_transaction_arrays(df_transactions)

    # --- Variant A: full noise (features + simulation both vary per seed) ---
    print(f"\nComputing FULL NOISE CEILING ground truths ({n_seeds} independent seeds, "
          f"bootstrap-resampled features + fresh Monte Carlo draw each)...")
    full_noise_gts = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        df_enriched = build_enriched_suppliers(df_suppliers, delay_by_supplier, rej_by_supplier, rng)
        gt = compute_ground_truth(df_enriched, df_relationships, df_products, n_runs=n_runs, seed=seed)
        full_noise_gts.append(gt)
        print(f"  seed {seed + 1}/{n_seeds} done")

    df_full, summary_full = pairwise_stats(full_noise_gts, k, "FULL NOISE CEILING (features + simulation vary)")

    # --- Variant B: pure simulation noise (fixed features, only MC seed varies) ---
    print(f"\nComputing PURE SIMULATION-NOISE CEILING ground truths "
          f"({n_seeds} draws, single fixed feature set, only Monte Carlo seed varies)...")
    rng_fixed = np.random.default_rng(0)
    df_enriched_fixed = build_enriched_suppliers(df_suppliers, delay_by_supplier, rej_by_supplier, rng_fixed)
    pure_sim_gts = []
    for seed in range(1000, 1000 + n_seeds):
        gt = compute_ground_truth(df_enriched_fixed, df_relationships, df_products, n_runs=n_runs, seed=seed)
        pure_sim_gts.append(gt)
        print(f"  MC draw {seed - 1000 + 1}/{n_seeds} done")

    df_pure, summary_pure = pairwise_stats(pure_sim_gts, k, "PURE SIMULATION-NOISE CEILING (features fixed)")

    df_full.to_csv(os.path.join(out_dir, "ceiling_full_noise.csv"), index=False)
    df_pure.to_csv(os.path.join(out_dir, "ceiling_pure_simulation_noise.csv"), index=False)

    print("\n=== Ceiling summary vs. your actual method results ===")
    print(f"  {'metric':<20}{'full_noise_ceiling':<22}{'pure_sim_ceiling':<22}")
    for col in [f"precision_at_{k}", f"ndcg_at_{k}", "spearman"]:
        f_mean, f_ci = summary_full[col]
        p_mean, p_ci = summary_pure[col]
        print(f"  {col:<20}{f_mean:.4f}+/-{f_ci:.4f}      {p_mean:.4f}+/-{p_ci:.4f}")

    print("\nReference — best method results from learn_weights.py (n=50 held-out seeds):")
    print("  precision_at_10: 0.1320   ndcg_at_10: 0.7742   spearman: 0.3029")

    summary_rows = []
    for variant, summ in [("full_noise_ceiling", summary_full), ("pure_simulation_ceiling", summary_pure)]:
        row = {"variant": variant}
        for col, (mean, ci) in summ.items():
            row[f"{col}_mean"] = mean
            row[f"{col}_ci95"] = ci
        summary_rows.append(row)
    pd.DataFrame(summary_rows).to_csv(os.path.join(out_dir, "ceiling_summary.csv"), index=False)
    print(f"\nResults written to {out_dir}/")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-seeds", type=int, default=20)
    parser.add_argument("--n-runs", type=int, default=5000)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--out-dir", type=str, default=OUT_DIR)
    args = parser.parse_args()
    run(args.n_seeds, args.n_runs, args.k, args.out_dir)


if __name__ == "__main__":
    main()
