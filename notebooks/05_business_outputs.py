import sys, os
sys.path.insert(0, os.path.abspath('..'))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from IPython.display import display

# ── src imports ──────────────────────────────────────────────────────────────
from src.db import get_engine, read_table, write_dataframe, execute_statement, read_query
from src.simulation import identify_worst_case_scenarios
from src.playbook import (
    generate_playbook,
    playbook_summary,
    recommend_action,
    MITIGATION_ACTIONS,
)
from src.scoring import compute_resilience_scores

# ── Plot style ───────────────────────────────────────────────────────────────
sns.set_theme(style="whitegrid", font_scale=1.05)
plt.rcParams.update({
    "figure.dpi": 120,
    "figure.figsize": (13, 6),
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "figure.titlesize": 16,
})
QUAD_PALETTE = {
    "Critical Priority": "#e74c3c",
    "Monitor Closely":   "#e67e22",
    "Contingency Plan":  "#f1c40f",
    "Routine Review":    "#2ecc71",
}

# ── Load tables ───────────────────────────────────────────────────────────────
print("Loading tables from PostgreSQL …")
df_priority_matrix    = read_table("risk_priority_matrix")
df_resilience_scores  = read_table("resilience_scores")
df_simulation_results = read_table("simulation_results")
df_suppliers          = read_table("suppliers")
df_suppliers_enriched = read_table("suppliers_enriched")
df_relationships      = read_table("supply_relationships")

print(f"  risk_priority_matrix   : {len(df_priority_matrix):>4} rows")
print(f"  resilience_scores      : {len(df_resilience_scores):>4} rows")
print(f"  simulation_results     : {len(df_simulation_results):>4} rows")

# ── Worst-case scenarios ──────────────────────────────────────────────────────
df_worst_case = identify_worst_case_scenarios(df_simulation_results)
print(f"  worst_case computed    : {len(df_worst_case):>4} suppliers")
print()
print(df_worst_case.head())


df_playbook = generate_playbook(
    df_priority_matrix,
    df_resilience_scores,
    df_simulation_results,
    df_worst_case,
)
print(f"Playbook generated: {len(df_playbook)} supplier entries\n")

# ── Full playbook display ─────────────────────────────────────────────────────
pd.set_option("display.max_rows", 110)
pd.set_option("display.float_format", "₹{:,.0f}".format)
print(df_playbook[[
    "supplier_id", "supplier_name", "priority_quadrant",
    "dominant_risk_factor", "recommended_action",
    "action_cost", "expected_annual_loss", "risk_reduction",
    "roi", "payback_period_years"
]])
pd.reset_option("display.float_format")


# ── Top-10 highest-ROI actions — formatted report table ──────────────────────
df_top10 = df_playbook.head(10).copy()

# Filter out infinite payback rows for display clarity
df_top10_display = df_top10[[
    "supplier_name", "priority_quadrant", "recommended_action",
    "action_cost", "expected_annual_loss", "risk_reduction",
    "roi", "payback_period_years"
]].copy()

df_top10_display["action_cost"]        = df_top10_display["action_cost"].map("₹{:,.0f}".format)
df_top10_display["expected_annual_loss"] = df_top10_display["expected_annual_loss"].map("₹{:,.0f}".format)
df_top10_display["risk_reduction"]     = df_top10_display["risk_reduction"].map("₹{:,.0f}".format)
df_top10_display["roi"]                = df_top10_display["roi"].map("{:.2f}x".format)
df_top10_display["payback_period_years"] = df_top10_display["payback_period_years"].apply(
    lambda v: f"{v:.2f} yrs" if v != float("inf") else "∞"
)
df_top10_display.columns = [
    "Supplier", "Quadrant", "Recommended Action",
    "Cost", "Expected Annual Loss", "Risk Reduction",
    "ROI", "Payback Period"
]
df_top10_display.index = range(1, 11)

print("TOP 10 HIGHEST-ROI MITIGATION ACTIONS")
print("=" * 80)
print(df_top10_display.style.set_caption("Table 1 — Top 10 Ranked Mitigation Actions by ROI"))


summary = playbook_summary(df_playbook)

print("=" * 56)
print("  PORTFOLIO MITIGATION SUMMARY (At-Risk Cohort)")
print("=" * 56)
print(f"  Total Mitigation Budget Required : ₹{summary['total_mitigation_budget']:>15,.2f}")
print(f"  Total Risk Eliminated            : ₹{summary['total_risk_eliminated']:>15,.2f}")
print(f"  Portfolio-Level ROI              :  {summary['portfolio_roi']:>14.4f}x")
print()
print("  Suppliers per Recommended Action:")
for action, count in sorted(summary["action_counts"].items(), key=lambda x: -x[1]):
    print(f"    {action:<35}: {count:>3} suppliers")
print("=" * 56)


# ── Pie chart — action type distribution ─────────────────────────────────────
action_counts = summary["action_counts"]
labels  = list(action_counts.keys())
sizes   = list(action_counts.values())
colors  = ["#e74c3c", "#e67e22", "#3498db", "#2ecc71", "#9b59b6"][:len(labels)]
explode = [0.04] * len(labels)

fig, ax = plt.subplots(figsize=(9, 7))
wedges, texts, autotexts = ax.pie(
    sizes, labels=labels, autopct="%1.0f%%",
    startangle=140, colors=colors, explode=explode,
    textprops={"fontsize": 11}, pctdistance=0.78,
    wedgeprops={"linewidth": 1.2, "edgecolor": "white"},
)
for at in autotexts:
    at.set_fontsize(10)
    at.set_fontweight("bold")

ax.set_title("Distribution of Recommended Mitigation Actions\nAcross All 100 Suppliers",
             fontsize=14, pad=18)
plt.tight_layout()
# plt.show()


df_critical_pb = df_playbook[df_playbook["priority_quadrant"] == "Critical Priority"].copy()
action_map = {v["action_name"]: v["description"] for v in MITIGATION_ACTIONS.values()}

for rank, (_, row) in enumerate(df_critical_pb.iterrows(), 1):
    res_row = df_resilience_scores[df_resilience_scores["supplier_id"] == row["supplier_id"]]
    res_score = df_priority_matrix.loc[
        df_priority_matrix["supplier_id"] == row["supplier_id"], "resilience_score"
    ].values[0]
    geo_col = "geo_risk" if "geo_risk" in df_resilience_scores.columns else "geographic_risk"

    dep = res_row.iloc[0]["dependency_risk"]      if not res_row.empty else 0.0
    geo = res_row.iloc[0][geo_col]                if not res_row.empty else 0.0
    rel = res_row.iloc[0]["reliability_risk"]      if not res_row.empty else 0.0
    sub = res_row.iloc[0]["substitutability_risk"] if not res_row.empty else 0.0

    payback_str = (f"{row['payback_period_years']:.2f} years"
                   if row["payback_period_years"] != float("inf") else "∞")

    print("╔" + "═" * 68 + "╗")
    print(f"║  #{rank}  CRITICAL PRIORITY — {row['supplier_name']:<42}║")
    print("╠" + "═" * 68 + "╣")
    print(f"║  Resilience Score          : {res_score:.3f}  (0 = maximum risk, 1 = resilient) ║")
    print(f"║  Total P95 Exposure        : ₹{row['expected_annual_loss']:>12,.0f} / year (expected)    ║")
    print(f"╠" + "─" * 68 + "╣")
    print(f"║  Risk Factor Scores:                                                ║")
    print(f"║    Dependency Risk         : {dep:.3f}                                    ║")
    print(f"║    Geographic Risk         : {geo:.3f}                                    ║")
    print(f"║    Reliability Risk        : {rel:.3f}                                    ║")
    print(f"║    Substitutability Risk   : {sub:.3f}  ← dominant                       ║")
    print(f"╠" + "─" * 68 + "╣")
    print(f"║  Dominant Risk Factor      : {row['dominant_risk_factor']:<38}║")
    print(f"║  Recommended Action        : {row['recommended_action']:<38}║")
    print(f"║  Action Description        : {row['action_description'][:38]:<38}║")
    print(f"╠" + "─" * 68 + "╣")
    print(f"║  Financial Case:                                                    ║")
    print(f"║    One-off Mitigation Cost : ₹{row['action_cost']:>12,.0f}                          ║")
    print(f"║    Expected Annual Loss    : ₹{row['expected_annual_loss']:>12,.0f}                          ║")
    print(f"║    Annual Risk Eliminated  : ₹{row['risk_reduction']:>12,.0f}                          ║")
    print(f"║    Return on Investment    : {row['roi']:.2f}x                                   ║")
    print(f"║    Payback Period          : {payback_str:<39}║")
    print("╚" + "═" * 68 + "╝")
    print()


# ── Horizontal paired bar chart — top 15 by ROI ──────────────────────────────
df_top15 = df_playbook[df_playbook["roi"] < float("inf")].head(15).copy()
df_top15 = df_top15.sort_values("roi", ascending=True)   # ascending for horizontal bar

fig, ax = plt.subplots(figsize=(13, 8))
y = range(len(df_top15))
bar_h = 0.38

bars_cost = ax.barh(
    [i - bar_h / 2 for i in y], df_top15["action_cost"] / 1e6,
    height=bar_h, color="#3498db", label="Mitigation Cost (₹M)", alpha=0.88
)
bars_red = ax.barh(
    [i + bar_h / 2 for i in y], df_top15["risk_reduction"] / 1e6,
    height=bar_h, color="#e74c3c", label="Annual Risk Eliminated (₹M)", alpha=0.88
)

ax.set_yticks(list(y))
ax.set_yticklabels(df_top15["supplier_name"], fontsize=9)
ax.set_xlabel("Value (₹ Millions)", fontsize=11)
ax.set_title("Top 15 Suppliers by ROI — Cost-of-Action vs Cost-of-Inaction", fontsize=13, pad=14)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"₹{v:.1f}M"))
ax.legend(fontsize=10, loc="lower right")
ax.axvline(0, color="black", linewidth=0.8)
sns.despine(left=False)
plt.tight_layout()
# plt.show()


# ── Break-even scatter — action_cost vs ROI, coloured by quadrant ────────────
df_scatter = df_playbook[df_playbook["roi"] < 50].copy()   # cap extreme outliers for visual

fig, ax = plt.subplots(figsize=(12, 7))
for quad, grp in df_scatter.groupby("priority_quadrant"):
    ax.scatter(
        grp["action_cost"] / 1e6, grp["roi"],
        label=quad, color=QUAD_PALETTE.get(quad, "grey"),
        s=90, alpha=0.85, edgecolors="white", linewidths=0.6
    )

ax.axhline(1.0, color="black", linestyle="--", linewidth=1.5, label="ROI = 1× (Break-Even)")
ax.set_xlabel("One-off Mitigation Cost (₹ Millions)", fontsize=11)
ax.set_ylabel("Return on Investment (×)", fontsize=11)
ax.set_title("Mitigation Cost vs ROI — All 100 Suppliers\n(above dashed line = pays back within one year)",
             fontsize=13, pad=14)
ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"₹{v:.1f}M"))
ax.legend(title="Priority Quadrant", fontsize=9, title_fontsize=9)
sns.despine()
plt.tight_layout()
# plt.show()


# ── 1. Total network P95 exposure ─────────────────────────────────────────────
total_network_p95 = df_priority_matrix["total_p95_exposure"].sum()

critical_exposure = df_priority_matrix.loc[
    df_priority_matrix["priority_quadrant"] == "Critical Priority",
    "total_p95_exposure"
].sum()

critical_fraction = critical_exposure / total_network_p95 * 100

print("=" * 56)
print("  NETWORK-LEVEL EXPOSURE SUMMARY")
print("=" * 56)
print(f"  Total Network P95 Exposure      : ₹{total_network_p95:>15,.2f}")
print(f"  Critical Priority Exposure      : ₹{critical_exposure:>15,.2f}")
print(f"  Critical Priority Share         :  {critical_fraction:>14.1f}%")
print()

# ── 2. Current mean network resilience score ──────────────────────────────────
# We compute fresh from the scores table (composite_score column = resilience_score)
score_col = "composite_score" if "composite_score" in df_resilience_scores.columns else "resilience_score"
current_mean_resilience = df_resilience_scores[score_col].mean()
print(f"  Network Resilience Score (now)  :  {current_mean_resilience:>14.4f}")

# ── 3. Projected score after mitigation ──────────────────────────────────────
# Strategy: for every Critical Priority / Monitor Closely supplier, apply the
# risk_reduction_estimate to the dominant factor score, recompute composite risk,
# then average across all 100 suppliers.
WEIGHTS = {"dependency": 0.40, "geographic": 0.25, "reliability": 0.20, "substitutability": 0.15}
REDUCTION_MAP = {
    "dual_sourcing":              {"substitutability_risk": 0.60, "dependency_risk": 0.50},
    "safety_stock_increase":      {"dependency_risk": 0.25},
    "supplier_development":       {"reliability_risk": 0.40},
    "geographic_diversification": {"geographic_risk": 0.45},
    "quarterly_monitoring":       {},
}
FACTOR_TO_WEIGHT = {
    "dependency_risk":      "dependency",
    "substitutability_risk":"substitutability",
    "reliability_risk":     "reliability",
    "geographic_risk":      "geographic",
}

geo_col = "geo_risk" if "geo_risk" in df_resilience_scores.columns else "geographic_risk"

# Build working copy with aligned column names
df_sim = df_resilience_scores.copy()
df_sim.rename(columns={geo_col: "geographic_risk", score_col: "resilience_score"}, inplace=True)

# Apply reductions for at-risk suppliers
target_quads = {"Critical Priority", "Monitor Closely"}
for _, pb_row in df_playbook.iterrows():
    if pb_row["priority_quadrant"] not in target_quads:
        continue
    s_id = pb_row["supplier_id"]

    # Map action name back to action_id key
    action_key = next(
        (k for k, v in MITIGATION_ACTIONS.items() if v["action_name"] == pb_row["recommended_action"]),
        None
    )
    if action_key is None:
        continue

    reductions = REDUCTION_MAP.get(action_key, {})
    idx = df_sim[df_sim["supplier_id"] == s_id].index
    if idx.empty:
        continue

    for factor, frac in reductions.items():
        if factor in df_sim.columns:
            df_sim.loc[idx, factor] = df_sim.loc[idx, factor] * (1.0 - frac)

# Recompute composite risk and resilience score
df_sim["composite_risk_projected"] = (
    WEIGHTS["dependency"]     * df_sim["dependency_risk"].fillna(0) +
    WEIGHTS["geographic"]     * df_sim["geographic_risk"].fillna(0) +
    WEIGHTS["reliability"]    * df_sim["reliability_risk"].fillna(0) +
    WEIGHTS["substitutability"] * df_sim["substitutability_risk"].fillna(0)
)
df_sim["resilience_score_projected"] = 1.0 - df_sim["composite_risk_projected"]

projected_mean_resilience = df_sim["resilience_score_projected"].mean()
improvement = projected_mean_resilience - current_mean_resilience

print(f"  Network Resilience (projected)  :  {projected_mean_resilience:>14.4f}")
print(f"  Improvement from mitigation     :  +{improvement:>13.4f}")
print("=" * 56)


n_critical = int((df_priority_matrix["priority_quadrant"] == "Critical Priority").sum())
n_monitor  = int((df_priority_matrix["priority_quadrant"] == "Monitor Closely").sum())

exec_summary = {
    "Metric": [
        "Total Suppliers Analysed",
        "Total Network P95 Exposure",
        "Suppliers in Critical Priority",
        "Suppliers in Monitor Closely",
        "Recommended Mitigation Budget",
        "Total Risk Eliminated (Annual)",
        "Portfolio ROI",
        "Network Resilience Score (Before)",
        "Network Resilience Score (Projected After Mitigation)",
    ],
    "Value": [
        f"{len(df_priority_matrix)}",
        f"₹{total_network_p95:,.2f}",
        f"{n_critical}",
        f"{n_monitor}",
        f"₹{summary['total_mitigation_budget']:,.2f}",
        f"₹{summary['total_risk_eliminated']:,.2f}",
        f"{summary['portfolio_roi']:.4f}×",
        f"{current_mean_resilience:.4f}",
        f"{projected_mean_resilience:.4f}",
    ],
}
df_exec = pd.DataFrame(exec_summary)

# ── Styled display ────────────────────────────────────────────────────────────
styled = (
    df_exec.style
    .set_caption("Table 2 — ShockProof Executive Summary")
    .set_table_styles([
        {"selector": "caption",
         "props": [("font-size", "15px"), ("font-weight", "bold"),
                   ("text-align", "left"), ("margin-bottom", "6px")]},
        {"selector": "th",
         "props": [("background-color", "#2c3e50"), ("color", "white"),
                   ("font-size", "12px"), ("padding", "8px 14px")]},
        {"selector": "td",
         "props": [("padding", "7px 14px"), ("font-size", "12px")]},
        {"selector": "tr:nth-child(even) td",
         "props": [("background-color", "#f4f6f8")]},
        {"selector": "tr:hover td",
         "props": [("background-color", "#d6eaf8")]},
    ])
    .hide(axis="index")
)
print(styled)

print("\nPlain-text version (report-ready):")
print("=" * 56)
for _, r in df_exec.iterrows():
    print(f"  {r['Metric']:<46}: {r['Value']}")
print("=" * 56)


# Map worst-case scenario name for each supplier
scenario_map = df_worst_case.set_index("supplier_id")["worst_case_scenario"].to_dict()

df_db_playbook = df_playbook[["supplier_id", "recommended_action",
                               "action_cost", "expected_annual_loss", "roi"]].copy()
df_db_playbook["scenario"] = df_db_playbook["supplier_id"].map(scenario_map).fillna("unknown")
df_db_playbook.rename(columns={
    "recommended_action": "recommended_action",
    "action_cost":        "estimated_cost",
    "expected_annual_loss": "p95_impact",
}, inplace=True)

# ── Clear existing rows then insert ──────────────────────────────────────────
print("Clearing existing rows from 'mitigation_playbook' …")
execute_statement("DELETE FROM mitigation_playbook")

print("Writing playbook to PostgreSQL …")
write_dataframe(
    df_db_playbook[["supplier_id", "scenario", "recommended_action",
                    "estimated_cost", "p95_impact", "roi"]],
    "mitigation_playbook",
    if_exists="append",
)

# ── Verification ──────────────────────────────────────────────────────────────
row_count = read_query("SELECT COUNT(*) FROM mitigation_playbook").iloc[0, 0]
expected  = 100
print(f"\nDatabase Verification:")
print(f"  Rows in 'mitigation_playbook' : {row_count}  (expected: {expected})")
if row_count == expected:
    print("  Status : ✓ SUCCESS — playbook written and verified.")
else:
    print("  Status : ✗ FAILURE — row count mismatch. Investigate.")

