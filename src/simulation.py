"""simulation.py — Runs Monte Carlo simulations of supply chain disruptions."""

import numpy as np
import pandas as pd
from src.db import get_engine, read_table
from src.scenarios import (
    get_all_scenarios,
    get_scenario_by_id,
    PORT_STRIKE,
    FACTORY_SHUTDOWN,
    CURRENCY_SHOCK,
    LOGISTICS_DELAY,
    QUALITY_FAILURE
)


def estimate_beta_params(a, c):
    """
    Estimates shape parameters alpha and beta for a Beta distribution spanning (a, c)
    using the Method of Moments. Assumes a symmetric PERT-style distribution:
      mean = (a + c) / 2
      std = (c - a) / 6

    Args:
        a (float): Minimum value of the distribution support.
        c (float): Maximum value of the distribution support.

    Returns:
        tuple: (alpha, beta) shape parameters.
    """
    mean_val = (a + c) / 2.0
    std_val = (c - a) / 6.0
    
    # Scale to standard [0, 1] interval
    mean_scaled = (mean_val - a) / (c - a) if (c > a) else 0.5
    var_scaled = (std_val ** 2) / ((c - a) ** 2) if (c > a) else 0.027777777777777776 # 1/36
    
    if var_scaled >= mean_scaled * (1.0 - mean_scaled) or var_scaled <= 0.0:
        # Fallback to standard symmetric shape if variance is invalid
        alpha = 4.0
        beta = 4.0
    else:
        temp = (mean_scaled * (1.0 - mean_scaled) / var_scaled) - 1.0
        alpha = mean_scaled * temp
        beta = (1.0 - mean_scaled) * temp
        
    return alpha, beta


def get_supplier_normalization_bounds(df_suppliers=None):
    """
    Computes min/max bounds for delay_volatility and rejection_rate.
    If df_suppliers is not provided, loads it from the database using read_table.

    Args:
        df_suppliers (pd.DataFrame, optional): Pre-loaded DataFrame of suppliers.

    Returns:
        tuple: (min_vol, max_vol, min_rej, max_rej) bounds.
    """
    if df_suppliers is None:
        try:
            df_suppliers = read_table('suppliers')
        except Exception:
            # Fallback if DB is unavailable during unit testing
            return 0.0, 3.0, 0.0, 0.05
            
    min_vol = df_suppliers['delay_volatility'].min()
    max_vol = df_suppliers['delay_volatility'].max()
    min_rej = df_suppliers['rejection_rate'].min()
    max_rej = df_suppliers['rejection_rate'].max()
    
    # Handle NaN or identical values
    if pd.isna(min_vol) or pd.isna(max_vol) or min_vol == max_vol:
        min_vol, max_vol = 0.0, max_vol if not pd.isna(max_vol) and max_vol > 0 else 1.0
    if pd.isna(min_rej) or pd.isna(max_rej) or min_rej == max_rej:
        min_rej, max_rej = 0.0, max_rej if not pd.isna(max_rej) and max_rej > 0 else 1.0
        
    return min_vol, max_vol, min_rej, max_rej


def run_simulation(supplier, scenario, supply_relationships, products, n_runs=10000):
    """
    Runs a fully vectorized Monte Carlo simulation for a single supplier and scenario.

    Args:
        supplier (dict or pd.Series): Supplier record containing volatility, rejection rate, country, etc.
        scenario (DisruptionScenario): Scenario object with parameters.
        supply_relationships (pd.DataFrame): DataFrame of sourcing relationships.
        products (pd.DataFrame): DataFrame of product registry with unit_cost and monthly_demand.
        n_runs (int, optional): Number of Monte Carlo runs. Defaults to 10000.

    Returns:
        dict: Dict containing: supplier_id, scenario_id, n_runs, p50_impact, p95_impact,
              mean_impact, std_impact, zero_impact_fraction, and impact_distribution.
    """
    supplier_id = supplier.get('supplier_id')
    
    # 1. Compute Modulated Probability
    min_vol, max_vol, min_rej, max_rej = get_supplier_normalization_bounds()
    
    raw_vol = supplier.get('delay_volatility', 0.0)
    if pd.isna(raw_vol):
        raw_vol = 0.0
    norm_vol = (raw_vol - min_vol) / (max_vol - min_vol) if (max_vol > min_vol) else 0.0
    
    raw_rej = supplier.get('rejection_rate', 0.0)
    if pd.isna(raw_rej):
        raw_rej = 0.0
    norm_rej = (raw_rej - min_rej) / (max_rej - min_rej) if (max_rej > min_rej) else 0.0
    
    prob = scenario.annual_probability
    
    if getattr(scenario, 'reliability_modulated', False):
        prob = prob * (1.0 + norm_vol)
        
    if getattr(scenario, 'rejection_modulated', False):
        prob = prob * (1.0 + norm_rej)
        
    if getattr(scenario, 'geographic_modifier', False):
        country = supplier.get('country', '')
        if isinstance(country, str) and country.lower().strip() in {
            'china', 'estados unidos', 'méxico', 'mexico', 'brasil', 'brazil'
        }:
            prob = prob * 1.5
            
    prob = max(0.0, min(prob, 1.0))
    
    # 2. Draw Simulation Random Variables
    # Shocks Bernoulli trial
    shocks = np.random.random(n_runs) < prob
    
    # Duration Uniform draw
    durations = np.random.uniform(scenario.duration_min_days, scenario.duration_max_days, size=n_runs)
    
    # Beta distributed supply loss fraction scaled to bounds
    alpha, beta = estimate_beta_params(scenario.supply_loss_min, scenario.supply_loss_max)
    beta_samples = np.random.beta(alpha, beta, size=n_runs)
    loss_fractions = scenario.supply_loss_min + (scenario.supply_loss_max - scenario.supply_loss_min) * beta_samples
    
    # 3. Calculate Total Product Revenue weight for the supplier
    supplier_rels = supply_relationships[supply_relationships['supplier_id'] == supplier_id]
    total_product_revenue_weight = 0.0
    
    if not supplier_rels.empty:
        merged = pd.merge(supplier_rels, products, on='product_id')
        if not merged.empty:
            merged['monthly_revenue'] = merged['unit_cost'] * merged['monthly_demand']
            merged['weighted_revenue'] = merged['supply_share'] * merged['monthly_revenue']
            total_product_revenue_weight = merged['weighted_revenue'].sum()
            
    # 4. Vectorized Revenue at Risk calculation
    revenue_at_risk = loss_fractions * (durations / 30.0) * total_product_revenue_weight
    revenue_at_risk = np.where(shocks, revenue_at_risk, 0.0)
    
    # 5. Extract Metrics
    p50_impact = float(np.percentile(revenue_at_risk, 50))
    p95_impact = float(np.percentile(revenue_at_risk, 95))
    mean_impact = float(np.mean(revenue_at_risk))
    std_impact = float(np.std(revenue_at_risk))
    zero_impact_fraction = float(np.mean(revenue_at_risk == 0.0))
    
    return {
        'supplier_id': int(supplier_id),
        'scenario_id': scenario.scenario_id,
        'n_runs': int(n_runs),
        'p50_impact': p50_impact,
        'p95_impact': p95_impact,
        'mean_impact': mean_impact,
        'std_impact': std_impact,
        'zero_impact_fraction': zero_impact_fraction,
        'impact_distribution': revenue_at_risk
    }


def run_all_simulations(df_suppliers, df_scenarios, df_relationships, df_products, n_runs=10000):
    """
    Runs disruption simulations for all suppliers across all scenarios.

    Args:
        df_suppliers (pd.DataFrame): DataFrame of all suppliers.
        df_scenarios (pd.DataFrame or list): DataFrame or list of disruption scenarios.
        df_relationships (pd.DataFrame): DataFrame of sourcing relationships.
        df_products (pd.DataFrame): DataFrame of product catalog.
        n_runs (int, optional): Number of Monte Carlo runs. Defaults to 10000.

    Returns:
        pd.DataFrame: A consolidated DataFrame containing row-level metrics for all combinations.
    """
    # Parse scenarios to DisruptionScenario objects
    scenarios_to_run = []
    if isinstance(df_scenarios, pd.DataFrame):
        for _, row in df_scenarios.iterrows():
            scenario_id = row.get('scenario_id')
            try:
                scenarios_to_run.append(get_scenario_by_id(scenario_id))
            except ValueError:
                # Dynamically construct DisruptionScenario from row
                from src.scenarios import DisruptionScenario
                scenario_obj = DisruptionScenario(
                    scenario_id=row['scenario_id'],
                    display_name=row.get('display_name', row['scenario_id']),
                    annual_probability=float(row['annual_probability']),
                    duration_min_days=int(row['duration_min_days']),
                    duration_max_days=int(row['duration_max_days']),
                    supply_loss_min=float(row['supply_loss_min']),
                    supply_loss_max=float(row['supply_loss_max']),
                    description=row.get('description', ''),
                    geographic_modifier=bool(row.get('geographic_modifier', False)),
                    reliability_modulated=bool(row.get('reliability_modulated', False)),
                    affects_all_in_country=bool(row.get('affects_all_in_country', False)),
                    rejection_modulated=bool(row.get('rejection_modulated', False))
                )
                scenarios_to_run.append(scenario_obj)
    else:
        scenarios_to_run = list(df_scenarios)
        
    results = []
    
    for idx, (_, supplier) in enumerate(df_suppliers.iterrows()):
        for scenario in scenarios_to_run:
            res = run_simulation(supplier, scenario, df_relationships, df_products, n_runs=n_runs)
            results.append({
                'supplier_id': res['supplier_id'],
                'scenario_id': res['scenario_id'],
                'n_runs': res['n_runs'],
                'p50_impact': res['p50_impact'],
                'p95_impact': res['p95_impact'],
                'mean_impact': res['mean_impact'],
                'std_impact': res['std_impact'],
                'zero_impact_fraction': res['zero_impact_fraction'],
                'impact_distribution': res['impact_distribution']
            })
            
        if (idx + 1) % 10 == 0 or (idx + 1) == len(df_suppliers):
            print(f"Progress: Simulated {idx + 1}/{len(df_suppliers)} suppliers across all scenarios.")
            
    return pd.DataFrame(results)


def analyse_distribution(impact_array, supplier_name, scenario_name):
    """
    Analyzes the full impact distribution array and returns key statistics.

    Args:
        impact_array (np.ndarray): Full array of simulated impact values.
        supplier_name (str): Name of the supplier.
        scenario_name (str): Name of the scenario.

    Returns:
        dict: Summary statistics including mean, median, std, percentiles, skewness,
              kurtosis, and the tail-fatness metric var_ratio.
    """
    mean_val = float(np.mean(impact_array))
    median_val = float(np.median(impact_array))
    std_val = float(np.std(impact_array))
    
    p50_val = float(np.percentile(impact_array, 50))
    p75_val = float(np.percentile(impact_array, 75))
    p90_val = float(np.percentile(impact_array, 90))
    p95_val = float(np.percentile(impact_array, 95))
    p99_val = float(np.percentile(impact_array, 99))
    
    # Calculate skewness and kurtosis
    try:
        from scipy.stats import skew, kurtosis
        skew_val = float(skew(impact_array))
        kurt_val = float(kurtosis(impact_array))
    except Exception:
        # Fallback to manual computation if scipy is not loaded or fails
        n = len(impact_array)
        if n > 2 and std_val > 0.0:
            diff = impact_array - mean_val
            skew_val = float((np.sum(diff**3) / n) / (std_val**3))
            kurt_val = float((np.sum(diff**4) / n) / (std_val**4) - 3.0)
        else:
            skew_val = 0.0
            kurt_val = 0.0
            
    var_ratio = p95_val / mean_val if mean_val > 0.0 else 0.0
    
    return {
        'mean': mean_val,
        'median': median_val,
        'std': std_val,
        'p50': p50_val,
        'p75': p75_val,
        'p90': p90_val,
        'p95': p95_val,
        'p99': p99_val,
        'skewness': skew_val,
        'kurtosis': kurt_val,
        'var_ratio': var_ratio
    }


def identify_worst_case_scenarios(df_simulation_results):
    """
    Groups results by supplier and returns the scenario producing the highest P95 impact,
    along with the total P95 exposure across all scenarios for that supplier.

    Args:
        df_simulation_results (pd.DataFrame): Combined simulation results DataFrame.

    Returns:
        pd.DataFrame: A DataFrame showing worst-case scenario details and total exposure per supplier.
    """
    if df_simulation_results.empty:
        return pd.DataFrame(columns=['supplier_id', 'worst_case_scenario', 'max_p95_impact', 'total_p95_exposure'])
        
    scenario_col = 'scenario_id' if 'scenario_id' in df_simulation_results.columns else 'scenario_name'
    
    # 1. Total exposure across all scenarios for each supplier
    total_exposure = df_simulation_results.groupby('supplier_id')['p95_impact'].sum().reset_index()
    total_exposure.rename(columns={'p95_impact': 'total_p95_exposure'}, inplace=True)
    
    # 2. Worst-case scenario per supplier (highest P95 impact)
    idx = df_simulation_results.groupby('supplier_id')['p95_impact'].idxmax()
    worst_cases = df_simulation_results.loc[idx, ['supplier_id', scenario_col, 'p95_impact']].copy()
    worst_cases.rename(columns={scenario_col: 'worst_case_scenario', 'p95_impact': 'max_p95_impact'}, inplace=True)
    
    # 3. Merge together
    return pd.merge(worst_cases, total_exposure, on='supplier_id')
