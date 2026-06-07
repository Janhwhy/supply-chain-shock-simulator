"""test_scenarios.py — Unit tests for the disruption scenarios module."""

import unittest
import pandas as pd
from src.scenarios import (
    get_all_scenarios,
    get_scenario_by_id,
    scenarios_to_dataframe,
    DisruptionScenario
)


class TestScenariosModule(unittest.TestCase):
    """Unit tests for src/scenarios.py."""

    def test_get_all_scenarios(self):
        """Test that get_all_scenarios returns all five scenarios with correct attributes."""
        scenarios = get_all_scenarios()
        self.assertEqual(len(scenarios), 5)
        
        # Verify that they are DisruptionScenario instances
        for scenario in scenarios:
            self.assertIsInstance(scenario, DisruptionScenario)

        # Check a few specific attributes to ensure correct instantiation
        port_strike = next(s for s in scenarios if s.scenario_id == "port_strike")
        self.assertEqual(port_strike.display_name, "Port Strike")
        self.assertEqual(port_strike.annual_probability, 0.18)
        self.assertEqual(port_strike.duration_min_days, 14)
        self.assertEqual(port_strike.duration_max_days, 45)
        self.assertEqual(port_strike.supply_loss_min, 0.60)
        self.assertEqual(port_strike.supply_loss_max, 1.00)
        self.assertTrue(port_strike.geographic_modifier)
        self.assertFalse(port_strike.reliability_modulated)
        
        factory_shutdown = next(s for s in scenarios if s.scenario_id == "factory_shutdown")
        self.assertTrue(factory_shutdown.reliability_modulated)

    def test_get_scenario_by_id_success(self):
        """Test successful scenario lookup by ID."""
        scenario = get_scenario_by_id("currency_shock")
        self.assertEqual(scenario.display_name, "Currency Shock")
        self.assertTrue(scenario.affects_all_in_country)

    def test_get_scenario_by_id_not_found(self):
        """Test that get_scenario_by_id raises ValueError for invalid ID."""
        with self.assertRaises(ValueError):
            get_scenario_by_id("non_existent_scenario_id")

    def test_scenarios_to_dataframe(self):
        """Test that scenarios_to_dataframe returns a valid pandas DataFrame."""
        df = scenarios_to_dataframe()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 5)
        self.assertIn("scenario_id", df.columns)
        self.assertIn("display_name", df.columns)
        self.assertIn("annual_probability", df.columns)
        
        # Verify specific content
        self.assertEqual(df.loc[df["scenario_id"] == "quality_failure", "rejection_modulated"].values[0], True)


if __name__ == "__main__":
    unittest.main()
