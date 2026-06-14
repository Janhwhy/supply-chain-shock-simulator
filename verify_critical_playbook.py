"""
Verification script: loads risk_priority_matrix and resilience_scores from PostgreSQL,
filters to 'Critical Priority' suppliers, calls recommend_action() for each, and
prints a full diagnostic report.
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import pandas as pd
from src.db import read_table
from src.playbook import recommend_action

SEPARATOR = "=" * 72

# ── 1. Load tables from PostgreSQL ────────────────────────────────────────────
print(SEPARATOR)
print("Loading risk_priority_matrix from PostgreSQL...")
df_priority = read_table("risk_priority_matrix")
print(f"  Loaded {len(df_priority)} rows.")

print("Loading resilience_scores from PostgreSQL...")
df_scores   = read_table("resilience_scores")
print(f"  Loaded {len(df_scores)} rows.")

# ── 2. Filter to Critical Priority suppliers ──────────────────────────────────
df_critical = df_priority[df_priority["priority_quadrant"] == "Critical Priority"].copy()
print(f"\n  Critical Priority suppliers found: {len(df_critical)}\n")
print(SEPARATOR)

# resilience_scores uses 'geo_risk' as the column name (schema alias)
# Provide a normalised 'geographic_risk' alias for recommend_action
GEO_COL = "geo_risk" if "geo_risk" in df_scores.columns else "geographic_risk"

confirmed_non_monitoring = []
failed = []

for _, crit_row in df_critical.iterrows():
    s_id   = crit_row["supplier_id"]
    s_name = crit_row["supplier_name"]
    quadrant      = crit_row["priority_quadrant"]
    res_score     = crit_row["resilience_score"]
    total_p95     = crit_row["total_p95_exposure"]

    # Fetch factor scores from resilience_scores table
    score_match = df_scores[df_scores["supplier_id"] == s_id]
    if score_match.empty:
        print(f"  WARNING: No resilience_scores row found for supplier_id={s_id} ({s_name})")
        failed.append(s_name)
        continue

    sr = score_match.iloc[0]
    dep_risk = float(sr.get("dependency_risk",       0.0))
    geo_risk = float(sr.get(GEO_COL,                0.0))
    rel_risk = float(sr.get("reliability_risk",      0.0))
    sub_risk = float(sr.get("substitutability_risk", 0.0))

    # Build the supplier dict that recommend_action expects
    supplier_dict = {
        "supplier_id":          s_id,
        "supplier_name":        s_name,
        "priority_quadrant":    quadrant,
        "resilience_score":     res_score,
        "total_p95_exposure":   total_p95,
        "dependency_risk":      dep_risk,
        "geographic_risk":      geo_risk,
        "geo_risk":             geo_risk,
        "reliability_risk":     rel_risk,
        "substitutability_risk": sub_risk,
    }

    action_id, dominant_factor = recommend_action(supplier_dict)

    # Pretty-print individual record
    print(f"Supplier          : {s_name}  (ID: {s_id})")
    print(f"Priority Quadrant : {quadrant}")
    print(f"Resilience Score  : {res_score:.3f}")
    print(f"Factor Scores     :")
    print(f"  dependency_risk      = {dep_risk:.3f}")
    print(f"  geographic_risk      = {geo_risk:.3f}")
    print(f"  reliability_risk     = {rel_risk:.3f}")
    print(f"  substitutability_risk= {sub_risk:.3f}")
    print(f"Dominant Factor   : {dominant_factor}")
    print(f"Recommended Action: {action_id}")

    # Confirmation check
    if action_id == "quarterly_monitoring":
        status = "✗ FAIL — should NOT receive Quarterly Monitoring"
        failed.append(s_name)
    else:
        status = "✓ PASS — non-monitoring action assigned"
        confirmed_non_monitoring.append(s_name)

    print(f"Confirmation      : {status}")
    print(SEPARATOR)

# ── 3. Final summary ──────────────────────────────────────────────────────────
print("\n=== VERIFICATION SUMMARY ===")
print(f"  Critical Priority suppliers checked : {len(df_critical)}")
print(f"  PASSED (non-Quarterly Monitoring)   : {len(confirmed_non_monitoring)}")
print(f"  FAILED                              : {len(failed)}")
if confirmed_non_monitoring:
    print(f"\n  Confirmed suppliers:")
    for name in confirmed_non_monitoring:
        print(f"    ✓ {name}")
if failed:
    print(f"\n  Failed suppliers:")
    for name in failed:
        print(f"    ✗ {name}")

overall = "ALL CHECKS PASSED ✓" if not failed else "SOME CHECKS FAILED ✗"
print(f"\n  Overall Result: {overall}")
