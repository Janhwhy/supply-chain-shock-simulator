from src.playbook import recommend_action, compute_roi, MITIGATION_ACTIONS
sup = {
    'supplier_id': 27,
    'total_p95_exposure': 2821557.45,
    'dominant_risk_factor': 'dependency_risk',
    'risk_band': 'Critical',
    'monthly_revenue': 235129.78,
}
action = MITIGATION_ACTIONS['safety_stock_increase']
res = compute_roi(sup, action, 0.15)
print(res)
