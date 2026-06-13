"""test_simulation.py — Unit tests for the Monte Carlo simulation engine."""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch
from src.scenarios import DisruptionScenario
from src.simulation import (
    estimate_beta_params,
    get_supplier_normalization_bounds,
    run_simulation,
    run_all_simulations,
    analyse_distribution,
    identify_worst_case_scenarios
)


@pytest.fixture
def sample_suppliers():
    return pd.DataFrame([
        {
            "supplier_id": 1,
            "supplier_name": "Supplier A",
            "country": "China",
            "delay_volatility": 1.5,
            "rejection_rate": 0.01
        },
        {
            "supplier_id": 2,
            "supplier_name": "Supplier B",
            "country": "Germany",
            "delay_volatility": 2.5,
            "rejection_rate": 0.05
        }
    ])


@pytest.fixture
def sample_products():
    return pd.DataFrame([
        {"product_id": 10, "unit_cost": 100.0, "monthly_demand": 50},  # Monthly revenue = 5000
        {"product_id": 20, "unit_cost": 200.0, "monthly_demand": 30}   # Monthly revenue = 6000
    ])


@pytest.fixture
def sample_relationships():
    return pd.DataFrame([
        {"supplier_id": 1, "product_id": 10, "supply_share": 0.6},  # weighted revenue = 0.6 * 5000 = 3000
        {"supplier_id": 1, "product_id": 20, "supply_share": 0.4},  # weighted revenue = 0.4 * 6000 = 2400
        # Total weight for Supplier 1 = 5400
        {"supplier_id": 2, "product_id": 10, "supply_share": 0.4}   # weighted revenue = 0.4 * 5000 = 2000
        # Total weight for Supplier 2 = 2000
    ])


@pytest.fixture
def port_strike():
    return DisruptionScenario(
        scenario_id="port_strike",
        display_name="Port Strike",
        annual_probability=0.20,
        duration_min_days=10,
        duration_max_days=30,
        supply_loss_min=0.50,
        supply_loss_max=0.90,
        geographic_modifier=True,
        description="Geographically exposed port strike"
    )


@pytest.fixture(autouse=True)
def mock_db_read_table(sample_suppliers):
    """Mocks database read_table call so the simulation tests run without a live PG connection."""
    with patch("src.simulation.read_table") as mock_read:
        mock_read.return_value = sample_suppliers
        yield mock_read


# ============================================================================
# Core Simulation Logic Tests
# ============================================================================

def test_run_simulation_keys(sample_suppliers, port_strike, sample_relationships, sample_products):
    """Asserts that run_simulation returns a dictionary containing all expected keys."""
    res = run_simulation(
        supplier=sample_suppliers.iloc[0],
        scenario=port_strike,
        supply_relationships=sample_relationships,
        products=sample_products,
        n_runs=100
    )
    assert isinstance(res, dict)
    expected_keys = {
        'supplier_id', 'scenario_id', 'n_runs', 'p50_impact', 'p95_impact',
        'mean_impact', 'std_impact', 'zero_impact_fraction', 'impact_distribution'
    }
    assert expected_keys.issubset(res.keys())


def test_run_simulation_p95_p50_relation(sample_suppliers, port_strike, sample_relationships, sample_products):
    """Asserts that P95 is always greater than or equal to P50."""
    res = run_simulation(
        supplier=sample_suppliers.iloc[0],
        scenario=port_strike,
        supply_relationships=sample_relationships,
        products=sample_products,
        n_runs=1000
    )
    assert res['p95_impact'] >= res['p50_impact']


def test_run_simulation_zero_impact_fraction_range(sample_suppliers, port_strike, sample_relationships, sample_products):
    """Asserts that zero_impact_fraction is between 0 and 1."""
    res = run_simulation(
        supplier=sample_suppliers.iloc[0],
        scenario=port_strike,
        supply_relationships=sample_relationships,
        products=sample_products,
        n_runs=500
    )
    assert 0.0 <= res['zero_impact_fraction'] <= 1.0


def test_run_simulation_non_negative_impacts(sample_suppliers, port_strike, sample_relationships, sample_products):
    """Asserts that simulated impact values are always non-negative."""
    res = run_simulation(
        supplier=sample_suppliers.iloc[0],
        scenario=port_strike,
        supply_relationships=sample_relationships,
        products=sample_products,
        n_runs=500
    )
    assert np.all(res['impact_distribution'] >= 0.0)
    assert res['p50_impact'] >= 0.0
    assert res['p95_impact'] >= 0.0
    assert res['mean_impact'] >= 0.0


def test_run_simulation_runs_consistency(sample_suppliers, port_strike, sample_relationships, sample_products):
    """Asserts that setting n_runs=100 produces consistent output structure regardless of run count."""
    res100 = run_simulation(
        supplier=sample_suppliers.iloc[0],
        scenario=port_strike,
        supply_relationships=sample_relationships,
        products=sample_products,
        n_runs=100
    )
    res50 = run_simulation(
        supplier=sample_suppliers.iloc[0],
        scenario=port_strike,
        supply_relationships=sample_relationships,
        products=sample_products,
        n_runs=50
    )
    
    # Structure must be identical
    assert res100.keys() == res50.keys()
    # Output arrays must match the requested n_runs size
    assert len(res100['impact_distribution']) == 100
    assert len(res50['impact_distribution']) == 50
    assert res100['n_runs'] == 100
    assert res50['n_runs'] == 50


def test_run_simulation_zero_probability(sample_suppliers, sample_relationships, sample_products):
    """Asserts that a scenario with annual_probability=0 produces zero_impact_fraction=1.0 (shock never occurs)."""
    zero_prob_scenario = DisruptionScenario(
        scenario_id="zero_prob",
        display_name="Zero Prob",
        annual_probability=0.0,
        duration_min_days=10,
        duration_max_days=20,
        supply_loss_min=0.5,
        supply_loss_max=0.9,
        description="Zero probability scenario"
    )
    res = run_simulation(
        supplier=sample_suppliers.iloc[0],
        scenario=zero_prob_scenario,
        supply_relationships=sample_relationships,
        products=sample_products,
        n_runs=100
    )
    assert res['zero_impact_fraction'] == 1.0
    assert np.all(res['impact_distribution'] == 0.0)
    assert res['p50_impact'] == 0.0
    assert res['p95_impact'] == 0.0
    assert res['mean_impact'] == 0.0


def test_run_simulation_certain_disruption(sample_suppliers, sample_relationships, sample_products):
    """Asserts that a scenario with annual_probability=1 and supply_loss_min=1.0 produces zero_impact_fraction=0.0."""
    certain_scenario = DisruptionScenario(
        scenario_id="certain",
        display_name="Certain",
        annual_probability=1.0,
        duration_min_days=30,  # 30 days means duration / 30 = 1.0
        duration_max_days=30,
        supply_loss_min=1.0,   # loss = 1.0
        supply_loss_max=1.0,
        description="Certain scenario"
    )
    res = run_simulation(
        supplier=sample_suppliers.iloc[0],
        scenario=certain_scenario,
        supply_relationships=sample_relationships,
        products=sample_products,
        n_runs=100
    )
    assert res['zero_impact_fraction'] == 0.0
    assert np.all(res['impact_distribution'] > 0.0)
    assert res['mean_impact'] == 5400.0  # Weight 5400 * duration 1.0 * loss 1.0


# ============================================================================
# Additional Helper Function Tests
# ============================================================================

def test_estimate_beta_params():
    """Test Method of Moments Beta parameter estimation."""
    alpha, beta = estimate_beta_params(0.60, 1.00)
    assert pytest.approx(alpha) == 4.0
    assert pytest.approx(beta) == 4.0

    # Test identical min-max fallback
    alpha_zero, beta_zero = estimate_beta_params(0.50, 0.50)
    assert alpha_zero == 4.0
    assert beta_zero == 4.0


def test_analyse_distribution():
    """Test distribution analysis statistics calculation."""
    impact_array = np.array([0.0, 100.0, 200.0, 300.0, 400.0])
    stats = analyse_distribution(impact_array, "Supplier A", "Port Strike")
    
    assert pytest.approx(stats['mean']) == 200.0
    assert pytest.approx(stats['median']) == 200.0
    assert pytest.approx(stats['p50']) == 200.0
    assert pytest.approx(stats['p95']) == 380.0
    assert pytest.approx(stats['var_ratio']) == 380.0 / 200.0
    assert 'skewness' in stats
    assert 'kurtosis' in stats


def test_identify_worst_case_scenarios():
    """Test identification of worst case scenario and exposure per supplier."""
    df_results = pd.DataFrame([
        {"supplier_id": 1, "scenario_id": "port_strike", "p95_impact": 5000.0},
        {"supplier_id": 1, "scenario_id": "factory_shutdown", "p95_impact": 8000.0},
        {"supplier_id": 2, "scenario_id": "port_strike", "p95_impact": 3000.0},
        {"supplier_id": 2, "scenario_id": "factory_shutdown", "p95_impact": 1000.0}
    ])
    
    worst = identify_worst_case_scenarios(df_results)
    assert len(worst) == 2
    
    # Supplier 1 worst case is factory shutdown (8000), total exposure = 13000
    row1 = worst[worst['supplier_id'] == 1].iloc[0]
    assert row1['worst_case_scenario'] == 'factory_shutdown'
    assert pytest.approx(row1['max_p95_impact']) == 8000.0
    assert pytest.approx(row1['total_p95_exposure']) == 13000.0
    
    # Supplier 2 worst case is port strike (3000), total exposure = 4000
    row2 = worst[worst['supplier_id'] == 2].iloc[0]
    assert row2['worst_case_scenario'] == 'port_strike'
    assert pytest.approx(row2['max_p95_impact']) == 3000.0
    assert pytest.approx(row2['total_p95_exposure']) == 4000.0


def test_run_all_simulations(sample_suppliers, port_strike, sample_relationships, sample_products):
    """Test batch simulation run_all_simulations."""
    scenarios = [port_strike]
    df_all = run_all_simulations(
        df_suppliers=sample_suppliers,
        df_scenarios=scenarios,
        df_relationships=sample_relationships,
        df_products=sample_products,
        n_runs=10
    )
    
    assert len(df_all) == 2  # 2 suppliers * 1 scenario
    assert 'supplier_id' in df_all.columns
    assert 'scenario_id' in df_all.columns
    assert 'p95_impact' in df_all.columns
    assert 'impact_distribution' in df_all.columns
