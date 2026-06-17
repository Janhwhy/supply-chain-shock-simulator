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
from src.scenarios import get_all_scenarios, scenarios_to_dataframe
from src.graph import build_dependency_graph, compute_pagerank

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
    profile["resilience_scores"] = (
        _df_to_records(res_row.drop(columns=["score_date"], errors="ignore"))
        if not res_row.empty else {}
    )

    prio_row = df_prio[df_prio["supplier_id"] == supplier_id]
    profile["priority_matrix"] = (
        _df_to_records(prio_row.drop(columns=["created_at"], errors="ignore"))
        if not prio_row.empty else {}
    )

    sim_rows = df_sim[df_sim["supplier_id"] == supplier_id]
    profile["simulation_results"] = (
        _df_to_records(sim_rows.drop(columns=["result_id", "created_at"], errors="ignore"))
        if not sim_rows.empty else []
    )

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
        df = read_table("simulation_results")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    # simulation_results stores display names; map scenario_id → display_name
    scenario_obj = next(s for s in get_all_scenarios() if s.scenario_id == scenario_id)
    df_filtered = df[df["scenario_name"] == scenario_obj.display_name].copy()

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
        df_pb   = read_table("mitigation_playbook")
        df_prio = read_table("risk_priority_matrix")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    # Enrich with quadrant + supplier_name for filter support
    df = df_pb.merge(
        df_prio[["supplier_id", "supplier_name", "priority_quadrant"]],
        on="supplier_id", how="left",
    )

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
