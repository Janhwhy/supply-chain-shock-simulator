"""test_playbook.py — Unit tests for the mitigation playbook module."""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch
from src.playbook import (
    recommend_action,
    compute_roi,
    generate_playbook,
    playbook_summary,
    MITIGATION_ACTIONS
)

# ============================================================================
# 1. Tests for recommend_action
# ============================================================================

def test_recommend_action_critical_priority():
    """Verify recommendation logic for Critical Priority quadrant suppliers."""
    # Case A: substitutability_risk is dominant
    sup_a = {
        'supplier_id': 1,
        'priority_quadrant': 'Critical Priority',
        'substitutability_risk': 0.8,
        'geographic_risk': 0.4,
        'dependency_risk': 0.1,
        'reliability_risk': 0.1
    }
    action_id, dom = recommend_action(sup_a)
    assert action_id == 'dual_sourcing'
    assert dom == 'substitutability_risk'

    # Case B: geographic_risk is dominant
    sup_b = {
        'supplier_id': 2,
        'priority_quadrant': 'Critical Priority',
        'substitutability_risk': 0.3,
        'geographic_risk': 0.9,
        'dependency_risk': 0.1,
        'reliability_risk': 0.1
    }
    action_id, dom = recommend_action(sup_b)
    assert action_id == 'geographic_diversification'
    assert dom == 'geographic_risk'

    # Case C: Tie-break (substitutability >= geographic)
    sup_c = {
        'supplier_id': 3,
        'priority_quadrant': 'Critical Priority',
        'substitutability_risk': 0.6,
        'geographic_risk': 0.6,
        'dependency_risk': 0.1,
        'reliability_risk': 0.1
    }
    action_id, dom = recommend_action(sup_c)
    assert action_id == 'dual_sourcing'
    assert dom == 'substitutability_risk'


def test_recommend_action_monitor_closely():
    """Verify recommendation logic for Monitor Closely quadrant suppliers."""
    # Case A: dependency_risk is dominant
    sup_a = {
        'supplier_id': 1,
        'priority_quadrant': 'Monitor Closely',
        'dependency_risk': 0.7,
        'reliability_risk': 0.4,
        'geographic_risk': 0.1,
        'substitutability_risk': 0.1
    }
    action_id, dom = recommend_action(sup_a)
    assert action_id == 'safety_stock_increase'
    assert dom == 'dependency_risk'

    # Case B: reliability_risk is dominant
    sup_b = {
        'supplier_id': 2,
        'priority_quadrant': 'Monitor Closely',
        'dependency_risk': 0.2,
        'reliability_risk': 0.8,
        'geographic_risk': 0.1,
        'substitutability_risk': 0.1
    }
    action_id, dom = recommend_action(sup_b)
    assert action_id == 'supplier_development'
    assert dom == 'reliability_risk'


def test_recommend_action_contingency_plan():
    """Verify recommendation logic for Contingency Plan quadrant suppliers (always Dual-Sourcing)."""
    sup = {
        'supplier_id': 1,
        'priority_quadrant': 'Contingency Plan',
        'dependency_risk': 0.8,
        'substitutability_risk': 0.3,
        'geographic_risk': 0.1,
        'reliability_risk': 0.1
    }
    action_id, dom = recommend_action(sup)
    assert action_id == 'dual_sourcing'
    assert dom == 'dependency_risk'  # Overall maximum risk factor


def test_recommend_action_routine_review():
    """Verify recommendation logic for Routine Review quadrant suppliers."""
    sup = {
        'supplier_id': 1,
        'priority_quadrant': 'Routine Review',
        'dependency_risk': 0.2,
        'reliability_risk': 0.2
    }
    action_id, dom = recommend_action(sup)
    assert action_id == 'quarterly_monitoring'
    assert dom == 'reliability_risk'


def test_recommend_action_fallback_lookup():
    """Verify recommend_action queries df_factor_breakdown if scores are missing from row."""
    sup = {
        'supplier_id': 5,
        'priority_quadrant': 'Monitor Closely'
    }
    df_factors = pd.DataFrame([
        {
            'supplier_id': 5,
            'dependency_risk': 0.9,
            'reliability_risk': 0.3,
            'geographic_risk': 0.1,
            'substitutability_risk': 0.1
        }
    ])
    action_id, dom = recommend_action(sup, df_factor_breakdown=df_factors)
    assert action_id == 'safety_stock_increase'
    assert dom == 'dependency_risk'


# ============================================================================
# 2. Tests for compute_roi
# ============================================================================

def test_compute_roi_dual_sourcing():
    """Test cost and ROI calculations for Dual-Sourcing."""
    sup = {
        'supplier_id': 1,
        'total_p95_exposure': 1000000.0,
        'dominant_risk_factor': 'substitutability_risk',
        'annual_revenue_exposure': 5000000.0
    }
    action = MITIGATION_ACTIONS['dual_sourcing']
    prob = 0.20  # worst-case scenario probability
    
    res = compute_roi(sup, action, prob)
    
    # Cost: 8% of 5,000,000 = 400,000
    assert pytest.approx(res['action_cost']) == 400000.0
    # Expected annual loss: 1,000,000 * 0.20 = 200,000
    assert pytest.approx(res['expected_annual_loss']) == 200000.0
    # Risk reduction: 200,000 * 0.60 (substitutability_risk estimate) = 120,000
    assert pytest.approx(res['risk_reduction']) == 120000.0
    # ROI: 120,000 / 400,000 = 0.30
    assert pytest.approx(res['roi']) == 0.30
    # Payback period: 400,000 / 120,000 = 3.333 years
    assert pytest.approx(res['payback_period_years']) == 10 / 3.0


def test_compute_roi_safety_stock_critical():
    """Test cost and ROI calculations for Safety Stock carrying costs for Critical band."""
    sup = {
        'supplier_id': 2,
        'total_p95_exposure': 1000000.0,
        'dominant_risk_factor': 'dependency_risk',
        'risk_band': 'Critical',
        'monthly_revenue': 100000.0
    }
    action = MITIGATION_ACTIONS['safety_stock_increase']
    prob = 0.15
    
    res = compute_roi(sup, action, prob)
    
    # Critical band => additional days = 30
    # Cost: (30 / 30) * 100,000 * 0.05 = 5000
    assert pytest.approx(res['action_cost']) == 5000.0
    # Expected annual loss: 1,000,000 * 0.15 = 150,000
    # Risk reduction: 150,000 * 0.25 (dependency_risk estimate) = 37,500
    assert pytest.approx(res['risk_reduction']) == 37500.0
    # ROI: 37,500 / 5000 = 7.50
    assert pytest.approx(res['roi']) == 7.50
    # Payback period: 5000 / 37,500 = 0.1333 years
    assert pytest.approx(res['payback_period_years']) == 5000 / 37500.0


def test_compute_roi_safety_stock_high():
    """Test cost and ROI calculations for Safety Stock carrying costs for High band."""
    sup = {
        'supplier_id': 2,
        'total_p95_exposure': 1000000.0,
        'dominant_risk_factor': 'dependency_risk',
        'risk_band': 'High',
        'monthly_revenue': 100000.0
    }
    action = MITIGATION_ACTIONS['safety_stock_increase']
    prob = 0.15
    
    res = compute_roi(sup, action, prob)
    
    # High band => additional days = 15
    # Cost: (15 / 30) * 100,000 * 0.05 = 2500
    assert pytest.approx(res['action_cost']) == 2500.0


def test_compute_roi_flat_rates():
    """Test cost and ROI calculations for flat rates (Supplier Development and Quarterly Monitoring)."""
    # Supplier Development
    sup_dev = {
        'supplier_id': 3,
        'total_p95_exposure': 1000000.0,
        'dominant_risk_factor': 'reliability_risk'
    }
    res_dev = compute_roi(sup_dev, MITIGATION_ACTIONS['supplier_development'], 0.10)
    assert pytest.approx(res_dev['action_cost']) == 200000.0
    assert pytest.approx(res_dev['risk_reduction']) == 100000.0 * 0.40 # 100,000 * 0.40 = 40,000
    assert pytest.approx(res_dev['roi']) == 40000.0 / 200000.0 # 0.20

    # Quarterly Monitoring
    sup_mon = {
        'supplier_id': 4,
        'total_p95_exposure': 100000.0,
        'dominant_risk_factor': 'reliability_risk'
    }
    res_mon = compute_roi(sup_mon, MITIGATION_ACTIONS['quarterly_monitoring'], 0.35)
    assert pytest.approx(res_mon['action_cost']) == 15000.0
    assert pytest.approx(res_mon['risk_reduction']) == 35000.0 * 0.15
    assert pytest.approx(res_mon['roi']) == (35000.0 * 0.15) / 15000.0


def test_compute_roi_zero_edge_cases():
    """Test compute_roi handles zero cost and zero risk reduction safely."""
    # Zero cost
    sup = {
        'supplier_id': 1,
        'total_p95_exposure': 100000.0
    }
    free_action = {
        'action_id': 'free',
        'base_cost_formula': lambda row: 0.0,
        'risk_reduction_estimate': 0.50
    }
    res_free = compute_roi(sup, free_action, 0.1)
    assert res_free['action_cost'] == 0.0
    assert res_free['roi'] == 0.0
    assert res_free['payback_period_years'] == 0.0

    # Zero risk reduction
    costly_action_zero_reduction = {
        'action_id': 'zero',
        'base_cost_formula': lambda row: 100.0,
        'risk_reduction_estimate': 0.0
    }
    res_zero = compute_roi(sup, costly_action_zero_reduction, 0.1)
    assert res_zero['action_cost'] == 100.0
    assert res_zero['risk_reduction'] == 0.0
    assert res_zero['roi'] == 0.0
    assert res_zero['payback_period_years'] == float('inf')


# ============================================================================
# 3. Tests for generate_playbook and playbook_summary
# ============================================================================

@pytest.fixture
def mock_playbook_inputs():
    df_priority = pd.DataFrame([
        {'supplier_id': 1, 'supplier_name': 'Supplier A', 'priority_quadrant': 'Critical Priority', 'total_p95_exposure': 500000.0, 'monthly_revenue': 20000.0},
        {'supplier_id': 2, 'supplier_name': 'Supplier B', 'priority_quadrant': 'Monitor Closely', 'total_p95_exposure': 300000.0, 'monthly_revenue': 15000.0},
        {'supplier_id': 3, 'supplier_name': 'Supplier C', 'priority_quadrant': 'Routine Review', 'total_p95_exposure': 100000.0, 'monthly_revenue': 5000.0}
    ])
    
    df_scores = pd.DataFrame([
        {'supplier_id': 1, 'risk_band': 'Critical', 'dependency_risk': 0.3, 'geographic_risk': 0.2, 'reliability_risk': 0.1, 'substitutability_risk': 0.8},
        {'supplier_id': 2, 'risk_band': 'High', 'dependency_risk': 0.9, 'geographic_risk': 0.1, 'reliability_risk': 0.2, 'substitutability_risk': 0.1},
        {'supplier_id': 3, 'risk_band': 'Low', 'dependency_risk': 0.1, 'geographic_risk': 0.1, 'reliability_risk': 0.1, 'substitutability_risk': 0.1}
    ])
    
    df_simulation_results = pd.DataFrame() # not directly used if worst-case is present
    
    df_worst_case = pd.DataFrame([
        {'supplier_id': 1, 'worst_case_scenario': 'port_strike', 'total_p95_exposure': 500000.0},
        {'supplier_id': 2, 'worst_case_scenario': 'factory_shutdown', 'total_p95_exposure': 300000.0},
        {'supplier_id': 3, 'worst_case_scenario': 'logistics_delay', 'total_p95_exposure': 100000.0}
    ])
    
    return df_priority, df_scores, df_simulation_results, df_worst_case


@patch('src.playbook.read_table')
def test_generate_playbook(mock_read, mock_playbook_inputs):
    """Test full playbook generation, columns, and ROI sorting."""
    # Set read_table to return empty DataFrames to trigger internal fallback (monthly_revenue column usage)
    mock_read.return_value = pd.DataFrame()
    
    df_priority, df_scores, df_simulation_results, df_worst_case = mock_playbook_inputs
    
    df_playbook = generate_playbook(df_priority, df_scores, df_simulation_results, df_worst_case)
    
    assert len(df_playbook) == 3
    expected_cols = [
        'supplier_id', 'supplier_name', 'priority_quadrant', 'dominant_risk_factor',
        'recommended_action', 'action_description', 'action_cost',
        'expected_annual_loss', 'risk_reduction', 'roi', 'payback_period_years'
    ]
    assert list(df_playbook.columns) == expected_cols
    
    # Assert sorted by ROI descending
    rois = df_playbook['roi'].tolist()
    assert sorted(rois, reverse=True) == rois
    
    # Check individual recommendations:
    # Supplier A: Critical Priority + substitutability_risk dominant -> Dual-Sourcing
    row_a = df_playbook[df_playbook['supplier_id'] == 1].iloc[0]
    assert row_a['recommended_action'] == 'Dual-Sourcing'
    assert row_a['dominant_risk_factor'] == 'substitutability_risk'

    # Supplier B: Monitor Closely + dependency_risk dominant -> Safety Stock Increase
    row_b = df_playbook[df_playbook['supplier_id'] == 2].iloc[0]
    assert row_b['recommended_action'] == 'Safety Stock Increase'
    assert row_b['dominant_risk_factor'] == 'dependency_risk'

    # Supplier C: Routine Review -> Quarterly Monitoring
    row_c = df_playbook[df_playbook['supplier_id'] == 3].iloc[0]
    assert row_c['recommended_action'] == 'Quarterly Monitoring'
    assert row_c['dominant_risk_factor'] == 'reliability_risk'


def test_playbook_summary():
    """Test portfolio-level playbook summary calculations."""
    df_playbook = pd.DataFrame([
        # Critical Priority (Included in budget/reduction)
        {'supplier_id': 1, 'priority_quadrant': 'Critical Priority', 'recommended_action': 'Dual-Sourcing', 'action_cost': 50000.0, 'risk_reduction': 100000.0},
        # Monitor Closely (Included in budget/reduction)
        {'supplier_id': 2, 'priority_quadrant': 'Monitor Closely', 'recommended_action': 'Safety Stock Increase', 'action_cost': 10000.0, 'risk_reduction': 20000.0},
        # Routine Review (EXCLUDED from budget/reduction totals, but included in action counts)
        {'supplier_id': 3, 'priority_quadrant': 'Routine Review', 'recommended_action': 'Quarterly Monitoring', 'action_cost': 15000.0, 'risk_reduction': 0.0}
    ])
    
    summary = playbook_summary(df_playbook)
    
    # Total budget = 50,000 + 10,000 = 60,000 (Routine Review's 15,000 excluded)
    assert pytest.approx(summary['total_mitigation_budget']) == 60000.0
    # Total risk eliminated = 100,000 + 20,000 = 120,000 (Routine Review's 0.0 excluded)
    assert pytest.approx(summary['total_risk_eliminated']) == 120000.0
    # Portfolio ROI = 120,000 / 60,000 = 2.0
    assert pytest.approx(summary['portfolio_roi']) == 2.0
    # Counts of all actions in playbook
    expected_counts = {
        'Dual-Sourcing': 1,
        'Safety Stock Increase': 1,
        'Quarterly Monitoring': 1
    }
    assert summary['action_counts'] == expected_counts


def test_playbook_summary_empty():
    """Verify playbook_summary behaves gracefully on empty playbooks."""
    summary = playbook_summary(pd.DataFrame())
    assert summary['total_mitigation_budget'] == 0.0
    assert summary['total_risk_eliminated'] == 0.0
    assert summary['portfolio_roi'] == 0.0
    assert summary['action_counts'] == {}
