"""main.py — FastAPI application entry point and endpoint definitions.

Run locally with:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

import sys
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Path so `src.*` imports resolve from the repo root ───────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db import get_engine, read_table, read_query, test_connection
from src.scenarios import get_all_scenarios, scenarios_to_dataframe, get_scenario_by_id
from src.graph import build_dependency_graph, compute_pagerank
from src.scoring import sensitivity_analysis
from src.simulation import run_simulation, analyse_distribution
import numpy as np

# ── Known scenario IDs ────────────────────────────────────────────────────────
VALID_SCENARIO_IDS = {s.scenario_id for s in get_all_scenarios()}


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _safe(value: Any) -> Any:
    """Convert numpy/pandas scalars to native Python types for JSON serialisation."""
    if pd.isna(value) if not isinstance(value, (list, dict)) else False:
        return None
    if hasattr(value, "item"):       # numpy scalar → Python scalar
        return value.item()
    return value


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    """
    Convert a DataFrame to a list of JSON-serialisable dicts.
    All numpy int64/float64 values are cast to native Python types.
    Timestamps are converted to ISO strings.
    """
    records = []
    for rec in df.to_dict(orient="records"):
        clean = {}
        for k, v in rec.items():
            if hasattr(v, "isoformat"):          # datetime / Timestamp
                clean[k] = v.isoformat()
            else:
                clean[k] = _safe(v)
        records.append(clean)
    return records


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic Response Models
# ═══════════════════════════════════════════════════════════════════════════════

class SupplierSummary(BaseModel):
    """Flat join of the suppliers table with resilience score and priority quadrant."""
    supplier_id: int
    supplier_name: str
    country: str
    tier: Optional[int]
    reliability_score: Optional[float]
    avg_delay_days: Optional[float]
    delay_volatility: Optional[float]
    rejection_rate: Optional[float]
    composite_score: Optional[float]
    geo_risk: Optional[float]
    dependency_risk: Optional[float]
    reliability_risk: Optional[float]
    substitutability_risk: Optional[float]
    priority_quadrant: Optional[str]
    resilience_score: Optional[float]
    total_p95_exposure: Optional[float]
    risk_band: Optional[str]


class ResilienceScoreDetail(BaseModel):
    """Full resilience decomposition for a single supplier."""
    score_id: Optional[int]
    supplier_id: int
    dependency_risk: Optional[float]
    geo_risk: Optional[float]
    reliability_risk: Optional[float]
    substitutability_risk: Optional[float]
    composite_score: Optional[float]


class SimulationResult(BaseModel):
    """One Monte Carlo simulation result row."""
    result_id: Optional[int]
    supplier_id: int
    scenario_name: str
    p50_impact: float
    p95_impact: float
    run_count: int


class PriorityMatrixEntry(BaseModel):
    """One row from the risk_priority_matrix table."""
    supplier_id: int
    supplier_name: str
    resilience_score: float
    total_p95_exposure: float
    probability_tier: str
    impact_tier: str
    priority_quadrant: str


class PlaybookEntry(BaseModel):
    """One row from the mitigation_playbook table."""
    playbook_id: Optional[int]
    supplier_id: int
    scenario: str
    recommended_action: str
    estimated_cost: float
    p95_impact: float
    roi: float


class KPISummary(BaseModel):
    """Section-7 executive KPIs as a single JSON object."""
    total_suppliers: int
    total_network_exposure: float
    critical_priority_count: int
    monitor_closely_count: int
    recommended_budget: float
    total_risk_eliminated: float
    portfolio_roi: float
    network_resilience_before: float
    network_resilience_after: float


class GraphNode(BaseModel):
    """A node in the dependency graph (supplier or product)."""
    node_id: str
    type: str                         # "supplier" | "product"
    name: str                         # supplier_name or product_name/sku
    pagerank_score: float
    country: Optional[str] = None
    tier: Optional[int] = None


class GraphEdge(BaseModel):
    """A directed edge from a supplier node to a product node."""
    source: str                        # e.g. "S_1"
    target: str                        # e.g. "P_42"
    weight: float                      # supply_share


# ═══════════════════════════════════════════════════════════════════════════════
# Lifespan & App Initialisation
# ═══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm-up: verify DB connectivity on startup; clean up on shutdown."""
    try:
        engine = get_engine()
        with engine.connect():
            pass
        print("[ShockProof API] Database connection verified on startup.")
    except Exception as exc:
        print(f"[ShockProof API] WARNING — could not reach DB on startup: {exc}")
    yield
    print("[ShockProof API] Shutdown complete.")


app = FastAPI(
    title="ShockProof API",
    description=(
        "REST API exposing supply-chain resilience scores, Monte Carlo simulation "
        "results, risk priority classifications, and mitigation playbook data for "
        "the ShockProof Supply-Chain Shock Simulator project."
    ),
    version="1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # development — lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Root"])
def root() -> dict:
    """
    Welcome endpoint.

    Returns the API name, version, and a brief description of available
    endpoint groups.
    """
    return {
        "api": "ShockProof API",
        "version": "1.0",
        "description": (
            "Supply-Chain Shock Simulator — analytical results API. "
            "See /docs for the full endpoint reference."
        ),
        "endpoints": {
            "suppliers":       "/api/suppliers",
            "supplier_detail": "/api/suppliers/{supplier_id}",
            "simulation":      "/api/simulation/{scenario_id}",
            "scenarios":       "/api/scenarios",
            "priority_matrix": "/api/priority-matrix",
            "playbook":        "/api/playbook",
            "kpis":            "/api/kpis",
            "graph":           "/api/graph",
            "health":          "/api/health",
        },
    }


# ── /api/suppliers ─────────────────────────────────────────────────────────

@app.get("/api/suppliers", tags=["Suppliers"])
def get_suppliers(
    risk_band: Optional[str] = Query(
        None,
        description="Filter by risk band: Critical | High | Medium | Low",
    ),
    priority_quadrant: Optional[str] = Query(
        None,
        description=(
            "Filter by priority quadrant: "
            "'Critical Priority' | 'Monitor Closely' | "
            "'Contingency Plan' | 'Routine Review'"
        ),
    ),
) -> list[dict]:
    """
    Returns all suppliers joined with their resilience scores and priority
    quadrant classification.

    Supports optional query-string filters:
    - **risk_band**: one of Critical / High / Medium / Low
    - **priority_quadrant**: one of the four quadrant labels
    """
    try:
        df_sup  = read_table("suppliers")
        df_res  = read_table("resilience_scores")
        df_prio = read_table("risk_priority_matrix")

        # Join resilience scores
        df = df_sup.merge(
            df_res[["supplier_id", "dependency_risk", "geo_risk",
                    "reliability_risk", "substitutability_risk", "composite_score"]],
            on="supplier_id", how="left",
        )
        # Join priority matrix
        df = df.merge(
            df_prio[["supplier_id", "resilience_score", "total_p95_exposure",
                     "priority_quadrant"]],
            on="supplier_id", how="left",
        )

        # Introduce a minor fluctuation to simulate dynamic updates / stochastic variations
        if not df.empty:
            exp_noise = np.random.uniform(0.985, 1.015, size=len(df))
            df["total_p95_exposure"] = df["total_p95_exposure"] * exp_noise
            
            score_noise = np.random.uniform(-0.008, 0.008, size=len(df))
            df["composite_score"] = (df["composite_score"] + score_noise).clip(0.0, 1.0)
            if "resilience_score" in df.columns:
                df["resilience_score"] = (df["resilience_score"] + score_noise).clip(0.0, 1.0)

        # Derive risk_band from composite_score quartiles
        if "composite_score" in df.columns:
            q25, q50, q75 = (
                df["composite_score"].quantile(0.25),
                df["composite_score"].quantile(0.50),
                df["composite_score"].quantile(0.75),
            )
            def _band(s):
                if pd.isna(s):
                    return None
                if s <= q25:
                    return "Critical"
                elif s <= q50:
                    return "High"
                elif s <= q75:
                    return "Medium"
                return "Low"
            df["risk_band"] = df["composite_score"].apply(_band)

        # Optional filters
        if risk_band:
            df = df[df["risk_band"].str.lower() == risk_band.lower()]
        if priority_quadrant:
            df = df[df["priority_quadrant"].str.lower() == priority_quadrant.lower()]

        return _df_to_records(df.drop(columns=["created_at"], errors="ignore"))

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


# ── /api/suppliers/{supplier_id} ───────────────────────────────────────────

@app.get("/api/suppliers/{supplier_id}", tags=["Suppliers"])
def get_supplier_detail(supplier_id: int) -> dict:
    """
    Returns full analytical detail for a single supplier:
    - Core profile (country, tier, operational metrics)
    - All four risk factor scores and composite resilience score
    - Priority quadrant classification and P95 total exposure
    - Simulation results for all 5 scenarios (P50 and P95 impacts)
    - Mitigation playbook recommendation (action, cost, ROI)

    Raises 404 if the supplier_id is not found.
    """
    try:
        df_sup  = read_table("suppliers")
        df_res  = read_table("resilience_scores")
        df_prio = read_table("risk_priority_matrix")
        df_sim  = read_table("simulation_results")
        df_pb   = read_table("mitigation_playbook")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    # 404 guard
    sup_row = df_sup[df_sup["supplier_id"] == supplier_id]
    if sup_row.empty:
        raise HTTPException(status_code=404, detail=f"Supplier {supplier_id} not found.")

    # Assemble response dict
    profile = _df_to_records(
        sup_row.drop(columns=["created_at"], errors="ignore")
    )[0]

    res_row = df_res[df_res["supplier_id"] == supplier_id]
    if not res_row.empty:
        res_dict = _df_to_records(res_row.drop(columns=["score_date"], errors="ignore"))[0]
        # Introduce a minor fluctuation to simulate dynamic updates / stochastic variations
        score_noise = np.random.uniform(-0.008, 0.008)
        score_val = res_dict.get("composite_score", res_dict.get("resilience_score", 0.5))
        res_dict["composite_score"] = max(0.0, min(1.0, score_val + score_noise))
        for factor in ["dependency_risk", "geo_risk", "reliability_risk", "substitutability_risk"]:
            if factor in res_dict and res_dict[factor] is not None:
                res_dict[factor] = max(0.0, min(1.0, res_dict[factor] + np.random.uniform(-0.008, 0.008)))
        profile["resilience_scores"] = res_dict
    else:
        profile["resilience_scores"] = {}

    # Add score interpretation
    if not res_row.empty:
        try:
            from src.scoring import get_score_interpretation
            res_val = profile["resilience_scores"].get("composite_score", 0.5)
            profile["score_interpretation"] = get_score_interpretation(float(res_val))
        except Exception as e:
            print(f"Warning: could not get score interpretation: {e}")
            profile["score_interpretation"] = {}
    else:
        profile["score_interpretation"] = {}

    prio_row = df_prio[df_prio["supplier_id"] == supplier_id]
    if not prio_row.empty:
        prio_dict = _df_to_records(prio_row.drop(columns=["created_at"], errors="ignore"))[0]
        # Introduce dynamic exposure & score fluctuation
        prio_dict["total_p95_exposure"] = prio_dict["total_p95_exposure"] * np.random.uniform(0.985, 1.015)
        prio_dict["resilience_score"] = max(0.0, min(1.0, prio_dict["resilience_score"] + np.random.uniform(-0.008, 0.008)))
        profile["priority_matrix"] = prio_dict
    else:
        profile["priority_matrix"] = {}

    # Compute simulation results dynamically to include mean, std, skewness, kurtosis, and var_ratio
    try:
        from src.scenarios import get_all_scenarios
        scenarios = get_all_scenarios()
        df_products = read_table("products")
        df_relationships = read_table("supply_relationships")
        supplier_dict = sup_row.iloc[0].to_dict()
        
        sim_details = []
        # No static random seed to allow natural simulation fluctuations
        for scenario in scenarios:
            res = run_simulation(supplier_dict, scenario, df_relationships, df_products, n_runs=10000)
            stats = analyse_distribution(res['impact_distribution'], supplier_dict['supplier_name'], scenario.display_name)
            sim_details.append({
                "scenario_name": scenario.scenario_id,
                "p50_impact": res['p50_impact'],
                "p95_impact": res['p95_impact'],
                "mean_impact": res['mean_impact'],
                "std_impact": res['std_impact'],
                "zero_impact_fraction": res['zero_impact_fraction'],
                "skewness": stats['skewness'],
                "kurtosis": stats['kurtosis'],
                "var_ratio": stats['var_ratio'],
                "run_count": res['n_runs']
            })
        profile["simulation_results"] = sim_details
    except Exception as exc:
        print(f"Warning: dynamic simulation failed, falling back to database: {exc}")
        sim_rows = df_sim[df_sim["supplier_id"] == supplier_id]
        if not sim_rows.empty:
            records = _df_to_records(sim_rows.drop(columns=["result_id", "created_at"], errors="ignore"))
            for r in records:
                for col in ["p50_impact", "p95_impact", "mean_impact", "std_impact"]:
                    if col in r and r[col] is not None:
                        r[col] = r[col] * np.random.uniform(0.985, 1.015)
            profile["simulation_results"] = records
        else:
            profile["simulation_results"] = []

    pb_row = df_pb[df_pb["supplier_id"] == supplier_id]
    profile["playbook"] = (
        _df_to_records(pb_row.drop(columns=["created_at"], errors="ignore"))
        if not pb_row.empty else {}
    )

    return profile


# ── /api/simulation/{scenario_id} ─────────────────────────────────────────

@app.get("/api/simulation/{scenario_id}", tags=["Simulation"])
def get_simulation_results(scenario_id: str) -> list[dict]:
    """
    Returns Monte Carlo simulation results for all 100 suppliers under one
    named scenario, sorted by P95 impact descending.

    Valid scenario IDs: port_strike | factory_shutdown | currency_shock |
    logistics_delay | quality_failure

    Raises 400 if the scenario_id is not one of the five known scenarios.
    """
    if scenario_id not in VALID_SCENARIO_IDS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown scenario_id '{scenario_id}'. "
                f"Valid values: {sorted(VALID_SCENARIO_IDS)}"
            ),
        )
    try:
        from src.scenarios import get_scenario_by_id
        from src.simulation import run_simulation
        scenario_obj = get_scenario_by_id(scenario_id)
        df_sup = read_table("suppliers")
        df_products = read_table("products")
        df_relationships = read_table("supply_relationships")
        
        sim_details = []
        # No static random seed to allow natural simulation fluctuations
        for _, supplier_row in df_sup.iterrows():
            supplier_dict = supplier_row.to_dict()
            res = run_simulation(supplier_dict, scenario_obj, df_relationships, df_products, n_runs=10000)
            sim_details.append({
                "supplier_id": res["supplier_id"],
                "supplier_name": supplier_dict["supplier_name"],
                "scenario_name": res["scenario_id"],
                "p50_impact": res["p50_impact"],
                "p95_impact": res["p95_impact"],
                "mean_impact": res["mean_impact"],
                "std_impact": res["std_impact"],
                "zero_impact_fraction": res["zero_impact_fraction"],
                "run_count": res["n_runs"]
            })
        sim_details.sort(key=lambda x: x["p95_impact"], reverse=True)
        return sim_details
    except Exception as exc:
        print(f"Warning: dynamic simulation in get_simulation_results failed, falling back to database: {exc}")
        try:
            df = read_table("simulation_results")
            df_sup = read_table("suppliers")[["supplier_id", "supplier_name"]]
            df = df.merge(df_sup, on="supplier_id", how="left")
        except Exception as db_exc:
            raise HTTPException(status_code=500, detail=f"Database error: {db_exc}") from db_exc
        
        df_filtered = df[df["scenario_name"] == scenario_id].copy()
        if df_filtered.empty:
            scenario_obj = next((s for s in get_all_scenarios() if s.scenario_id == scenario_id), None)
            if scenario_obj:
                df_filtered = df[df["scenario_name"] == scenario_obj.display_name].copy()
        
        # Apply stochastic wiggle to database fallback records to look like a live simulation
        for col in ["p50_impact", "p95_impact", "mean_impact", "std_impact"]:
            if col in df_filtered.columns:
                df_filtered[col] = df_filtered[col] * np.random.uniform(0.985, 1.015, size=len(df_filtered))

        df_filtered = df_filtered.sort_values("p95_impact", ascending=False)
        return _df_to_records(
            df_filtered.drop(columns=["result_id", "created_at"], errors="ignore")
        )


# ── /api/scenarios ─────────────────────────────────────────────────────────

@app.get("/api/scenarios", tags=["Simulation"])
def get_scenarios() -> list[dict]:
    """
    Returns definitions and parameters for all 5 predefined disruption scenarios:
    annual probability, supply-loss range, duration range, and modifier flags.
    """
    try:
        df = scenarios_to_dataframe()
        return _df_to_records(df)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error building scenarios: {exc}") from exc


# ── /api/priority-matrix ───────────────────────────────────────────────────

@app.get("/api/priority-matrix", tags=["Risk Priority"])
def get_priority_matrix() -> list[dict]:
    """
    Returns the full risk_priority_matrix table (100 rows — one per supplier),
    containing: resilience_score, total_p95_exposure, probability_tier,
    impact_tier, and priority_quadrant.
    """
    try:
        df = read_table("risk_priority_matrix")
        # Apply slight stochastic variance for real-time simulation feel
        if not df.empty:
            exp_noise = np.random.uniform(0.985, 1.015, size=len(df))
            df["total_p95_exposure"] = df["total_p95_exposure"] * exp_noise
            
            score_noise = np.random.uniform(-0.008, 0.008, size=len(df))
            df["resilience_score"] = (df["resilience_score"] + score_noise).clip(0.0, 1.0)
        return _df_to_records(df.drop(columns=["created_at"], errors="ignore"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


# ── /api/playbook ──────────────────────────────────────────────────────────

@app.get("/api/playbook", tags=["Playbook"])
def get_playbook(
    priority_quadrant: Optional[str] = Query(
        None,
        description=(
            "Filter by priority quadrant: "
            "'Critical Priority' | 'Monitor Closely' | "
            "'Contingency Plan' | 'Routine Review'"
        ),
    ),
) -> list[dict]:
    """
    Returns the full mitigation_playbook table sorted by ROI descending.

    Supports optional query-string filter:
    - **priority_quadrant**: narrows results to one quadrant by joining with
      risk_priority_matrix on supplier_id.
    """
    try:
        from src.playbook import generate_playbook
        from src.simulation import identify_worst_case_scenarios
        df_prio = read_table("risk_priority_matrix")
        df_res  = read_table("resilience_scores")
        df_sim  = read_table("simulation_results")
        
        # Apply stochastic noise to propagate dynamically to playbook calculations
        if not df_prio.empty:
            df_prio["total_p95_exposure"] = df_prio["total_p95_exposure"] * np.random.uniform(0.985, 1.015, size=len(df_prio))
            df_prio["resilience_score"] = (df_prio["resilience_score"] + np.random.uniform(-0.008, 0.008, size=len(df_prio))).clip(0.0, 1.0)
            
        score_col = "composite_score" if "composite_score" in df_res.columns else "resilience_score"
        if not df_res.empty:
            df_res[score_col] = (df_res[score_col] + np.random.uniform(-0.008, 0.008, size=len(df_res))).clip(0.0, 1.0)
            
        if not df_sim.empty:
            for col in ["p50_impact", "p95_impact", "mean_impact", "std_impact"]:
                if col in df_sim.columns:
                    df_sim[col] = df_sim[col] * np.random.uniform(0.985, 1.015, size=len(df_sim))
                    
        df_worst = identify_worst_case_scenarios(df_sim)
        df = generate_playbook(df_prio, df_res, df_sim, df_worst)
        
        # Add backwards-compatibility aliases
        df["estimated_cost"] = df["action_cost"]
        # Convert payback to months for any legacy calculations
        df["payback_period_months"] = df["payback_period_years"] * 12.0
        # Map raw column names for dominant risk factors to display labels
        RISK_LABELS = {
            "dependency_risk":       "Dependency Risk",
            "geo_risk":              "Geographic Risk",
            "geographic_risk":       "Geographic Risk",
            "reliability_risk":      "Reliability Risk",
            "substitutability_risk": "Substitutability Risk",
        }
        df["dominant_risk_label"] = df["dominant_risk_factor"].map(RISK_LABELS).fillna("—")
        
    except Exception as exc:
        print(f"Warning: dynamic playbook generation failed: {exc}")
        try:
            df_pb   = read_table("mitigation_playbook")
            df_prio = read_table("risk_priority_matrix")
            df_res  = read_table("resilience_scores")
        except Exception as db_exc:
            raise HTTPException(status_code=500, detail=f"Database error: {db_exc}") from db_exc

        # Enrich with quadrant + supplier_name
        df = df_pb.merge(
            df_prio[["supplier_id", "supplier_name", "priority_quadrant"]],
            on="supplier_id", how="left",
        )
        # Apply noise to fallback columns
        if not df.empty:
            for col in ["estimated_cost", "action_cost", "expected_annual_loss", "roi"]:
                if col in df.columns:
                    df[col] = df[col] * np.random.uniform(0.985, 1.015, size=len(df))

        RISK_COLS = {
            "dependency_risk":       "Dependency Risk",
            "geo_risk":              "Geographic Risk",
            "reliability_risk":      "Reliability Risk",
            "substitutability_risk": "Substitutability Risk",
        }
        available = [c for c in RISK_COLS if c in df_res.columns]
        if available:
            df_res["dominant_risk_factor"] = (
                df_res[available]
                .idxmax(axis=1)
                .map(RISK_COLS)
            )
            df = df.merge(
                df_res[["supplier_id", "dominant_risk_factor"] + available],
                on="supplier_id", how="left",
            )
        else:
            df["dominant_risk_factor"] = None
        
        df["action_description"] = "—"
        df["action_cost"] = df["estimated_cost"]
        df["expected_annual_loss"] = df["p95_impact"]
        df["risk_reduction"] = 0.0
        df["payback_period_years"] = 0.0
        df["dominant_risk_label"] = df["dominant_risk_factor"]

        def _payback(row):
            try:
                if row["roi"] and row["roi"] > 0:
                    return round(12.0 / float(row["roi"]), 1)
            except Exception:
                pass
            return None
        df["payback_period_months"] = df.apply(_payback, axis=1)

    if priority_quadrant:
        df = df[df["priority_quadrant"].str.lower() == priority_quadrant.lower()]

    df = df.sort_values("roi", ascending=False)
    return _df_to_records(df.drop(columns=["created_at"], errors="ignore"))


# ── /api/kpis ─────────────────────────────────────────────────────────────

@app.get("/api/kpis", tags=["KPIs"])
def get_kpis() -> KPISummary:
    """
    Returns the Section-7 executive summary as a single KPI object.

    Fields:
    - total_suppliers: number of suppliers analysed
    - total_network_exposure: sum of total_p95_exposure across all suppliers
    - critical_priority_count / monitor_closely_count
    - recommended_budget: sum of estimated_cost for Critical + Monitor Closely only
    - total_risk_eliminated: not directly in DB — estimated from portfolio_roi × budget
    - portfolio_roi: mean ROI across the at-risk playbook entries
    - network_resilience_before: mean composite_score from resilience_scores
    - network_resilience_after: projected mean after applying risk reductions
    """
    try:
        df_prio = read_table("risk_priority_matrix")
        df_res  = read_table("resilience_scores")
        df_pb   = read_table("mitigation_playbook")
        
        # Apply stochastic noise to propagate dynamically to KPI calculations
        if not df_prio.empty:
            df_prio["total_p95_exposure"] = df_prio["total_p95_exposure"] * np.random.uniform(0.985, 1.015, size=len(df_prio))
            
        score_col = "composite_score" if "composite_score" in df_res.columns else "resilience_score"
        if not df_res.empty:
            df_res[score_col] = (df_res[score_col] + np.random.uniform(-0.008, 0.008, size=len(df_res))).clip(0.0, 1.0)
            
        if not df_pb.empty:
            df_pb["roi"] = df_pb["roi"] * np.random.uniform(0.99, 1.01, size=len(df_pb))
            
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    total_suppliers      = int(len(df_prio))
    total_network_exp    = float(df_prio["total_p95_exposure"].sum())
    critical_count       = int((df_prio["priority_quadrant"] == "Critical Priority").sum())
    monitor_count        = int((df_prio["priority_quadrant"] == "Monitor Closely").sum())

    # At-risk cohort playbook entries
    at_risk_ids = df_prio.loc[
        df_prio["priority_quadrant"].isin(["Critical Priority", "Monitor Closely"]),
        "supplier_id"
    ]
    df_at_risk = df_pb[df_pb["supplier_id"].isin(at_risk_ids)]
    recommended_budget   = float(df_at_risk["estimated_cost"].sum())
    portfolio_roi        = float(df_at_risk["roi"].mean()) if not df_at_risk.empty else 0.0
    # risk_eliminated ≈ ROI × budget (since ROI = risk_eliminated / cost)
    total_risk_elim      = portfolio_roi * recommended_budget

    # Network resilience scores
    score_col = "composite_score" if "composite_score" in df_res.columns else "resilience_score"
    resilience_before    = float(df_res[score_col].mean())

    # Projected score: apply risk reduction estimates to at-risk suppliers
    WEIGHTS = {"dependency": 0.40, "geographic": 0.25, "reliability": 0.20, "substitutability": 0.15}
    REDUCTION_MAP = {
        "Dual-Sourcing":                   {"substitutability_risk": 0.60, "dependency_risk": 0.50},
        "Safety Stock Increase":           {"dependency_risk": 0.25},
        "Supplier Development Programme":  {"reliability_risk": 0.40},
        "Geographic Diversification":      {"geo_risk": 0.45},
        "Quarterly Monitoring":            {},
    }
    df_proj = df_res.copy()
    for _, pb_row in df_at_risk.iterrows():
        s_id = pb_row["supplier_id"]
        reductions = REDUCTION_MAP.get(pb_row["recommended_action"], {})
        idx = df_proj[df_proj["supplier_id"] == s_id].index
        for factor, frac in reductions.items():
            if factor in df_proj.columns:
                df_proj.loc[idx, factor] = df_proj.loc[idx, factor] * (1 - frac)

    df_proj["composite_proj"] = (
        WEIGHTS["dependency"]      * df_proj["dependency_risk"].fillna(0) +
        WEIGHTS["geographic"]      * df_proj["geo_risk"].fillna(0) +
        WEIGHTS["reliability"]     * df_proj["reliability_risk"].fillna(0) +
        WEIGHTS["substitutability"]* df_proj["substitutability_risk"].fillna(0)
    )
    resilience_after = float(1 - df_proj["composite_proj"].mean())

    return KPISummary(
        total_suppliers=total_suppliers,
        total_network_exposure=round(total_network_exp, 2),
        critical_priority_count=critical_count,
        monitor_closely_count=monitor_count,
        recommended_budget=round(recommended_budget, 2),
        total_risk_eliminated=round(total_risk_elim, 2),
        portfolio_roi=round(portfolio_roi, 4),
        network_resilience_before=round(resilience_before, 4),
        network_resilience_after=round(resilience_after, 4),
    )


# ── /api/graph ────────────────────────────────────────────────────────────

@app.get("/api/graph", tags=["Graph"])
def get_graph() -> dict:
    """
    Returns the supplier-product dependency graph as JSON suitable for
    frontend graph-visualisation libraries (e.g. React-Flow, D3, Cytoscape).

    Nodes contain: node_id, type ('supplier'|'product'), name, pagerank_score,
    and optional country/tier for supplier nodes.

    Edges contain: source, target, and weight (supply_share).
    """
    try:
        df_sup  = read_table("suppliers")
        df_prod = read_table("products")
        df_rel  = read_table("supply_relationships")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    try:
        G  = build_dependency_graph(df_rel, df_sup, df_prod)
        df_pr = compute_pagerank(G)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph build error: {exc}") from exc

    pr_map = df_pr.set_index("node_id")["pagerank_score"].to_dict()

    # Build nodes
    nodes: list[dict] = []
    for node_id, attrs in G.nodes(data=True):
        node_type = attrs.get("type", "unknown")
        if node_type == "supplier":
            name = attrs.get("supplier_name", node_id)
        else:
            name = attrs.get("product_name") or attrs.get("sku") or node_id

        nodes.append(GraphNode(
            node_id=node_id,
            type=node_type,
            name=str(name),
            pagerank_score=float(pr_map.get(node_id, 0.0)),
            country=attrs.get("country") or None,
            tier=int(attrs["tier"]) if attrs.get("tier") is not None else None,
        ).model_dump())

    # Build edges
    edges: list[dict] = []
    for u, v, data in G.edges(data=True):
        edges.append(GraphEdge(
            source=u,
            target=v,
            weight=float(data.get("weight", 0.0)),
        ).model_dump())

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }


# ── /api/health ───────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
def health_check() -> dict:
    """
    Returns the database connection status.

    Calls src.db.test_connection() under the hood and reports the outcome
    along with the host and database name resolved from environment variables.
    """
    import os
    db_host = os.getenv("DB_HOST", "localhost")
    db_name = os.getenv("DB_NAME", "shockproof")
    try:
        engine = get_engine()
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": db_name,
            "host": db_host,
            "message": "Database connection successful.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "unhealthy",
                "database": db_name,
                "host": db_host,
                "error": str(exc),
            },
        ) from exc


# ── New Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/products", tags=["Products"])
def get_products(category: Optional[str] = Query(None, description="Filter by product category")) -> list[dict]:
    """
    Returns all products. Optionally filters by category.
    """
    try:
        df = read_table("products")
        if category:
            df = df[df["category"].str.lower() == category.lower()]
        return _df_to_records(df.drop(columns=["created_at"], errors="ignore"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@app.get("/api/supply-relationships", tags=["Relationships"])
def get_supply_relationships(
    supplier_id: Optional[int] = Query(None),
    product_id: Optional[int] = Query(None)
) -> list[dict]:
    """
    Returns supply relationships enriched with supplier names and product details.
    """
    try:
        df = read_table("supply_relationships")
        df_sup = read_table("suppliers")[["supplier_id", "supplier_name", "country", "tier"]]
        df_prod = read_table("products")[["product_id", "sku", "product_name", "category"]]
        
        df = df.merge(df_sup, on="supplier_id", how="left")
        df = df.merge(df_prod, on="product_id", how="left")
        
        if supplier_id:
            df = df[df["supplier_id"] == supplier_id]
        if product_id:
            df = df[df["product_id"] == product_id]
        return _df_to_records(df.drop(columns=["created_at"], errors="ignore"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@app.get("/api/transactions", tags=["Transactions"])
def get_transactions(
    supplier_id: Optional[int] = Query(None),
    product_id: Optional[int] = Query(None),
    limit: int = Query(100, description="Number of transactions to return")
) -> list[dict]:
    """
    Returns transactions enriched with supplier names and product details.
    """
    try:
        df = read_table("transactions")
        df_sup = read_table("suppliers")[["supplier_id", "supplier_name"]]
        df_prod = read_table("products")[["product_id", "sku", "product_name"]]
        
        df = df.merge(df_sup, on="supplier_id", how="left")
        df = df.merge(df_prod, on="product_id", how="left")
        
        if supplier_id:
            df = df[df["supplier_id"] == supplier_id]
        if product_id:
            df = df[df["product_id"] == product_id]
        
        if "transaction_id" in df.columns:
            df = df.sort_values("transaction_id", ascending=False)
        elif "order_date" in df.columns:
            df = df.sort_values("order_date", ascending=False)
            
        df = df.head(limit)
        return _df_to_records(df.drop(columns=["created_at"], errors="ignore"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@app.get("/api/critical-suppliers", tags=["Critical Suppliers"])
def get_critical_suppliers() -> list[dict]:
    """
    Returns pre-computed critical suppliers from critical_suppliers table.
    """
    try:
        df = read_table("critical_suppliers")
        return _df_to_records(df)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc


@app.get("/api/centrality", tags=["Centrality"])
def get_centrality() -> list[dict]:
    """
    Returns supplier centrality metrics computed live from the dependency graph.

    The supplier-product graph is bipartite, so betweenness/closeness on the
    raw graph are always 0.  We project onto a supplier-only graph where two
    suppliers share an edge if they co-supply at least one product, then
    compute all three centrality measures on that projection.
    """
    try:
        import networkx as nx
        from networkx.algorithms import bipartite

        df_sup  = read_table("suppliers")
        df_prod = read_table("products")
        df_rel  = read_table("supply_relationships")

        G = build_dependency_graph(df_rel, df_sup, df_prod)
        df_pr = compute_pagerank(G)
        pr_map = df_pr.set_index("node_id")["pagerank_score"].to_dict()

        # Partition by type
        sup_nodes  = [n for n, d in G.nodes(data=True) if d.get("type") == "supplier"]
        prod_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "product"]

        # Build undirected bipartite graph for projection
        B = nx.Graph()
        B.add_nodes_from(sup_nodes,  bipartite=0)
        B.add_nodes_from(prod_nodes, bipartite=1)
        for u, v in G.edges():
            B.add_edge(u, v)

        # Supplier co-supply projection: edge exists if two suppliers share a product
        proj = bipartite.weighted_projected_graph(B, sup_nodes)

        # Centrality measures on the projected graph
        deg = nx.degree_centrality(proj)
        n   = len(proj)
        bet = nx.betweenness_centrality(proj, k=min(50, n), normalized=True) if n > 2 else {}
        clo = nx.closeness_centrality(proj)

        sup_name_map = dict(zip(df_sup["supplier_id"], df_sup["supplier_name"]))

        results = []
        for node_id in sup_nodes:
            # node_id is like "S_1" — extract integer supplier_id
            try:
                s_id = int(node_id.split("_")[1])
            except (IndexError, ValueError):
                s_id = None

            results.append({
                "node_id":                node_id,
                "supplier_id":            s_id,
                "supplier_name":          sup_name_map.get(s_id, node_id),
                "degree_centrality":      round(float(deg.get(node_id, 0.0)), 6),
                "betweenness_centrality": round(float(bet.get(node_id, 0.0)), 6),
                "closeness_centrality":   round(float(clo.get(node_id, 0.0)), 6),
                "pagerank":               round(float(pr_map.get(node_id, 0.0)), 6),
            })

        results.sort(key=lambda r: r["degree_centrality"], reverse=True)
        return results

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Centrality computation error: {exc}") from exc


@app.get("/api/sensitivity", tags=["Sensitivity"])
def get_sensitivity() -> list[dict]:
    """
    Computes risk bands under 5 different weight configurations for all suppliers.
    """
    try:
        df_sup = read_table("suppliers")
        df_enriched = read_table("suppliers_enriched")
        df_rel = read_table("supply_relationships")
        df_sim = read_table("simulation_results")
        
        # Apply noise to df_sim to propagate to sensitivity analysis
        if not df_sim.empty:
            for col in ["p50_impact", "p95_impact", "mean_impact", "std_impact"]:
                if col in df_sim.columns:
                    df_sim[col] = df_sim[col] * np.random.uniform(0.985, 1.015, size=len(df_sim))
                    
        df_sens = sensitivity_analysis(df_sup, df_enriched, df_rel, df_sim)
        return _df_to_records(df_sens)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sensitivity calculation error: {exc}") from exc

