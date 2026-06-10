"""test_scoring.py — Unit tests for the resilience scoring logic."""

import unittest
import pandas as pd
import numpy as np
from src.scoring import (
    compute_dependency_risk,
    compute_geographic_risk,
    compute_reliability_risk,
    compute_substitutability_risk,
    compute_resilience_scores,
    get_score_interpretation,
    sensitivity_analysis
)


class TestScoringModule(unittest.TestCase):
    """Unit tests for src/scoring.py."""

    def setUp(self):
        # Set up mock DataFrames
        self.df_relationships = pd.DataFrame([
            {"supplier_id": 1, "product_id": 10, "supply_share": 0.40, "is_sole_source": False},
            {"supplier_id": 1, "product_id": 20, "supply_share": 0.20, "is_sole_source": False},
            {"supplier_id": 2, "product_id": 10, "supply_share": 0.60, "is_sole_source": True},  # Share > 50% & Sole source
            {"supplier_id": 3, "product_id": 20, "supply_share": 0.80, "is_sole_source": False}  # Share > 50%
        ])

        self.df_suppliers = pd.DataFrame([
            {"supplier_id": 1, "supplier_name": "Supplier A", "country": "USA", "tier": 1},
            {"supplier_id": 2, "supplier_name": "Supplier B", "country": "Germany", "tier": 2},
            {"supplier_id": 3, "supplier_name": "Supplier C", "country": "Germany", "tier": 2},
            {"supplier_id": 4, "supplier_name": "Supplier D", "country": "Germany", "tier": 1} # 3 peers in Germany
        ])

        self.df_suppliers_enriched = pd.DataFrame([
            {"supplier_id": 1, "avg_delay_days": 1.0, "delay_volatility": 0.5},
            {"supplier_id": 2, "avg_delay_days": 2.0, "delay_volatility": 1.5},
            {"supplier_id": 3, "avg_delay_days": 3.0, "delay_volatility": 2.5},
            {"supplier_id": 4, "avg_delay_days": 1.0, "delay_volatility": 0.5}
        ])

        self.df_simulation_results = pd.DataFrame([
            {"supplier_id": 1, "scenario_id": "port_strike", "p95_impact": 1000.0},
            {"supplier_id": 2, "scenario_id": "port_strike", "p95_impact": 2000.0},
            {"supplier_id": 3, "scenario_id": "port_strike", "p95_impact": 3000.0},
            {"supplier_id": 4, "scenario_id": "port_strike", "p95_impact": 0.0}
        ])

    def test_compute_dependency_risk(self):
        """Test dependency risk computation and >50% max risk mapping."""
        dep_risk = compute_dependency_risk(self.df_relationships)
        
        # Max shares: Supplier 1 -> 0.40, Supplier 2 -> 0.60 (clips to 0.50), Supplier 3 -> 0.80 (clips to 0.50)
        # Clipped shares: Supplier 1 -> 0.40, Supplier 2 -> 0.50, Supplier 3 -> 0.50
        # Normalised: min (0.40) to max (0.50).
        # Supplier 1 -> 0.0, Supplier 2 & 3 -> 1.0
        self.assertEqual(dep_risk[1], 0.0)
        self.assertEqual(dep_risk[2], 1.0)
        self.assertEqual(dep_risk[3], 1.0)

    def test_compute_geographic_risk(self):
        """Test geographic risk fraction and 3+ peer penalty logic."""
        geo_risk = compute_geographic_risk(self.df_suppliers)
        
        # Total suppliers N = 4.
        # Counts: USA -> 1, Germany -> 3.
        # Supplier 1 (USA): frac = (1 - 1)/(4 - 1) = 0.0. No penalty. raw = 0.0
        # Supplier 2, 3, 4 (Germany): frac = (3 - 1)/(4 - 1) = 2/3 = 0.6667. Has penalty (+0.15) => 0.8167.
        # Normalised: Supplier 1 -> 0.0, Germany peers -> 1.0
        self.assertEqual(geo_risk[1], 0.0)
        self.assertEqual(geo_risk[2], 1.0)
        self.assertEqual(geo_risk[3], 1.0)
        self.assertEqual(geo_risk[4], 1.0)

    def test_compute_reliability_risk(self):
        """Test operational reliability risk equal weighting composite."""
        rel_risk = compute_reliability_risk(self.df_suppliers_enriched)
        
        # Supplier 1 & 4 (delay=1.0, vol=0.5) - minimum values, normalized should be 0.0 + 0.0 = 0.0
        # Supplier 3 (delay=3.0, vol=2.5) - maximum values, normalized should be 1.0 + 1.0 = 1.0
        # Supplier 2 (delay=2.0, vol=1.5) - middle values, delay_scaled = 0.5, vol_scaled = 0.5, risk = 0.5
        self.assertEqual(rel_risk[1], 0.0)
        self.assertEqual(rel_risk[4], 0.0)
        self.assertEqual(rel_risk[2], 0.5)
        self.assertEqual(rel_risk[3], 1.0)

    def test_compute_substitutability_risk(self):
        """Test average alternatives logic and is_sole_source override."""
        sub_risk = compute_substitutability_risk(self.df_relationships)
        
        # Product 10 suppliers: {1, 2} (2 suppliers => alt_count = 1)
        # Product 20 suppliers: {1, 3} (2 suppliers => alt_count = 1)
        # Supplier 1 alts: Product 10 -> 1, Product 20 -> 1. Avg = 1.0. inv = 1.0
        # Supplier 2 is sole source -> gets 1.0 override
        # Supplier 3 alts: Product 20 -> 1. Avg = 1.0. inv = 1.0
        # Since everyone gets same inv = 1.0, and supplier 2 is overridden to 1.0,
        # non-sole-source (Supplier 1 and 3) should scale to 0.0 as max_val == min_val.
        self.assertEqual(sub_risk[1], 0.0)
        self.assertEqual(sub_risk[2], 1.0)
        self.assertEqual(sub_risk[3], 0.0)

    def test_compute_resilience_scores(self):
        """Test composite resilience scoring and weights validation."""
        # 1. Test weight validations
        with self.assertRaises(ValueError):
            # Missing key
            compute_resilience_scores(
                self.df_suppliers, self.df_suppliers_enriched,
                self.df_relationships, self.df_simulation_results,
                weights={'dependency': 0.5, 'geographic': 0.5}
            )
            
        with self.assertRaises(ValueError):
            # Sum != 1.0
            compute_resilience_scores(
                self.df_suppliers, self.df_suppliers_enriched,
                self.df_relationships, self.df_simulation_results,
                weights={'dependency': 0.4, 'geographic': 0.3, 'reliability': 0.2, 'substitutability': 0.2}
            )
            
        # 2. Test resilience scores calculation (Default weights: dep=0.4, geo=0.25, rel=0.20, sub=0.15)
        # Supplier 1: dep=0.0, geo=0.0, rel=0.0, sub=0.0. Composite risk = 0.0, Resilience score = 1.0 => Band: Low
        # Supplier 2: dep=1.0, geo=1.0, rel=0.5, sub=1.0.
        # Composite risk = 0.4*1.0 + 0.25*1.0 + 0.2*0.5 + 0.15*1.0 = 0.4 + 0.25 + 0.1 + 0.15 = 0.90
        # Resilience score = 1.0 - 0.90 = 0.10 => Band: Critical
        df_res = compute_resilience_scores(
            self.df_suppliers, self.df_suppliers_enriched,
            self.df_relationships, self.df_simulation_results
        )
        
        row1 = df_res[df_res['supplier_id'] == 1].iloc[0]
        self.assertAlmostEqual(row1['resilience_score'], 1.0)
        self.assertEqual(row1['risk_band'], 'Low')
        
        row2 = df_res[df_res['supplier_id'] == 2].iloc[0]
        self.assertAlmostEqual(row2['resilience_score'], 0.1)
        self.assertEqual(row2['risk_band'], 'Critical')

    def test_get_score_interpretation(self):
        """Test score interpretation mappings."""
        critical_desc = get_score_interpretation(0.15)
        self.assertEqual(critical_desc['risk_band'], 'Critical')
        self.assertEqual(critical_desc['urgency_level'], 'Immediate')
        
        low_desc = get_score_interpretation(0.85)
        self.assertEqual(low_desc['risk_band'], 'Low')
        self.assertEqual(low_desc['urgency_level'], 'Low')

    def test_sensitivity_analysis(self):
        """Test sensitivity analysis output structure."""
        df_sens = sensitivity_analysis(
            self.df_suppliers, self.df_suppliers_enriched,
            self.df_relationships, self.df_simulation_results
        )
        
        # Should return a row for each of the 4 suppliers
        self.assertEqual(len(df_sens), 4)
        self.assertIn('default', df_sens.columns)
        self.assertIn('dependency_heavy', df_sens.columns)
        self.assertIn('geographic_heavy', df_sens.columns)
        self.assertIn('reliability_heavy', df_sens.columns)
        self.assertIn('substitutability_heavy', df_sens.columns)


if __name__ == '__main__':
    unittest.main()
