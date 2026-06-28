"""playbook.py — Recommends response strategies and mitigation playbooks for disruptions."""

import pandas as pd
import numpy as np
from src.db import read_table
from src.scenarios import get_all_scenarios

# ============================================================================
# 1. Mitigation Action Catalogue Templates
# ============================================================================

MITIGATION_ACTIONS = {
    'dual_sourcing': {
        'action_id': 'dual_sourcing',
        'action_name': 'Dual-Sourcing',
        'description': 'Qualify and onboard a backup supplier.',
        'applies_to_factor': 'dependency',
        'base_cost_formula': lambda row: 0.08 * row.get('annual_revenue_exposure', 0.0),
        'risk_reduction_estimate': {
            'dependency_risk': 0.50,
            'substitutability_risk': 0.60
        }
    },
    'safety_stock_increase': {
        'action_id': 'safety_stock_increase',
        'action_name': 'Safety Stock Increase',
        'description': 'Increase safety stock to mitigate dependency risk.',
        'applies_to_factor': 'dependency',
        'base_cost_formula': lambda row: (
            (30 if row.get('risk_band') == 'Critical' else (15 if row.get('risk_band') == 'High' else 0)) / 30.0
        ) * row.get('monthly_revenue', 0.0) * 0.05,
        'risk_reduction_estimate': {
            'dependency_risk': 0.25
        }
    },
    'supplier_development': {
        'action_id': 'supplier_development',
        'action_name': 'Supplier Development Programme',
        'description': 'Conduct training and audits to improve operational reliability.',
        'applies_to_factor': 'reliability',
        'base_cost_formula': lambda row: 200000.0,
        'risk_reduction_estimate': {
            'reliability_risk': 0.40
        }
    },
    'geographic_diversification': {
        'action_id': 'geographic_diversification',
        'action_name': 'Geographic Diversification',
        'description': 'Relocate or qualify suppliers in new regions to reduce geographic concentration.',
        'applies_to_factor': 'geographic',
        'base_cost_formula': lambda row: 0.12 * row.get('annual_revenue_exposure', 0.0),
        'risk_reduction_estimate': {
            'geographic_risk': 0.45,
            'geo_risk': 0.45
        }
    },
    'quarterly_monitoring': {
        'action_id': 'quarterly_monitoring',
        'action_name': 'Quarterly Monitoring',
        'description': 'Implement quarterly performance and risk monitoring.',
        'applies_to_factor': 'reliability',
        'base_cost_formula': lambda row: 15000.0,
        'risk_reduction_estimate': {
            'reliability_risk': 0.15
        }
    }
}


# ============================================================================
# 2. Action Selection Logic
# ============================================================================

def recommend_action(supplier_row, df_factor_breakdown=None):
    """
    Selects the recommended mitigation action and dominant risk factor for a supplier.

    Args:
        supplier_row (dict or pd.Series): Supplier details including priority_quadrant, 
            resilience_score, and optionally raw risk factors.
        df_factor_breakdown (pd.DataFrame, optional): DataFrame containing risk factor scores for all suppliers,
            used as a fallback lookup if factors are not present in supplier_row.

    Returns:
        tuple: (action_id, dominant_factor)
    """
    quadrant = supplier_row.get('priority_quadrant')
    s_id = supplier_row.get('supplier_id')
    
    # Try to extract factors directly from supplier_row
    dep = supplier_row.get('dependency_risk')
    geo = supplier_row.get('geographic_risk')
    if geo is None:
        geo = supplier_row.get('geo_risk')
    rel = supplier_row.get('reliability_risk')
    sub = supplier_row.get('substitutability_risk')
    
    # Fallback to lookup in df_factor_breakdown if factors are missing
    if (dep is None or geo is None or rel is None or sub is None) and df_factor_breakdown is not None and not df_factor_breakdown.empty:
        match = df_factor_breakdown[df_factor_breakdown['supplier_id'] == s_id]
        if not match.empty:
            row_match = match.iloc[0]
            dep = dep if dep is not None else row_match.get('dependency_risk')
            geo = geo if geo is not None else row_match.get('geographic_risk', row_match.get('geo_risk'))
            rel = rel if rel is not None else row_match.get('reliability_risk')
            sub = sub if sub is not None else row_match.get('substitutability_risk')
            
    # Default to 0.0 if still None
    dep = dep or 0.0
    geo = geo or 0.0
    rel = rel or 0.0
    sub = sub or 0.0
    
    if quadrant == 'Critical Priority':
        # Whichever raw factor score is highest between substitutability_risk and geographic_risk determines dominance
        if sub >= geo:
            return 'dual_sourcing', 'substitutability_risk'
        else:
            return 'geographic_diversification', 'geographic_risk'
            
    elif quadrant == 'Monitor Closely':
        # Whichever raw factor score is highest between dependency_risk and reliability_risk determines dominance
        if dep >= rel:
            return 'safety_stock_increase', 'dependency_risk'
        else:
            return 'supplier_development', 'reliability_risk'
            
    elif quadrant == 'Contingency Plan':
        # Recommend Dual-Sourcing (high impact justifies cost despite lower probability)
        # Determine overall dominant factor from all four risk factors
        factors = {
            'dependency_risk': dep,
            'geographic_risk': geo,
            'reliability_risk': rel,
            'substitutability_risk': sub
        }
        max_factor = max(factors, key=factors.get)
        return 'dual_sourcing', max_factor
        
    else:  # 'Routine Review' or any other fallback
        # Recommend Quarterly Monitoring
        return 'quarterly_monitoring', 'reliability_risk'


# ============================================================================
# 3. ROI Calculation
# ============================================================================

def compute_roi(supplier_row, action, scenario_probability):
    """
    Computes expected annual loss, risk reduction, cost, ROI, and payback period for a recommended action.

    Args:
        supplier_row (dict or pd.Series): Supplier details including total_p95_exposure and dominant_risk_factor.
        action (dict): Action template or instantiated action dictionary.
        scenario_probability (float): Annual probability of the worst-case scenario.

    Returns:
        dict: Calculations containing:
            - action_cost (float)
            - expected_annual_loss (float)
            - risk_reduction (float)
            - roi (float)
            - payback_period_years (float)
    """
    total_p95_exposure = supplier_row.get('total_p95_exposure', 0.0)
    expected_annual_loss = total_p95_exposure * scenario_probability
    
    # Calculate cost
    if 'base_cost_formula' in action:
        action_cost = action['base_cost_formula'](supplier_row)
    else:
        action_cost = action.get('action_cost', 0.0)
        
    # Determine risk reduction estimate fraction
    reduction_est = action.get('risk_reduction_estimate', 0.0)
    
    if isinstance(reduction_est, dict):
        # Determine which risk factor is dominant in supplier_row
        dom_factor = supplier_row.get('dominant_risk_factor')
        if dom_factor:
            dom_factor_str = str(dom_factor).lower()
            if dom_factor_str in reduction_est:
                reduction_val = reduction_est[dom_factor_str]
            elif 'dependency' in dom_factor_str:
                reduction_val = reduction_est.get('dependency_risk', 0.50)
            elif 'substitutability' in dom_factor_str:
                reduction_val = reduction_est.get('substitutability_risk', 0.60)
            elif 'geographic' in dom_factor_str or 'geo' in dom_factor_str:
                reduction_val = reduction_est.get('geographic_risk', reduction_est.get('geo_risk', 0.45))
            elif 'reliability' in dom_factor_str:
                reduction_val = reduction_est.get('reliability_risk', 0.40)
            else:
                reduction_val = list(reduction_est.values())[0] if reduction_est else 0.0
        else:
            reduction_val = max(reduction_est.values()) if reduction_est else 0.0
    else:
        reduction_val = float(reduction_est)
        
    risk_reduction = expected_annual_loss * reduction_val
    
    # Compute ROI and Payback Period
    if action_cost > 0.0:
        roi = risk_reduction / action_cost
        if risk_reduction > 0.0:
            payback_period_years = action_cost / risk_reduction
        else:
            payback_period_years = float('inf')
    else:
        roi = 0.0
        payback_period_years = 0.0
        
    return {
        'action_cost': action_cost,
        'expected_annual_loss': expected_annual_loss,
        'risk_reduction': risk_reduction,
        'roi': roi,
        'payback_period_years': payback_period_years
    }


# ============================================================================
# 4. Full Playbook Generation
# ============================================================================

def generate_playbook(df_priority_matrix, df_resilience_scores, df_simulation_results, df_worst_case):
    """
    Generates a ranked mitigation playbook for all suppliers.

    Args:
        df_priority_matrix (pd.DataFrame): Priority matrix containing supplier_id, priority_quadrant, total_p95_exposure.
        df_resilience_scores (pd.DataFrame): Resilience scores containing supplier_id, country, tier, and individual risk factors.
        df_simulation_results (pd.DataFrame): Raw simulation results containing scenario details.
        df_worst_case (pd.DataFrame): Worst-case scenario per supplier containing worst_case_scenario and total_p95_exposure.

    Returns:
        pd.DataFrame: Sorted DataFrame of mitigation recommendations and ROI details.
    """
    # Load supply relationships and products to compute monthly revenue
    monthly_revenues = {}
    try:
        df_rel = read_table('supply_relationships')
        df_prod = read_table('products')
        if df_rel is not None and not df_rel.empty and df_prod is not None and not df_prod.empty:
            df_merged = pd.merge(df_rel, df_prod, on='product_id')
            df_merged['weighted_revenue'] = df_merged['supply_share'] * df_merged['unit_cost'] * df_merged['monthly_demand']
            monthly_revenues = df_merged.groupby('supplier_id')['weighted_revenue'].sum().to_dict()
    except Exception:
        pass
        
    # Map scenarios to their annual probability
    scenario_probs = {s.scenario_id: s.annual_probability for s in get_all_scenarios()}
    for s in get_all_scenarios():
        scenario_probs[s.display_name] = s.annual_probability
        
    playbook_rows = []
    
    for _, row in df_priority_matrix.iterrows():
        s_id = row['supplier_id']
        s_name = row['supplier_name']
        quadrant = row['priority_quadrant']
        total_p95 = row['total_p95_exposure']
        
        # Find resilience info for risk band and factors
        res_row = df_resilience_scores[df_resilience_scores['supplier_id'] == s_id]
        if not res_row.empty:
            composite_score = res_row.iloc[0].get('composite_score', 0.5)
            r_band = res_row.iloc[0].get('risk_band')
            if pd.isna(r_band) or r_band is None:
                if composite_score < 0.15:
                    r_band = 'Critical'
                elif composite_score < 0.40:
                    r_band = 'High'
                elif composite_score < 0.70:
                    r_band = 'Medium'
                else:
                    r_band = 'Low'
            dep_risk = res_row.iloc[0].get('dependency_risk', 0.0)
            geo_risk = res_row.iloc[0].get('geographic_risk', res_row.iloc[0].get('geo_risk', 0.0))
            rel_risk = res_row.iloc[0].get('reliability_risk', 0.0)
            sub_risk = res_row.iloc[0].get('substitutability_risk', 0.0)
        else:
            r_band = 'Medium'
            dep_risk, geo_risk, rel_risk, sub_risk = 0.0, 0.0, 0.0, 0.0
            
        # Find worst-case scenario details and annual probability
        wc_row = df_worst_case[df_worst_case['supplier_id'] == s_id]
        if not wc_row.empty:
            wc_scenario = wc_row.iloc[0]['worst_case_scenario']
            prob = scenario_probs.get(wc_scenario, 0.15)
        else:
            prob = 0.15
            
        # Compute monthly revenue with fallback
        monthly_rev = monthly_revenues.get(s_id)
        if monthly_rev is None:
            if 'monthly_revenue' in row:
                monthly_rev = row['monthly_revenue']
            elif 'monthly_revenue' in res_row.columns:
                monthly_rev = res_row.iloc[0]['monthly_revenue']
            else:
                monthly_rev = total_p95 / 12.0
                
        # Build consolidated supplier dictionary
        supplier_dict = {
            'supplier_id': s_id,
            'supplier_name': s_name,
            'priority_quadrant': quadrant,
            'risk_band': r_band,
            'total_p95_exposure': total_p95,
            'dependency_risk': dep_risk,
            'geographic_risk': geo_risk,
            'geo_risk': geo_risk,
            'reliability_risk': rel_risk,
            'substitutability_risk': sub_risk,
            'monthly_revenue': monthly_rev,
            'annual_revenue_exposure': monthly_rev * 12.0
        }
        
        # Select recommended action
        action_id, dominant_factor = recommend_action(supplier_dict, df_resilience_scores)
        supplier_dict['dominant_risk_factor'] = dominant_factor
        
        # Retrieve action template
        action_template = MITIGATION_ACTIONS.get(action_id, MITIGATION_ACTIONS['quarterly_monitoring'])
        
        # Calculate ROI
        roi_stats = compute_roi(supplier_dict, action_template, prob)
        
        # Build playbook entry
        playbook_rows.append({
            'supplier_id': s_id,
            'supplier_name': s_name,
            'priority_quadrant': quadrant,
            'dominant_risk_factor': dominant_factor,
            'recommended_action': action_template['action_name'],
            'action_description': action_template['description'],
            'action_cost': roi_stats['action_cost'],
            'expected_annual_loss': roi_stats['expected_annual_loss'],
            'risk_reduction': roi_stats['risk_reduction'],
            'roi': roi_stats['roi'],
            'payback_period_years': roi_stats['payback_period_years']
        })
        
    df_playbook = pd.DataFrame(playbook_rows)
    
    if not df_playbook.empty:
        df_playbook.sort_values(by='roi', ascending=False, inplace=True)
        
    return df_playbook.reset_index(drop=True)


# ============================================================================
# 5. Portfolio Summary
# ============================================================================

def playbook_summary(df_playbook):
    """
    Computes portfolio-level mitigation summary statistics.

    Args:
        df_playbook (pd.DataFrame): Generated playbook DataFrame.

    Returns:
        dict: Portfolio summary metrics containing:
            - total_mitigation_budget (float): Budget for 'Critical Priority' and 'Monitor Closely' only.
            - total_risk_eliminated (float): Risk eliminated for the same.
            - portfolio_roi (float): Ratio of total risk eliminated to budget.
            - action_counts (dict): Count of suppliers per action type.
    """
    if df_playbook.empty:
        return {
            'total_mitigation_budget': 0.0,
            'total_risk_eliminated': 0.0,
            'portfolio_roi': 0.0,
            'action_counts': {}
        }
        
    # Filter for 'Critical Priority' and 'Monitor Closely'
    target_quadrants = ['Critical Priority', 'Monitor Closely']
    df_target = df_playbook[df_playbook['priority_quadrant'].isin(target_quadrants)]
    
    total_budget = float(df_target['action_cost'].sum())
    total_risk_elim = float(df_target['risk_reduction'].sum())
    
    portfolio_roi = total_risk_elim / total_budget if total_budget > 0 else 0.0
    
    # Counts of suppliers per recommended action type (for the whole portfolio)
    action_counts = df_playbook['recommended_action'].value_counts().to_dict()
    
    return {
        'total_mitigation_budget': total_budget,
        'total_risk_eliminated': total_risk_elim,
        'portfolio_roi': portfolio_roi,
        'action_counts': action_counts
    }
