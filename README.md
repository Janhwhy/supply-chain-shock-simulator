# ShockProof — Supply Chain Shock Simulator

A supply-chain resilience analytics platform: a Monte Carlo disruption simulator provides
ground-truth financial exposure per supplier, and a battery of risk-scoring methods — from a
hand-set scorecard up through gradient-boosted trees and a graph neural network — are benchmarked
against that ground truth with the same rigor a research paper would use (held-out seeds, paired
significance tests, an empirical noise ceiling). Results are served through a FastAPI backend and
a React dashboard.

## Architecture

```
data/                  synthetic data generation + Postgres schema
  generate_synthetic_data.py   seeds suppliers / products / supply_relationships / transactions
  schema.sql                   full Postgres schema (raw + derived tables)

notebooks/              the analytical pipeline, run in order (00 → 05)
  00_data_calibration          calibrates synthetic-data parameters against a real reference dataset
  01_etl_pipeline               computes avg_delay_days / delay_volatility / rejection_rate / reliability_score
  02_graph_construction         builds the supplier↔product dependency graph, PageRank
  03_monte_carlo_engine         runs the disruption simulations → simulation_results (ground truth)
  04_resilience_scoring         computes the composite resilience scorecard → resilience_scores
  05_business_outputs           priority matrix + mitigation playbook → risk_priority_matrix, mitigation_playbook

src/                     the reusable analytical library (imported by everything below)
  db.py                        Postgres connection / read_table / write_dataframe
  scenarios.py                 the 5 disruption scenario definitions
  simulation.py                Monte Carlo engine (also used live by the API)
  graph.py                     dependency graph, PageRank, centrality, risk propagation, bipartite matrices
  scoring.py                   every risk factor, the composite scorecard, risk-factor matrix, anomaly detection
  playbook.py                  mitigation action catalogue, ROI, playbook generation

evaluation/               offline research scripts — benchmark every method against Monte Carlo ground truth
  eval_harness.py              baselines vs. the hand-set composite (Spearman / Precision@K / NDCG@K, Wilcoxon)
  learn_weights.py             fits the scorecard weights to data instead of hand-picking them
  ceiling_check.py             empirical noise ceiling (how good can *any* model get, given simulation randomness)
  train_ml_models.py           trains & benchmarks gbt / mlp / ltr / gnn, persists the winner for the live API
  gnn_model.py                 the graph neural network (BipartiteGCN, plain PyTorch)
  explain_model.py             SHAP feature attribution for the winning model
  results/                     every run's output CSVs, plots, and the persisted live model + manifest

api/main.py                FastAPI app — serves all of the above live over REST
app/                        React + Vite dashboard

tests/                      pytest suite for src/ and evaluation/gnn_model.py (run: `pytest`)
```

## The four novelties

Ground truth throughout is *total P95 revenue-at-risk*: for each supplier, the Monte Carlo engine
(`src/simulation.py`) draws disruption scenarios and reports the realized 95th-percentile loss,
summed across 5 scenario types. Every scoring method below is a *cheap* proxy computed without
looking at that ground truth, then benchmarked against it on held-out seeds.

| # | Novelty | What's new | Held-out result |
|---|---|---|---|
| 1 | **Network risk propagation** (`src/graph.py::compute_risk_propagation`) | Diffuses each supplier's risk across the bipartite supplier↔product graph — a supplier sharing a product with risky co-suppliers inherits correlated exposure that no single-supplier factor previously captured. | Spearman 0.456 standalone (`propagation_only`) |
| 2 | **Graph Neural Network** (`evaluation/gnn_model.py::BipartiteGCN`) | Same idea as #1, but every propagation weight is *learned* end-to-end (Kipf & Welling-style bipartite GCN, plain PyTorch, no PyG dependency) instead of hand-set. | Spearman 0.973 |
| 3 | **Explainable AI** (`evaluation/explain_model.py`) | SHAP feature attribution for the live model, including a graph-aware explainer for the GNN case — answers *why* a supplier is risky, not just *how much*. | Live in `/api/suppliers/{id}` as `top_risk_factors` |
| 4 | **Unsupervised anomaly detection** (`src/scoring.py::compute_anomaly_scores`) | Isolation Forest on raw operational behavior (delay/volatility/rejection) — a signal that never looks at the supervised ground truth at all. | Independent early-warning flag, not a ranking metric |

Full benchmark (20 held-out test seeds, 5,000 Monte Carlo runs/seed):

| Method | Spearman | Precision@10 |
|---|---|---|
| hand-set composite scorecard | −0.048 | 0.000 |
| PageRank alone | 0.000 | 0.125 |
| learned linear weights (6-factor grid search) | 0.999 | 0.965 |
| MLP | 0.730 | 0.745 |
| pairwise learning-to-rank | 0.995 | 0.925 |
| **graph neural network** | **0.973** | **0.910** |
| **gradient-boosted trees — live model** | **0.9995** | **0.960** |
| *empirical noise ceiling* | *0.9994* | *0.980* |

`gbt` wins and sits at the empirical noise ceiling — there is no more headroom left to gain on
this metric from a better model architecture. Full numbers, per-seed data, and significance tests
are in `evaluation/results/`.

## Running it

**1. Database**
```bash
docker compose up -d
docker exec -i shockproof_db psql -U postgres -d shockproof < data/schema.sql
python data/generate_synthetic_data.py
```
Then run `notebooks/00` through `notebooks/05` in order to populate the derived tables
(`suppliers_enriched`, `simulation_results`, `resilience_scores`, `risk_priority_matrix`,
`mitigation_playbook`).

**2. Train the live ML model** (writes `evaluation/results/models/`, loaded by the API at startup)
```bash
pip install -r requirements.txt
python evaluation/train_ml_models.py --n-train 20 --n-test 20 --n-runs 5000
```

**3. API**
```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**4. Frontend**
```bash
cd app
npm install
npm run dev
```

**5. Tests**
```bash
pytest
```

## Re-running the research

Each script in `evaluation/` is independently runnable and writes its own CSVs/plots to
`evaluation/results/`:
```bash
python evaluation/eval_harness.py --n-seeds 30 --n-runs 5000     # baselines vs. composite
python evaluation/learn_weights.py --n-train 20 --n-test 20      # learned linear weights
python evaluation/ceiling_check.py --n-seeds 20                  # noise ceiling
python evaluation/train_ml_models.py --n-train 20 --n-test 20    # gbt/mlp/ltr/gnn + SHAP + anomaly diagnostic
```
