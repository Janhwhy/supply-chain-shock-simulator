"""test_scoring.py — Unit tests for the resilience scoring logic."""

import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch
from src.scoring import (
    compute_dependency_risk,
    compute_geographic_risk,
    compute_reliability_risk,
    compute_substitutability_risk,
    compute_resilience_scores,
    get_score_interpretation,
    sensitivity_analysis
)


@pytest.fixture
def sample_suppliers():
    return pd.DataFrame([
        {"supplier_id": 1, "supplier_name": "Supplier A", "country": "USA", "tier": 1},
        {"supplier_id": 2, "supplier_name": "Supplier B", "country": "Germany", "tier": 2},
        {"supplier_id": 3, "supplier_name": "Supplier C", "country": "Germany", "tier": 2},
        {"supplier_id": 4, "supplier_name": "Supplier D", "country": "Germany", "tier": 1} # 3 peers in Germany
    ])


@pytest.fixture
def sample_suppliers_enriched():
    return pd.DataFrame([
        {"supplier_id": 1, "avg_delay_days": 1.0, "delay_volatility": 0.5},
        {"supplier_id": 2, "avg_delay_days": 2.0, "delay_volatility": 1.5},
        {"supplier_id": 3, "avg_delay_days": 3.0, "delay_volatility": 2.5},
        {"supplier_id": 4, "avg_delay_days": 1.0, "delay_volatility": 0.5}
    ])


@pytest.fixture
def sample_relationships():
    return pd.DataFrame([
        {"supplier_id": 1, "product_id": 10, "supply_share": 0.40, "is_sole_source": False},
        {"supplier_id": 1, "product_id": 20, "supply_share": 0.20, "is_sole_source": False},
        {"supplier_id": 2, "product_id": 10, "supply_share": 0.60, "is_sole_source": True},  # Share > 50% & Sole source
        {"supplier_id": 3, "product_id": 20, "supply_share": 0.80, "is_sole_source": False}  # Share > 50%
    ])


@pytest.fixture
def sample_simulation_results():
    return pd.DataFrame([
        {"supplier_id": 1, "scenario_id": "port_strike", "p95_impact": 1000.0},
        {"supplier_id": 2, "scenario_id": "port_strike", "p95_impact": 2000.0},
        {"supplier_id": 3, "scenario_id": "port_strike", "p95_impact": 3000.0},
        {"supplier_id": 4, "scenario_id": "port_strike", "p95_impact": 0.0}
    ])


@pytest.fixture(autouse=True)
def mock_db_read_table(sample_suppliers):
    """Mocks database read_table call so any internal DB dependencies are stubbed out."""
    with patch("src.db.read_table") as mock_read:
        mock_read.return_value = sample_suppliers
        yield mock_read


# ============================================================================
# Core Scoring Requirements Tests
# ============================================================================

def test_resilience_score_bounds(sample_suppliers, sample_suppliers_enriched, sample_relationships, sample_simulation_results):
    """Asserts that all resilience scores are between 0 and 1."""
    df_res = compute_resilience_scores(
        sample_suppliers,
        sample_suppliers_enriched,
        sample_relationships,
        sample_simulation_results
    )
    assert np.all(df_res['resilience_score'] >= 0.0)
    assert np.all(df_res['resilience_score'] <= 1.0)


def test_weights_validation(sample_suppliers, sample_suppliers_enriched, sample_relationships, sample_simulation_results):
    """Asserts that weights that don't sum to 1.0 (or lack keys) raise a ValueError."""
    # Test missing weight keys
    with pytest.raises(ValueError, match="weights dict must contain keys"):
        compute_resilience_scores(
            sample_suppliers,
            sample_suppliers_enriched,
            sample_relationships,
            sample_simulation_results,
            weights={'dependency': 0.5, 'geographic': 0.5}
        )
        
    # Test weights sum != 1.0
    with pytest.raises(ValueError, match="weights must sum to 1.0"):
        compute_resilience_scores(
            sample_suppliers,
            sample_suppliers_enriched,
            sample_relationships,
            sample_simulation_results,
            weights={'dependency': 0.4, 'geographic': 0.3, 'reliability': 0.2, 'substitutability': 0.2}
        )


def test_maximum_risk_supplier():
    """Asserts that a supplier with maximum values on all risk factors scores below 0.10."""
    df_sup = pd.DataFrame([
        {"supplier_id": 1, "supplier_name": "Resilient", "country": "USA", "tier": 1},
        {"supplier_id": 2, "supplier_name": "Risky", "country": "Germany", "tier": 2},
        {"supplier_id": 3, "supplier_name": "Co-loc 1", "country": "Germany", "tier": 2},
        {"supplier_id": 4, "supplier_name": "Co-loc 2", "country": "Germany", "tier": 2} # 3 peers in Germany
    ])
    df_sup_enr = pd.DataFrame([
        {"supplier_id": 1, "avg_delay_days": 0.0, "delay_volatility": 0.0},
        {"supplier_id": 2, "avg_delay_days": 10.0, "delay_volatility": 5.0},  # Max operational delays/volatility
        {"supplier_id": 3, "avg_delay_days": 1.0, "delay_volatility": 0.5},
        {"supplier_id": 4, "avg_delay_days": 1.0, "delay_volatility": 0.5}
    ])
    df_rel = pd.DataFrame([
        {"supplier_id": 1, "product_id": 10, "supply_share": 0.10, "is_sole_source": False},
        {"supplier_id": 2, "product_id": 10, "supply_share": 0.80, "is_sole_source": True},  # Share > 50% & Sole Source
        {"supplier_id": 3, "product_id": 20, "supply_share": 0.20, "is_sole_source": False},
        {"supplier_id": 4, "product_id": 20, "supply_share": 0.20, "is_sole_source": False}
    ])
    df_sim = pd.DataFrame([
        {"supplier_id": 1, "scenario_id": "port_strike", "p95_impact": 0.0},
        {"supplier_id": 2, "scenario_id": "port_strike", "p95_impact": 0.0},
        {"supplier_id": 3, "scenario_id": "port_strike", "p95_impact": 0.0},
        {"supplier_id": 4, "scenario_id": "port_strike", "p95_impact": 0.0}
    ])
    
    df_res = compute_resilience_scores(df_sup, df_sup_enr, df_rel, df_sim)
    risky_row = df_res[df_res['supplier_id'] == 2].iloc[0]
    
    # Verify risk factors hit 1.0 (maximum risk)
    assert risky_row['dependency_risk'] == 1.0
    assert risky_row['geographic_risk'] == 1.0
    assert risky_row['reliability_risk'] == 1.0
    assert risky_row['substitutability_risk'] == 1.0
    
    # Resilience score should be exactly 0.0, which is < 0.10
    assert risky_row['resilience_score'] < 0.10


def test_minimum_risk_supplier():
    """Asserts that a supplier with minimum values on all risk factors scores above 0.90."""
    df_sup = pd.DataFrame([
        {"supplier_id": 1, "supplier_name": "Resilient", "country": "USA", "tier": 1},
        {"supplier_id": 2, "supplier_name": "Risky", "country": "Germany", "tier": 2},
        {"supplier_id": 3, "supplier_name": "Co-loc 1", "country": "Germany", "tier": 2},
        {"supplier_id": 4, "supplier_name": "Co-loc 2", "country": "Germany", "tier": 2}
    ])
    df_sup_enr = pd.DataFrame([
        {"supplier_id": 1, "avg_delay_days": 0.0, "delay_volatility": 0.0},
        {"supplier_id": 2, "avg_delay_days": 10.0, "delay_volatility": 5.0},
        {"supplier_id": 3, "avg_delay_days": 1.0, "delay_volatility": 0.5},
        {"supplier_id": 4, "avg_delay_days": 1.0, "delay_volatility": 0.5}
    ])
    df_rel = pd.DataFrame([
        {"supplier_id": 1, "product_id": 10, "supply_share": 0.10, "is_sole_source": False},
        {"supplier_id": 2, "product_id": 10, "supply_share": 0.80, "is_sole_source": True},
        {"supplier_id": 3, "product_id": 20, "supply_share": 0.20, "is_sole_source": False},
        {"supplier_id": 4, "product_id": 20, "supply_share": 0.20, "is_sole_source": False}
    ])
    df_sim = pd.DataFrame([
        {"supplier_id": 1, "scenario_id": "port_strike", "p95_impact": 0.0},
        {"supplier_id": 2, "scenario_id": "port_strike", "p95_impact": 0.0},
        {"supplier_id": 3, "scenario_id": "port_strike", "p95_impact": 0.0},
        {"supplier_id": 4, "scenario_id": "port_strike", "p95_impact": 0.0}
    ])
    
    df_res = compute_resilience_scores(df_sup, df_sup_enr, df_rel, df_sim)
    resilient_row = df_res[df_res['supplier_id'] == 1].iloc[0]
    
    # Verify risk factors hit 0.0 (minimum risk)
    assert resilient_row['dependency_risk'] == 0.0
    assert resilient_row['geographic_risk'] == 0.0
    assert resilient_row['reliability_risk'] == 0.0
    assert resilient_row['substitutability_risk'] == 0.0
    
    # Resilience score should be exactly 1.0, which is > 0.90
    assert resilient_row['resilience_score'] > 0.90


def test_score_interpretation_boundaries():
    """Asserts get_score_interpretation returns the correct risk_band for boundary values."""
    # Boundaries:
    # score < 0.30 -> 'Critical' (e.g. 0.29)
    # 0.30 <= score <= 0.50 -> 'High' (e.g. 0.30, 0.50)
    # 0.50 < score <= 0.70 -> 'Medium' (e.g. 0.70)
    # score > 0.70 -> 'Low' (e.g. 0.71)
    assert get_score_interpretation(0.29)['risk_band'] == 'Critical'
    assert get_score_interpretation(0.30)['risk_band'] == 'High'
    assert get_score_interpretation(0.50)['risk_band'] == 'High'
    assert get_score_interpretation(0.70)['risk_band'] == 'Medium'
    assert get_score_interpretation(0.71)['risk_band'] == 'Low'


def test_sensitivity_analysis_shape(sample_suppliers, sample_suppliers_enriched, sample_relationships, sample_simulation_results):
    """Asserts sensitivity_analysis returns a DataFrame with the correct shape."""
    df_sens = sensitivity_analysis(
        sample_suppliers,
        sample_suppliers_enriched,
        sample_relationships,
        sample_simulation_results
    )
    
    # 4 suppliers in fixture
    expected_rows = len(sample_suppliers)
    expected_cols = 7  # supplier_id, supplier_name, default, dependency_heavy, geographic_heavy, reliability_heavy, substitutability_heavy
    assert df_sens.shape == (expected_rows, expected_cols)
    
    # Verify configurations are present as columns
    expected_columns = {
        'supplier_id', 'supplier_name', 'default', 'dependency_heavy', 
        'geographic_heavy', 'reliability_heavy', 'substitutability_heavy'
    }
    assert expected_columns.issubset(df_sens.columns)


# ============================================================================
# Additional Helper Function Tests
# ============================================================================

def test_compute_dependency_risk(sample_relationships):
    """Test dependency risk calculation and clipping above 50%."""
    dep_risk = compute_dependency_risk(sample_relationships)
    
    # Supplier 1 max share: 0.40. Supplier 2 max: 0.60 (clips to 0.50). Supplier 3 max: 0.80 (clips to 0.50).
    # Normalised bounds: Min = 0.40, Max = 0.50.
    # Supplier 1 -> 0.0, Supplier 2 -> 1.0, Supplier 3 -> 1.0.
    assert dep_risk[1] == 0.0
    assert dep_risk[2] == 1.0
    assert dep_risk[3] == 1.0


def test_compute_geographic_risk(sample_suppliers):
    """Test geographic risk fraction and 3+ co-located peer penalty."""
    geo_risk = compute_geographic_risk(sample_suppliers)
    
    # N = 4. Counts: USA -> 1, Germany -> 3.
    # Supplier 1 (USA): frac = (1-1)/(4-1) = 0.0. Normalized = 0.0.
    # Germany peers (Supplier 2, 3, 4): frac = (3-1)/(4-1) = 2/3. Count >= 3 => penalty +0.15 => 0.8167. Normalized = 1.0.
    assert geo_risk[1] == 0.0
    assert geo_risk[2] == 1.0
    assert geo_risk[3] == 1.0
    assert geo_risk[4] == 1.0


def test_compute_reliability_risk(sample_suppliers_enriched):
    """Test operational reliability risk equal weighting composite."""
    rel_risk = compute_reliability_risk(sample_suppliers_enriched)
    
    # Supplier 1 & 4 (delay=1.0, vol=0.5) - minimum values -> normalized 0.0
    # Supplier 3 (delay=3.0, vol=2.5) - maximum values -> normalized 1.0
    # Supplier 2 (delay=2.0, vol=1.5) - middle values -> normalized 0.5
    assert rel_risk[1] == 0.0
    assert rel_risk[4] == 0.0
    assert rel_risk[2] == 0.5
    assert rel_risk[3] == 1.0


def test_compute_substitutability_risk(sample_relationships):
    """Test average alternatives logic and is_sole_source override."""
    sub_risk = compute_substitutability_risk(sample_relationships)
    
    # Product 10 count: 2 (alt count = 1). Product 20 count: 2 (alt count = 1).
    # Supplier 1 average alternatives = 1.0.
    # Supplier 2 is sole source -> overridden to 1.0.
    # Supplier 3 average alternatives = 1.0.
    # Normalized: Supplier 1 and 3 -> 0.0. Supplier 2 -> 1.0.
    assert sub_risk[1] == 0.0
    assert sub_risk[2] == 1.0
    assert sub_risk[3] == 0.0
