"""train_ml_models.py — Trains four non-linear/ranking/graph ML models on the
same risk-factor features and ground truth used by learn_weights.py, and
benchmarks them head-to-head against every baseline (including
composite_learned) on the same held-out seeds.

Motivation
----------
Every scoring method up to this point — the hand-set composite, the baselines
in eval_harness.py, and composite_learned in learn_weights.py — is a *linear*
combination of the risk factors in src/scoring.py::FACTOR_NAMES. This script
asks whether a model that can learn non-linear interactions between factors
(gradient-boosted trees, a small neural net), optimizes ranking directly
instead of via a fixed convex-combination form (pairwise learning-to-rank),
or learns its own graph-propagation weights instead of the hand-set damping
in compute_risk_propagation (a graph neural network) does meaningfully
better, using the exact same features, ground truth, and train/test seed
split as learn_weights.py.

Models:
  - gbt : HistGradientBoostingRegressor (sklearn), regresses total P95
          exposure directly.
  - mlp : StandardScaler -> MLPRegressor (sklearn), same regression target.
  - ltr : Pairwise learning-to-rank. For every unordered pair of suppliers
          within a seed with different ground truth, trains a
          (no-intercept) LogisticRegression on the feature difference,
          labeled by which supplier has higher exposure (classic RankSVM/
          pairwise-transform LTR, Burges et al. ICML 2005). At inference,
          score = w . x via `decision_function`, since the classifier's
          boundary is exactly that linear scoring function — this optimizes
          ranking directly, unlike gbt/mlp which regress exposure and rank
          afterwards.
  - gnn : BipartiteGCN (evaluation/gnn_model.py, plain PyTorch) — the same
          supplier<->product message-passing structure as
          compute_risk_propagation, but with every propagation weight
          learned end-to-end instead of hand-set (Kipf & Welling, ICLR 2017,
          adapted to a bipartite two-type graph).

Method
------
1. Reuses learn_weights.py's build_seed_records / FACTOR_NAMES and the same
   disjoint train seeds [0, n_train) / test seeds [n_train, n_train+n_test).
2. Stacks the train seeds' factor rows into one design matrix (X, y) — each
   supplier appears once per train seed, with that seed's bootstrap-derived
   factors and ground truth — and fits gbt/mlp/ltr on it; the gnn trains
   across the same seeds but keeps the graph topology fixed (only node
   features/targets vary per seed — a standard transductive-GNN setup).
3. Also re-fits the linear learn_weights.py grid-search model on the same
   train_records, so composite_learned is included as a comparison point.
4. Evaluates all four ML models + composite_learned + every eval_harness.py
   baseline on the held-out test seeds (Spearman, Precision@K, NDCG@K, paired
   Wilcoxon vs. each baseline per ML model).
5. Picks the winner among the four ML models by mean held-out Spearman and
   persists ONLY that one model (evaluation/results/models/best_model.joblib
   or best_model.pt for gnn + model_manifest.json) — the live API serves one
   model, not four; the comparison lives in the CSVs this script writes.
6. Runs an Isolation Forest anomaly-detection validity diagnostic
   (evaluation/results/anomaly_validity.csv) and computes SHAP feature
   attributions for the winning model (evaluation/results/shap_values.csv).

Usage:
    python evaluation/train_ml_models.py --n-train 20 --n-test 20 --n-runs 5000 --k 10
"""

import argparse
import json
import os
import warnings

import joblib
import numpy as np
import pandas as pd
import torch
from scipy.stats import wilcoxon
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from eval_harness import (
    DATA_DIR,
    METHODS,
    load_base_data,
    precompute_transaction_arrays,
    compute_method_scores,
    evaluate_methods,
)
from learn_weights import build_seed_records, optimize_weights
from explain_model import compute_shap_values
from gnn_model import BipartiteGCN, prepare_product_features, train_gnn, predict_gnn
from src import graph as gr
from src.scoring import FACTOR_NAMES, compute_anomaly_scores

OUT_DIR = os.path.join(os.path.dirname(__file__), "results")
ML_METHODS = ["gbt", "mlp", "ltr", "gnn"]
GNN_HIDDEN_DIM = 16


# ---------------------------------------------------------------------------
# Design matrices
# ---------------------------------------------------------------------------

def stack_records(records):
    """Stacks every train seed's (factors, ground_truth) into one (X, y) pair —
    each supplier contributes one row per seed, with that seed's bootstrap-
    derived factor values and realized exposure."""
    X_parts, y_parts = [], []
    for rec in records:
        factors = rec["factors"]
        gt = rec["ground_truth"].reindex(factors.index).fillna(0.0)
        X_parts.append(factors.to_numpy())
        y_parts.append(gt.to_numpy())
    return np.vstack(X_parts), np.concatenate(y_parts)


def build_pairwise_dataset(records):
    """Pairwise transform for learning-to-rank: for every unordered pair of
    suppliers within a seed whose ground truth differs, emits one training
    example (x_i - x_j, sign(gt_i - gt_j))."""
    X_diff, y_sign = [], []
    for rec in records:
        factors = rec["factors"]
        gt = rec["ground_truth"].reindex(factors.index).fillna(0.0).to_numpy()
        X = factors.to_numpy()
        idx_i, idx_j = np.triu_indices(len(gt), k=1)
        diffs = gt[idx_i] - gt[idx_j]
        keep = diffs != 0
        if not np.any(keep):
            continue
        X_diff.append(X[idx_i[keep]] - X[idx_j[keep]])
        y_sign.append(np.sign(diffs[keep]).astype(int))
    return np.vstack(X_diff), np.concatenate(y_sign)


# ---------------------------------------------------------------------------
# Model training / scoring
# ---------------------------------------------------------------------------

def train_models(train_records, gnn_context, random_state=42):
    X_train, y_train = stack_records(train_records)

    gbt = HistGradientBoostingRegressor(random_state=random_state)
    gbt.fit(X_train, y_train)

    mlp = Pipeline([
        ("scale", StandardScaler()),
        ("mlp", MLPRegressor(hidden_layer_sizes=(32, 16), max_iter=2000, random_state=random_state)),
    ])
    mlp.fit(X_train, y_train)

    X_pair, y_pair = build_pairwise_dataset(train_records)
    ltr = LogisticRegression(fit_intercept=False, max_iter=2000)
    ltr.fit(X_pair, y_pair)

    supplier_ids, product_ids, s2p, p2s, product_features = gnn_context
    gnn = train_gnn(train_records, supplier_ids, product_ids, s2p, p2s, product_features,
                     hidden_dim=GNN_HIDDEN_DIM, random_state=random_state)

    return {"gbt": gbt, "mlp": mlp, "ltr": ltr, "gnn": gnn}


def predict_scores(models, factors, gnn_context):
    """Higher = riskier, same convention as compute_method_scores."""
    X = factors.to_numpy()
    supplier_ids, product_ids, s2p, p2s, product_features = gnn_context
    return {
        "gbt": pd.Series(models["gbt"].predict(X), index=factors.index),
        "mlp": pd.Series(models["mlp"].predict(X), index=factors.index),
        "ltr": pd.Series(models["ltr"].decision_function(X), index=factors.index),
        "gnn": predict_gnn(models["gnn"], factors, supplier_ids, product_ids, s2p, p2s, product_features),
    }


# ---------------------------------------------------------------------------
# Main experiment loop
# ---------------------------------------------------------------------------

def run(n_train, n_test, n_runs, k, out_dir, random_state=42):
    warnings.filterwarnings("ignore")
    os.makedirs(out_dir, exist_ok=True)
    models_dir = os.path.join(out_dir, "models")
    os.makedirs(models_dir, exist_ok=True)

    print("Loading base synthetic data...")
    df_suppliers, df_products, df_relationships, df_transactions = load_base_data()
    delay_by_supplier, rej_by_supplier = precompute_transaction_arrays(df_transactions)

    print("Building dependency graph / PageRank (structure-only)...")
    G = gr.build_dependency_graph(df_relationships, df_suppliers, df_products)
    df_pagerank = gr.compute_pagerank(G)

    supplier_ids, product_ids, s2p, p2s = gr.build_bipartite_matrices(G)
    product_features = prepare_product_features(df_products, product_ids)
    gnn_context = (supplier_ids, product_ids, s2p, p2s, product_features)

    train_seeds = list(range(0, n_train))
    test_seeds = list(range(n_train, n_train + n_test))

    print(f"\nPreparing {n_train} TRAIN seeds...")
    train_records = build_seed_records(train_seeds, df_suppliers, df_products, df_relationships, G,
                                        delay_by_supplier, rej_by_supplier, n_runs, "train")
    print(f"\nPreparing {n_test} TEST seeds (held-out, disjoint from train)...")
    test_records = build_seed_records(test_seeds, df_suppliers, df_products, df_relationships, G,
                                       delay_by_supplier, rej_by_supplier, n_runs, "test")

    print("\nFitting the linear learn_weights.py grid-search model (comparison point)...")
    learned_weights, _ = optimize_weights(train_records)
    w = np.array([learned_weights[f] for f in FACTOR_NAMES])

    print("\nTraining ML models (gbt, mlp, ltr, gnn) on stacked TRAIN seeds...")
    models = train_models(train_records, gnn_context, random_state=random_state)

    print("\nEvaluating ML models + composite_learned + every baseline on HELD-OUT test seeds...")
    all_rows = []
    for rec in test_records:
        rng = np.random.default_rng(rec["seed"] + 200000)
        method_scores = compute_method_scores(
            df_suppliers, rec["df_enriched"], df_relationships, df_products, df_pagerank, G, rng
        )
        method_scores["composite_learned"] = pd.Series(
            rec["factors"].to_numpy() @ w, index=rec["factors"].index
        )
        method_scores.update(predict_scores(models, rec["factors"], gnn_context))

        df_metrics = evaluate_methods(method_scores, rec["ground_truth"], k)
        df_metrics["seed"] = rec["seed"]
        all_rows.append(df_metrics)

    df_all = pd.concat(all_rows, ignore_index=True)
    df_all.to_csv(os.path.join(out_dir, "ml_models_test_results.csv"), index=False)

    all_methods = METHODS + ["composite_learned"] + ML_METHODS
    metric_cols = [c for c in df_all.columns if c not in ("method", "seed")]

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
    df_summary.to_csv(os.path.join(out_dir, "ml_models_summary.csv"), index=False)

    print(f"\n=== Held-out test summary (mean +/- 95% CI over {n_test} seeds) ===")
    for _, row in df_summary.iterrows():
        parts = [f"{row['method']:<20}"]
        for col in metric_cols:
            parts.append(f"{col}={row[f'{col}_mean']:.4f}+/-{row[f'{col}_ci95']:.4f}")
        print("  " + "  ".join(parts))

    print("\n=== Each ML model vs. every baseline (% improvement + paired Wilcoxon) ===")
    sig_rows = []
    for ml_method in ML_METHODS:
        ml_vals = {
            col: df_all[df_all["method"] == ml_method].sort_values("seed")[col].to_numpy()
            for col in metric_cols
        }
        for baseline in all_methods:
            if baseline == ml_method:
                continue
            for col in metric_cols:
                base_vals = df_all[df_all["method"] == baseline].sort_values("seed")[col].to_numpy()
                base_mean = base_vals.mean()
                pct = (
                    (ml_vals[col].mean() - base_mean) / base_mean * 100
                    if base_mean != 0 else float("nan")
                )
                try:
                    _, p_value = wilcoxon(ml_vals[col], base_vals)
                except ValueError:
                    p_value = float("nan")
                sig_rows.append({
                    "ml_method": ml_method, "metric": col, "baseline": baseline,
                    "ml_mean": ml_vals[col].mean(), "baseline_mean": base_mean,
                    "pct_improvement": pct, "wilcoxon_p": p_value,
                })
                print(f"  [{col}] {ml_method} vs {baseline}: {pct:+.1f}%  (p={p_value:.4g})")
    df_sig = pd.DataFrame(sig_rows)
    df_sig.to_csv(os.path.join(out_dir, "ml_models_significance.csv"), index=False)

    print("\nComputing anomaly-detection validity diagnostic "
          "(Isolation Forest on operational features, independent of the supervised score)...")
    anomaly_rows = []
    for rec in test_records:
        df_anom = compute_anomaly_scores(rec["df_enriched"])
        gt = rec["ground_truth"].reindex(df_anom["supplier_id"]).fillna(0.0)
        is_anom = df_anom["is_anomalous"].to_numpy()
        anomaly_rows.append({
            "seed": rec["seed"],
            "n_anomalous": int(is_anom.sum()),
            "anomalous_mean_exposure": float(gt[is_anom].mean()) if is_anom.any() else float("nan"),
            "normal_mean_exposure": float(gt[~is_anom].mean()) if (~is_anom).any() else float("nan"),
        })
    df_anomaly = pd.DataFrame(anomaly_rows)
    df_anomaly.to_csv(os.path.join(out_dir, "anomaly_validity.csv"), index=False)
    anomaly_ratio = df_anomaly["anomalous_mean_exposure"].mean() / df_anomaly["normal_mean_exposure"].mean()
    print(f"Anomalous suppliers' mean P95 exposure is {anomaly_ratio:.2f}x normal suppliers', "
          f"averaged over {n_test} held-out test seeds "
          "(a validity check, not a ranking benchmark — anomaly detection answers a different "
          "question than the supervised models above).")

    spearman_by_method = df_summary.set_index("method")["spearman_mean"]
    winner = spearman_by_method.loc[ML_METHODS].idxmax()
    print(f"\nWinner among {ML_METHODS} by held-out mean Spearman: "
          f"{winner} (spearman={spearman_by_method[winner]:.4f})")

    if winner == "gnn":
        torch.save(models[winner].state_dict(), os.path.join(models_dir, "best_model.pt"))
        model_type = "torch"
    else:
        joblib.dump(models[winner], os.path.join(models_dir, "best_model.joblib"))
        model_type = "sklearn"

    winner_row = df_summary.set_index("method").loc[winner]
    manifest = {
        "model_name": winner,
        "model_type": model_type,
        "feature_order": FACTOR_NAMES,
        "test_spearman": float(winner_row["spearman_mean"]),
        f"test_precision_at_{k}": float(winner_row[f"precision_at_{k}_mean"]),
        f"test_ndcg_at_{k}": float(winner_row[f"ndcg_at_{k}_mean"]),
        "anomaly_exposure_ratio": float(anomaly_ratio),
    }
    if model_type == "torch":
        manifest["gnn_arch"] = {
            "supplier_dim": len(FACTOR_NAMES),
            "product_dim": product_features.shape[1],
            "hidden_dim": GNN_HIDDEN_DIM,
        }
        manifest["gnn_y_scale"] = float(models[winner]._y_scale)
    with open(os.path.join(models_dir, "model_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print("\nComputing SHAP feature attributions for the winning model "
          f"({winner}, evaluation/results/shap_values.csv)...")
    shap_gnn_context = (
        (supplier_ids, product_ids, s2p, p2s, product_features, test_records[0]["factors"])
        if winner == "gnn" else None
    )
    df_shap = compute_shap_values(models[winner], winner, test_records[0]["factors"],
                                   gnn_context=shap_gnn_context)
    df_shap.to_csv(os.path.join(out_dir, "shap_values.csv"))

    print(f"\nResults written to {out_dir}/, winning model persisted to {models_dir}/")
    return models, df_summary, df_sig, manifest


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
