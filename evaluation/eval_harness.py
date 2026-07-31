"""eval_harness.py — Benchmarks the composite resilience-scoring framework
against simpler baseline risk-ranking methods.

Task definition
---------------
A resilience score is a *cheap* proxy computed from static/operational
supplier features (dependency concentration, geography, reliability,
substitutability). The Monte Carlo simulation (src/simulation.py) is the
*expensive* ground truth: it draws disruption scenarios and reports the
realized P95 revenue-at-risk per supplier. This harness asks: how well does
each cheap scoring method rank suppliers relative to what the expensive
simulation says actually happens?

Ground truth per seed = total P95 exposure per supplier, summed across all
five disruption scenarios, from a fresh Monte Carlo draw.

Methods compared (all computed WITHOUT looking at the simulation output):
  - composite        : full weighted resilience score (default weights from src/scoring.py)
  - equal_weighted    : same four risk factors, equal (0.25) weights [ablation]
  - dependency_only   : max supply-share concentration risk alone
  - pagerank_only     : graph centrality (src/graph.py) alone
  - reliability_only  : vendor-scorecard-style reliability score alone
  - random            : shuffled ranking [sanity floor]

Each of N_SEEDS independent draws:
  1. bootstrap-resamples the transaction history per supplier (captures
     uncertainty in the operational features estimated from historical data),
  2. re-derives avg_delay_days / delay_volatility / rejection_rate /
     reliability_score exactly as notebooks/01_etl_pipeline.ipynb does,
  3. re-runs the full stochastic Monte Carlo simulation with a fresh seed.

Metrics: Spearman rank correlation, Precision@K, NDCG@K against the
ground-truth ranking. Reported as mean +/- 95% CI over seeds, with a paired
Wilcoxon signed-rank test (composite vs. each baseline) for significance.

Usage:
    python evaluation/eval_harness.py --n-seeds 30 --n-runs 5000 --k 10
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr, wilcoxon

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src import scoring as sc
from src import graph as gr
from src.scenarios import get_all_scenarios
from src.simulation import run_all_simulations

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw", "synthetic")
OUT_DIR = os.path.join(os.path.dirname(__file__), "results")

METHODS = [
    "composite",
    "equal_weighted",
    "dependency_only",
    "pagerank_only",
    "reliability_only",
    "revenue_weighted_only",
    "random",
]

EQUAL_WEIGHTS = {
    "dependency": 0.25,
    "geographic": 0.25,
    "reliability": 0.25,
    "substitutability": 0.25,
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_base_data():
    suppliers = pd.read_csv(os.path.join(DATA_DIR, "suppliers.csv"))
    products = pd.read_csv(os.path.join(DATA_DIR, "products.csv"))
    relationships = pd.read_csv(os.path.join(DATA_DIR, "supply_relationships.csv"))
    transactions = pd.read_csv(
        os.path.join(DATA_DIR, "transactions.csv"),
        parse_dates=["order_date", "promised_delivery_date", "actual_delivery_date"],
    )
    return suppliers, products, relationships, transactions


def precompute_transaction_arrays(transactions):
    """Group per-row delay days and rejection rate by supplier for fast bootstrap resampling."""
    df = transactions.copy()
    df["delay_days"] = (df["actual_delivery_date"] - df["promised_delivery_date"]).dt.days
    qty_clean = np.where(df["quantity_ordered"] <= 0, 1, df["quantity_ordered"])
    df["rejection_rate_row"] = df["quantity_rejected"] / qty_clean
    df["rejection_rate_row"] = df["rejection_rate_row"].fillna(0.0)

    delay_by_supplier = {}
    rej_by_supplier = {}
    for supplier_id, grp in df.groupby("supplier_id"):
        delay_vals = grp["delay_days"].dropna().to_numpy()
        delay_by_supplier[supplier_id] = delay_vals
        rej_by_supplier[supplier_id] = grp["rejection_rate_row"].to_numpy()

    return delay_by_supplier, rej_by_supplier


# ---------------------------------------------------------------------------
# Per-seed enrichment (bootstrap resample -> ETL formula from
# notebooks/01_etl_pipeline.ipynb, replicated exactly)
# ---------------------------------------------------------------------------

def build_enriched_suppliers(df_suppliers, delay_by_supplier, rej_by_supplier, rng):
    rows = []
    for _, row in df_suppliers.iterrows():
        sid = row["supplier_id"]
        delay_vals = delay_by_supplier.get(sid, np.array([]))
        rej_vals = rej_by_supplier.get(sid, np.array([]))

        if len(delay_vals) > 0:
            sample = delay_vals[rng.integers(0, len(delay_vals), size=len(delay_vals))]
            avg_delay = float(np.mean(sample))
            delay_vol = float(np.std(sample, ddof=1)) if len(sample) > 1 else 0.0
        else:
            avg_delay, delay_vol = 0.0, 0.0

        if len(rej_vals) > 0:
            sample_rej = rej_vals[rng.integers(0, len(rej_vals), size=len(rej_vals))]
            rejection_rate = float(np.mean(sample_rej))
        else:
            rejection_rate = 0.0

        rows.append(
            {
                "supplier_id": sid,
                "avg_delay_days": avg_delay,
                "delay_volatility": delay_vol,
                "rejection_rate": rejection_rate,
            }
        )

    df_enriched = df_suppliers.drop(
        columns=["avg_delay_days", "delay_volatility", "rejection_rate", "reliability_score"],
        errors="ignore",
    ).merge(pd.DataFrame(rows), on="supplier_id", how="left")

    def min_max(series):
        s_min, s_max = series.min(), series.max()
        if s_max == s_min:
            return series * 0.0
        return (series - s_min) / (s_max - s_min)

    norm_delay = min_max(df_enriched["avg_delay_days"])
    norm_vol = min_max(df_enriched["delay_volatility"])
    norm_rej = min_max(df_enriched["rejection_rate"])
    df_enriched["reliability_score"] = 1.0 - (
        0.4 * norm_delay + 0.4 * norm_vol + 0.2 * norm_rej
    )
    return df_enriched


# ---------------------------------------------------------------------------
# Ground truth: full Monte Carlo simulation -> total P95 exposure per supplier
# ---------------------------------------------------------------------------

def compute_ground_truth(df_enriched, df_relationships, df_products, n_runs, seed):
    np.random.seed(seed)
    scenarios = get_all_scenarios()
    df_sim = run_all_simulations(
        df_enriched, scenarios, df_relationships, df_products, n_runs=n_runs
    )
    exposure = df_sim.groupby("supplier_id")["p95_impact"].sum()
    return exposure


def compute_revenue_weighted_risk(df_relationships, df_products):
    """Supply-share concentration weighted by the actual revenue it represents
    (unit_cost x monthly_demand), summed per supplier and min-max normalized.
    Unlike dependency_only (raw max supply-share), this captures that a small
    share of a high-revenue product can matter more than a large share of a
    low-revenue one — the signal the Monte Carlo ground truth is dominated by."""
    merged = pd.merge(df_relationships, df_products, on="product_id")
    merged["revenue_exposure"] = merged["supply_share"] * merged["unit_cost"] * merged["monthly_demand"]
    raw = merged.groupby("supplier_id")["revenue_exposure"].sum()
    s_min, s_max = raw.min(), raw.max()
    if s_max == s_min:
        return pd.Series(0.0, index=raw.index)
    return (raw - s_min) / (s_max - s_min)


# ---------------------------------------------------------------------------
# Method scores (risk direction: higher = riskier), each indexed by supplier_id
# ---------------------------------------------------------------------------

def compute_method_scores(df_suppliers, df_enriched, df_relationships, df_products, df_pagerank, rng):
    scores = {}

    df_scored = sc.compute_resilience_scores(
        df_suppliers, df_enriched, df_relationships, df_simulation_results=pd.DataFrame()
    )
    scores["composite"] = df_scored.set_index("supplier_id")["composite_risk"]

    df_equal = sc.compute_resilience_scores(
        df_suppliers,
        df_enriched,
        df_relationships,
        df_simulation_results=pd.DataFrame(),
        weights=EQUAL_WEIGHTS,
    )
    scores["equal_weighted"] = df_equal.set_index("supplier_id")["composite_risk"]

    scores["dependency_only"] = sc.compute_dependency_risk(df_relationships)

    pr = df_pagerank[df_pagerank["node_type"] == "supplier"].copy()
    pr["supplier_id"] = pr["node_id"].apply(lambda v: int(v.split("_")[1]))
    scores["pagerank_only"] = pr.set_index("supplier_id")["pagerank_score"]

    reliability_risk = 1.0 - df_enriched.set_index("supplier_id")["reliability_score"]
    scores["reliability_only"] = reliability_risk

    scores["revenue_weighted_only"] = compute_revenue_weighted_risk(df_relationships, df_products)

    all_ids = df_suppliers["supplier_id"].to_numpy()
    scores["random"] = pd.Series(rng.permutation(len(all_ids)).astype(float), index=all_ids)

    return scores


# ---------------------------------------------------------------------------
# Ranking metrics
# ---------------------------------------------------------------------------

def precision_at_k(pred_ranking, true_ranking, k):
    pred_top = set(pred_ranking[:k])
    true_top = set(true_ranking[:k])
    return len(pred_top & true_top) / k


def ndcg_at_k(pred_ranking, relevance_by_id, k):
    def dcg(ranking):
        return sum(
            relevance_by_id.get(sid, 0.0) / np.log2(i + 2)
            for i, sid in enumerate(ranking[:k])
        )

    ideal_ranking = sorted(relevance_by_id, key=lambda sid: relevance_by_id[sid], reverse=True)
    idcg = dcg(ideal_ranking)
    if idcg == 0:
        return 0.0
    return dcg(ranking=pred_ranking) / idcg


def evaluate_methods(method_scores, ground_truth, k):
    common_ids = ground_truth.index
    true_ranking = ground_truth.sort_values(ascending=False).index.tolist()
    max_exposure = ground_truth.max()
    relevance = (ground_truth / max_exposure).to_dict() if max_exposure > 0 else {}

    rows = []
    for method, series in method_scores.items():
        series = series.reindex(common_ids).fillna(0.0)
        pred_ranking = series.sort_values(ascending=False).index.tolist()

        rho, _ = spearmanr(series.values, ground_truth.values)
        p_at_k = precision_at_k(pred_ranking, true_ranking, k)
        ndcg = ndcg_at_k(pred_ranking, relevance, k)

        rows.append(
            {
                "method": method,
                "spearman": rho if not np.isnan(rho) else 0.0,
                f"precision_at_{k}": p_at_k,
                f"ndcg_at_{k}": ndcg,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main experiment loop
# ---------------------------------------------------------------------------

def run_experiment(n_seeds, n_runs, k, out_dir):
    warnings.filterwarnings("ignore")
    os.makedirs(out_dir, exist_ok=True)

    print("Loading base synthetic data...")
    df_suppliers, df_products, df_relationships, df_transactions = load_base_data()
    delay_by_supplier, rej_by_supplier = precompute_transaction_arrays(df_transactions)

    print("Building dependency graph and computing PageRank (structure-only, seed-invariant)...")
    G = gr.build_dependency_graph(df_relationships, df_suppliers, df_products)
    df_pagerank = gr.compute_pagerank(G)

    all_rows = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        df_enriched = build_enriched_suppliers(
            df_suppliers, delay_by_supplier, rej_by_supplier, rng
        )
        ground_truth = compute_ground_truth(
            df_enriched, df_relationships, df_products, n_runs=n_runs, seed=seed
        )
        method_scores = compute_method_scores(
            df_suppliers, df_enriched, df_relationships, df_products, df_pagerank, rng
        )
        df_metrics = evaluate_methods(method_scores, ground_truth, k)
        df_metrics["seed"] = seed
        all_rows.append(df_metrics)

        print(f"  seed {seed + 1}/{n_seeds} done "
              f"(composite spearman={df_metrics.set_index('method').loc['composite', 'spearman']:.3f})")

    df_all = pd.concat(all_rows, ignore_index=True)
    df_all.to_csv(os.path.join(out_dir, "eval_results_per_seed.csv"), index=False)

    metric_cols = [c for c in df_all.columns if c not in ("method", "seed")]
    summary_rows = []
    for method in METHODS:
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
    df_summary.to_csv(os.path.join(out_dir, "eval_summary.csv"), index=False)

    print("\n=== Summary (mean +/- 95% CI over {} seeds) ===".format(n_seeds))
    for _, row in df_summary.iterrows():
        parts = [f"{row['method']:<18}"]
        for col in metric_cols:
            parts.append(f"{col}={row[f'{col}_mean']:.4f}+/-{row[f'{col}_ci95']:.4f}")
        print("  " + "  ".join(parts))

    print("\n=== Composite vs. baselines: % improvement + paired Wilcoxon signed-rank test ===")
    sig_rows = []
    composite_vals = {
        col: df_all[df_all["method"] == "composite"].sort_values("seed")[col].to_numpy()
        for col in metric_cols
    }
    for method in METHODS:
        if method == "composite":
            continue
        for col in metric_cols:
            base_vals = df_all[df_all["method"] == method].sort_values("seed")[col].to_numpy()
            comp_vals = composite_vals[col]
            base_mean = base_vals.mean()
            pct_improvement = (
                (comp_vals.mean() - base_mean) / base_mean * 100 if base_mean != 0 else float("nan")
            )
            try:
                stat, p_value = wilcoxon(comp_vals, base_vals)
            except ValueError:
                p_value = float("nan")
            sig_rows.append(
                {
                    "metric": col,
                    "baseline": method,
                    "composite_mean": comp_vals.mean(),
                    "baseline_mean": base_mean,
                    "pct_improvement": pct_improvement,
                    "wilcoxon_p": p_value,
                }
            )
            print(
                f"  [{col}] composite vs {method}: "
                f"{pct_improvement:+.1f}%  (p={p_value:.4g})"
            )
    df_sig = pd.DataFrame(sig_rows)
    df_sig.to_csv(os.path.join(out_dir, "eval_significance.csv"), index=False)

    try:
        plot_results(df_summary, metric_cols, out_dir)
    except Exception as e:
        print(f"(skipping plot: {e})")

    print(f"\nResults written to {out_dir}/")
    return df_all, df_summary, df_sig


def plot_results(df_summary, metric_cols, out_dir):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(metric_cols), figsize=(6 * len(metric_cols), 5))
    if len(metric_cols) == 1:
        axes = [axes]

    df_plot = df_summary.set_index("method").loc[METHODS]
    for ax, col in zip(axes, metric_cols):
        ax.bar(
            df_plot.index,
            df_plot[f"{col}_mean"],
            yerr=df_plot[f"{col}_ci95"],
            capsize=4,
            color="#464c89",
        )
        ax.set_title(col)
        ax.set_ylabel(col)
        ax.tick_params(axis="x", rotation=45)

    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "eval_comparison.png"), dpi=150)
    print(f"Saved figure to {os.path.join(out_dir, 'eval_comparison.png')}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-seeds", type=int, default=30, help="Number of independent bootstrap/simulation draws")
    parser.add_argument("--n-runs", type=int, default=5000, help="Monte Carlo runs per supplier-scenario pair")
    parser.add_argument("--k", type=int, default=10, help="K for Precision@K and NDCG@K")
    parser.add_argument("--out-dir", type=str, default=OUT_DIR, help="Directory to write results")
    args = parser.parse_args()

    run_experiment(n_seeds=args.n_seeds, n_runs=args.n_runs, k=args.k, out_dir=args.out_dir)


if __name__ == "__main__":
    main()
