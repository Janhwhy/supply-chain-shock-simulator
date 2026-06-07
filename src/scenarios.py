"""scenarios.py — Defines supply chain disruption scenarios and parameters."""

from dataclasses import dataclass, asdict
from typing import List
import pandas as pd


@dataclass
class DisruptionScenario:
    """
    Configuration dataclass defining a supply chain disruption scenario
    for use in the Monte Carlo simulation engine.

    Attributes:
        scenario_id (str): Unique identifier for the scenario.
        display_name (str): Human-readable display name.
        annual_probability (float): Annual probability of the scenario occurring (0.0 to 1.0).
        duration_min_days (int): Minimum duration of the disruption in days.
        duration_max_days (int): Maximum duration of the disruption in days.
        supply_loss_min (float): Minimum proportion of supply lost (0.0 to 1.0).
        supply_loss_max (float): Maximum proportion of supply lost (0.0 to 1.0).
        description (str): Detailed text description of the scenario.
        geographic_modifier (bool): If True, scenario only affects suppliers in high-exposure coastal countries.
        reliability_modulated (bool): If True, probability is scaled by supplier delay volatility.
        affects_all_in_country (bool): If True, all suppliers in target country are affected simultaneously.
        rejection_modulated (bool): If True, probability is scaled by supplier rejection rate.
    """
    scenario_id: str
    display_name: str
    annual_probability: float
    duration_min_days: int
    duration_max_days: int
    supply_loss_min: float
    supply_loss_max: float
    description: str
    geographic_modifier: bool = False
    reliability_modulated: bool = False
    affects_all_in_country: bool = False
    rejection_modulated: bool = False


# Predefined disruption scenarios
PORT_STRIKE = DisruptionScenario(
    scenario_id="port_strike",
    display_name="Port Strike",
    annual_probability=0.18,
    duration_min_days=14,
    duration_max_days=45,
    supply_loss_min=0.60,
    supply_loss_max=1.00,
    geographic_modifier=True,
    description="Sudden port closure disrupting maritime freight for geographically exposed suppliers"
)

FACTORY_SHUTDOWN = DisruptionScenario(
    scenario_id="factory_shutdown",
    display_name="Factory Shutdown",
    annual_probability=0.12,
    duration_min_days=7,
    duration_max_days=30,
    supply_loss_min=0.80,
    supply_loss_max=1.00,
    reliability_modulated=True,
    description="Supplier-specific production halt driven by operational failure"
)

CURRENCY_SHOCK = DisruptionScenario(
    scenario_id="currency_shock",
    display_name="Currency Shock",
    annual_probability=0.12,
    duration_min_days=30,
    duration_max_days=90,
    supply_loss_min=0.20,
    supply_loss_max=0.50,
    affects_all_in_country=True,
    description="Macroeconomic currency devaluation affecting all suppliers in a target currency zone"
)

LOGISTICS_DELAY = DisruptionScenario(
    scenario_id="logistics_delay",
    display_name="Logistics Delay",
    annual_probability=0.35,
    duration_min_days=5,
    duration_max_days=21,
    supply_loss_min=0.30,
    supply_loss_max=0.70,
    description="Systemic transport network slowdown causing widespread delivery delays"
)

QUALITY_FAILURE = DisruptionScenario(
    scenario_id="quality_failure",
    display_name="Quality Failure",
    annual_probability=0.10,
    duration_min_days=14,
    duration_max_days=60,
    supply_loss_min=0.40,
    supply_loss_max=0.90,
    rejection_modulated=True,
    description="Sudden spike in defective goods requiring supplier quarantine"
)


def get_all_scenarios() -> List[DisruptionScenario]:
    """
    Returns a list of all five predefined disruption scenarios.

    Returns:
        List[DisruptionScenario]: A list of all scenario configuration objects.
    """
    return [
        PORT_STRIKE,
        FACTORY_SHUTDOWN,
        CURRENCY_SHOCK,
        LOGISTICS_DELAY,
        QUALITY_FAILURE
    ]


def get_scenario_by_id(scenario_id: str) -> DisruptionScenario:
    """
    Returns a single scenario configuration matching the given ID.

    Args:
        scenario_id (str): Unique identifier of the desired scenario.

    Returns:
        DisruptionScenario: The matching scenario configuration object.

    Raises:
        ValueError: If no scenario matches the provided scenario_id.
    """
    for scenario in get_all_scenarios():
        if scenario.scenario_id == scenario_id:
            return scenario
    raise ValueError(f"Scenario ID '{scenario_id}' not found.")


def scenarios_to_dataframe() -> pd.DataFrame:
    """
    Summarizes all predefined disruption scenarios in a pandas DataFrame.

    Returns:
        pd.DataFrame: DataFrame containing scenario metadata and parameters.
    """
    data = [asdict(s) for s in get_all_scenarios()]
    return pd.DataFrame(data)
