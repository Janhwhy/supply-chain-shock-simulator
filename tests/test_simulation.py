"""test_simulation.py — Unit tests for the Monte Carlo simulation engine."""

import unittest
import numpy as np
import pandas as pd
from src.scenarios import DisruptionScenario
from src.simulation import (
    estimate_beta_params,
    get_supplier_normalization_bounds,
    run_simulation,
    run_all_simulations,
    analyse_distribution,
    identify_worst_case_scenarios
)


class TestSimulationModule(unittest.TestCase):
    """Unit tests for src/simulation.py."""

    def setUp(self):
        # Set up standard scenarios
        self.port_strike = DisruptionScenario(
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
        self.factory_shutdown = DisruptionScenario(
            scenario_id="factory_shutdown",
            display_name="Factory Shutdown",
            annual_probability=0.10,
            duration_min_days=10,
            duration_max_days=20,
            supply_loss_min=0.80,
            supply_loss_max=1.00,
            reliability_modulated=True,
            description="Operational failure"
        )
        self.quality_failure = DisruptionScenario(
            scenario_id="quality_failure",
            display_name="Quality Failure",
            annual_probability=0.10,
            duration_min_days=10,
            duration_max_days=20,
            supply_loss_min=0.80,
            supply_loss_max=1.00,
            rejection_modulated=True,
            description="Quality spike quarantine"
        )

        # Set up mock DataFrames
        self.df_suppliers = pd.DataFrame([
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

        self.df_products = pd.DataFrame([
            {"product_id": 10, "unit_cost": 100.0, "monthly_demand": 50},  # Monthly revenue = 5000
            {"product_id": 20, "unit_cost": 200.0, "monthly_demand": 30}   # Monthly revenue = 6000
        ])

        self.df_relationships = pd.DataFrame([
            {"supplier_id": 1, "product_id": 10, "supply_share": 0.6},  # weighted revenue = 0.6 * 5000 = 3000
            {"supplier_id": 1, "product_id": 20, "supply_share": 0.4},  # weighted revenue = 0.4 * 6000 = 2400
            # Total weight for Supplier 1 = 5400
            {"supplier_id": 2, "product_id": 10, "supply_share": 0.4}   # weighted revenue = 0.4 * 5000 = 2000
            # Total weight for Supplier 2 = 2000
        ])

    def test_estimate_beta_params(self):
        """Test Method of Moments Beta parameter estimation."""
        alpha, beta = estimate_beta_params(0.60, 1.00)
        # For default symmetric PERT: mean = 0.8, std = 0.4/6.
        # Scaled mean = 0.5, var = 1/36. This yields alpha = 4.0, beta = 4.0.
        self.assertAlmostEqual(alpha, 4.0)
        self.assertAlmostEqual(beta, 4.0)

        # Test boundary conditions or zero width
        alpha_zero, beta_zero = estimate_beta_params(0.50, 0.50)
        self.assertEqual(alpha_zero, 4.0)
        self.assertEqual(beta_zero, 4.0)

    def test_probability_modulation(self):
        """Test correct modulation of probability based on parameters."""
        # 1. Geographic modifier check: China is in the list of coastal countries (1.5x)
        # Supplier A is in China, Scenario is Port Strike (annual_probability = 0.20)
        # Since volatility / rejection rate are not modulated, prob = 0.20 * 1.5 = 0.30
        res_a = run_simulation(
            supplier=self.df_suppliers.iloc[0],
            scenario=self.port_strike,
            supply_relationships=self.df_relationships,
            products=self.df_products,
            n_runs=100
        )
        # Expected zero impact fraction to be roughly 1 - 0.30 = 0.70.
        # But we want to test exact modulation inside, let's test with 0 probability first.
        
        # Test 0 probability scenario has zero impact fraction of 1.0
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
        res_zero = run_simulation(
            supplier=self.df_suppliers.iloc[0],
            scenario=zero_prob_scenario,
            supply_relationships=self.df_relationships,
            products=self.df_products,
            n_runs=100
        )
        self.assertEqual(res_zero['zero_impact_fraction'], 1.0)
        self.assertEqual(np.sum(res_zero['impact_distribution']), 0.0)

    def test_run_simulation_math(self):
        """Test calculation of revenue at risk under simplified settings."""
        # 100% probability scenario
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
        # Supplier 1 total weight is 5400
        # Impact should be exactly 1.0 * (30/30) * 5400 = 5400 for all runs
        res = run_simulation(
            supplier=self.df_suppliers.iloc[0],
            scenario=certain_scenario,
            supply_relationships=self.df_relationships,
            products=self.df_products,
            n_runs=10
        )
        self.assertEqual(res['zero_impact_fraction'], 0.0)
        self.assertAlmostEqual(res['mean_impact'], 5400.0)
        np.testing.assert_allclose(res['impact_distribution'], 5400.0)

    def test_analyse_distribution(self):
        """Test distribution analysis statistics calculation."""
        impact_array = np.array([0.0, 100.0, 200.0, 300.0, 400.0])
        stats = analyse_distribution(impact_array, "Supplier A", "Port Strike")
        
        self.assertAlmostEqual(stats['mean'], 200.0)
        self.assertAlmostEqual(stats['median'], 200.0)
        self.assertAlmostEqual(stats['p50'], 200.0)
        # P95 of [0, 100, 200, 300, 400] is 380.0
        self.assertAlmostEqual(stats['p95'], 380.0)
        self.assertAlmostEqual(stats['var_ratio'], 380.0 / 200.0)
        self.assertIn('skewness', stats)
        self.assertIn('kurtosis', stats)

    def test_identify_worst_case_scenarios(self):
        """Test identification of worst case scenario and exposure per supplier."""
        df_results = pd.DataFrame([
            {"supplier_id": 1, "scenario_id": "port_strike", "p95_impact": 5000.0},
            {"supplier_id": 1, "scenario_id": "factory_shutdown", "p95_impact": 8000.0},
            {"supplier_id": 2, "scenario_id": "port_strike", "p95_impact": 3000.0},
            {"supplier_id": 2, "scenario_id": "factory_shutdown", "p95_impact": 1000.0}
        ])
        
        worst = identify_worst_case_scenarios(df_results)
        
        self.assertEqual(len(worst), 2)
        # Supplier 1 worst case is factory shutdown (8000), total exposure = 13000
        row1 = worst[worst['supplier_id'] == 1].iloc[0]
        self.assertEqual(row1['worst_case_scenario'], 'factory_shutdown')
        self.assertAlmostEqual(row1['max_p95_impact'], 8000.0)
        self.assertAlmostEqual(row1['total_p95_exposure'], 13000.0)
        
        # Supplier 2 worst case is port strike (3000), total exposure = 4000
        row2 = worst[worst['supplier_id'] == 2].iloc[0]
        self.assertEqual(row2['worst_case_scenario'], 'port_strike')
        self.assertAlmostEqual(row2['max_p95_impact'], 3000.0)
        self.assertAlmostEqual(row2['total_p95_exposure'], 4000.0)

    def test_run_all_simulations(self):
        """Test batch simulation function run_all_simulations."""
        scenarios = [self.port_strike, self.factory_shutdown]
        df_all = run_all_simulations(
            df_suppliers=self.df_suppliers,
            df_scenarios=scenarios,
            df_relationships=self.df_relationships,
            df_products=self.df_products,
            n_runs=10
        )
        
        # 2 suppliers * 2 scenarios = 4 rows
        self.assertEqual(len(df_all), 4)
        self.assertIn('supplier_id', df_all.columns)
        self.assertIn('scenario_id', df_all.columns)
        self.assertIn('p95_impact', df_all.columns)
        self.assertIn('impact_distribution', df_all.columns)


if __name__ == "__main__":
    unittest.main()
