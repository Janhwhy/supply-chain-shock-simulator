"""scoring.py — Calculates resilience and risk scores for supply chain entities."""

import numpy as np
import pandas as pd


def compute_dependency_risk(df_relationships):
    """
    Computes dependency risk for each supplier based on their maximum supply share.
    Suppliers holding a share > 50% on any product receive the maximum risk loading.

    Args:
        df_relationships (pd.DataFrame): Sourcing relationships containing:
            - supplier_id (int)
            - product_id (int)
            - supply_share (float)

    Returns:
        pd.Series: Series indexed by supplier_id containing normalized dependency risk scores (0 to 1).
    """
    if df_relationships.empty:
        return pd.Series(dtype=float)
        
    # Group by supplier_id and get the maximum supply share
    max_shares = df_relationships.groupby('supplier_id')['supply_share'].max()
    
    # Clip values: any share > 0.50 gets mapped to the maximum of 0.50
    clipped = max_shares.clip(upper=0.50)
    
    # Min-max scale
    s_min = clipped.min()
    s_max = clipped.max()
    if s_max == s_min:
        return pd.Series(0.0, index=max_shares.index)
        
    return (clipped - s_min) / (s_max - s_min)


def compute_geographic_risk(df_suppliers):
    """
    Computes geographic concentration risk for each supplier based on co-location.
    Suppliers in countries with 3+ co-located peers receive a 0.15 penalty before normalisation.

    Args:
        df_suppliers (pd.DataFrame): Supplier registry containing:
            - supplier_id (int)
            - country (str)

    Returns:
        pd.Series: Series indexed by supplier_id containing normalized geographic risk scores (0 to 1).
    """
    if df_suppliers.empty:
        return pd.Series(dtype=float)
        
    country_counts = df_suppliers['country'].value_counts()
    n_total = len(df_suppliers)
    
    raw_risks = {}
    for _, row in df_suppliers.iterrows():
        s_id = row['supplier_id']
        country = row['country']
        count = country_counts.get(country, 0)
        
        # Fraction of all other suppliers sharing the country
        frac = (count - 1) / (n_total - 1) if n_total > 1 else 0.0
        
        # If country has 3+ co-located peers, apply 0.15 penalty
        if count >= 3:
            frac += 0.15
            
        frac = min(frac, 1.0)
        raw_risks[s_id] = frac
        
    raw_series = pd.Series(raw_risks)
    s_min = raw_series.min()
    s_max = raw_series.max()
    if s_max == s_min:
        return pd.Series(0.0, index=raw_series.index)
        
    return (raw_series - s_min) / (s_max - s_min)


def compute_reliability_risk(df_suppliers_enriched):
    """
    Computes reliability risk based on average delay days and delay volatility.

    Args:
        df_suppliers_enriched (pd.DataFrame): Enriched supplier data containing:
            - supplier_id (int)
            - avg_delay_days (float)
            - delay_volatility (float)

    Returns:
        pd.Series: Series indexed by supplier_id containing operational reliability risk scores (0 to 1).
    """
    if df_suppliers_enriched.empty:
        return pd.Series(dtype=float)
        
    df = df_suppliers_enriched.copy()
    df['avg_delay_days'] = df['avg_delay_days'].fillna(0.0)
    df['delay_volatility'] = df['delay_volatility'].fillna(0.0)
    
    def min_max_scale(series):
        s_min = series.min()
        s_max = series.max()
        if s_max == s_min:
            return pd.Series(0.0, index=series.index)
        return (series - s_min) / (s_max - s_min)
        
    norm_delay = min_max_scale(df['avg_delay_days'])
    norm_vol = min_max_scale(df['delay_volatility'])
    
    reliability_risk = 0.5 * norm_delay + 0.5 * norm_vol
    
    return pd.Series(reliability_risk.values, index=df['supplier_id'])


def compute_substitutability_risk(df_relationships):
    """
    Computes substitutability risk based on average alternatives.
    Sole source suppliers receive the maximum risk loading of 1.0.

    Args:
        df_relationships (pd.DataFrame): Sourcing relationships containing:
            - supplier_id (int)
            - product_id (int)
            - is_sole_source (bool)

    Returns:
        pd.Series: Series indexed by supplier_id containing normalized substitutability risk scores (0 to 1).
    """
    if df_relationships.empty:
        return pd.Series(dtype=float)
        
    # Get number of suppliers per product
    product_supplier_counts = df_relationships.groupby('product_id')['supplier_id'].nunique().to_dict()
    
    # Calculate number of alternative suppliers for each relationship
    df = df_relationships.copy()
    df['alt_count'] = df['product_id'].map(product_supplier_counts) - 1
    
    # For each supplier, compute the average number of alternative suppliers
    avg_alts = df.groupby('supplier_id')['alt_count'].mean()
    
    # Invert: fewer alternatives means higher risk
    inv_alts = avg_alts.apply(lambda x: 1.0 / x if x > 0 else 999.0)
    
    # Identify sole-source suppliers (any relation where is_sole_source == True)
    sole_source_suppliers = set(df[df['is_sole_source'] == True]['supplier_id'])
    
    # Normalise only the non-sole-source suppliers using min-max scaling
    non_ss_inv_alts = inv_alts[~inv_alts.index.isin(sole_source_suppliers)]
    
    min_val = non_ss_inv_alts.min()
    max_val = non_ss_inv_alts.max()
    
    risk_series = pd.Series(0.0, index=avg_alts.index)
    for s_id in avg_alts.index:
        if s_id in sole_source_suppliers:
            risk_series[s_id] = 1.0
        else:
            val = inv_alts[s_id]
            if pd.isna(min_val) or pd.isna(max_val) or max_val == min_val:
                risk_series[s_id] = 0.0
            else:
                risk_series[s_id] = (val - min_val) / (max_val - min_val)
                
    return risk_series


def compute_resilience_scores(df_suppliers, df_suppliers_enriched, df_relationships, df_simulation_results, weights=None):
    """
    Computes composite resilience scores and assigns risk bands for all suppliers.

    Args:
        df_suppliers (pd.DataFrame): Supplier registry.
        df_suppliers_enriched (pd.DataFrame): Enriched supplier registry.
        df_relationships (pd.DataFrame): Sourcing relationships.
        df_simulation_results (pd.DataFrame): Simulation results.
        weights (dict, optional): Weights dict overriding defaults. Must sum to 1.0.

    Returns:
        pd.DataFrame: DataFrame containing risk factors, composite risk, resilience score, and risk band.
    """
    default_weights = {
        'dependency': 0.40,
        'geographic': 0.25,
        'reliability': 0.20,
        'substitutability': 0.15
    }
    
    if weights is not None:
        required_keys = {'dependency', 'geographic', 'reliability', 'substitutability'}
        if not required_keys.issubset(weights.keys()):
            raise ValueError(f"weights dict must contain keys: {required_keys}")
            
        w_sum = sum(weights[k] for k in required_keys)
        if abs(w_sum - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1.0 (got {w_sum})")
        actual_weights = {k: weights[k] for k in required_keys}
    else:
        actual_weights = default_weights
        
    dependency_risk = compute_dependency_risk(df_relationships)
    geographic_risk = compute_geographic_risk(df_suppliers)
    reliability_risk = compute_reliability_risk(df_suppliers_enriched)
    substitutability_risk = compute_substitutability_risk(df_relationships)
    
    df_scores = pd.DataFrame({
        'dependency_risk': dependency_risk,
        'geographic_risk': geographic_risk,
        'reliability_risk': reliability_risk,
        'substitutability_risk': substitutability_risk
    })
    df_scores.index.name = 'supplier_id'
    df_scores = df_scores.reset_index()
    
    df_result = pd.merge(
        df_suppliers[['supplier_id', 'supplier_name', 'country', 'tier']],
        df_scores,
        on='supplier_id',
        how='left'
    )
    
    for col in ['dependency_risk', 'geographic_risk', 'reliability_risk', 'substitutability_risk']:
        df_result[col] = df_result[col].fillna(0.0)
        
    df_result['composite_risk'] = (
        actual_weights['dependency'] * df_result['dependency_risk'] +
        actual_weights['geographic'] * df_result['geographic_risk'] +
        actual_weights['reliability'] * df_result['reliability_risk'] +
        actual_weights['substitutability'] * df_result['substitutability_risk']
    )
    df_result['resilience_score'] = 1.0 - df_result['composite_risk']
    
    if df_result.empty:
        df_result['risk_band'] = pd.Series(dtype=str)
        return df_result
        
    q25 = df_result['resilience_score'].quantile(0.25)
    q50 = df_result['resilience_score'].quantile(0.50)
    q75 = df_result['resilience_score'].quantile(0.75)
    
    def get_risk_band(score):
        if score <= q25:
            return 'Critical'
        elif score <= q50:
            return 'High'
        elif score <= q75:
            return 'Medium'
        else:
            return 'Low'
            
    df_result['risk_band'] = df_result['resilience_score'].apply(get_risk_band)
    
    return df_result


def get_score_interpretation(resilience_score):
    """
    Returns score interpretation details including risk band, recommended action, and urgency level.

    Args:
        resilience_score (float): Resilience score (0 to 1).

    Returns:
        dict: Dict containing risk_band, recommended_action, urgency_level, and interpretation.
    """
    if resilience_score < 0.30:
        band = 'Critical'
        action = 'Immediate supplier diversification, dual-sourcing, or buffer stock increase required.'
        urgency = 'Immediate'
        desc = 'The supplier has severe risk exposure with high dependency, low alternatives, or poor operational reliability.'
    elif resilience_score <= 0.50:
        band = 'High'
        action = 'Develop mitigation playbook, establish secondary supplier contacts, and monitor performance closely.'
        urgency = 'High'
        desc = 'The supplier has significant risk factors that require proactive monitoring and structured mitigation planning.'
    elif resilience_score <= 0.70:
        band = 'Medium'
        action = 'Routine monitoring and check-ins. Maintain standard safety stock.'
        urgency = 'Medium'
        desc = 'The supplier exhibits moderate risk levels, showing stable operations but subject to standard supply chain shocks.'
    else:
        band = 'Low'
        action = 'No immediate action needed. Maintain existing relationship and standard operations.'
        urgency = 'Low'
        desc = 'The supplier is highly resilient with strong operational performance and ample alternative sources available.'
        
    return {
        'risk_band': band,
        'recommended_action': action,
        'urgency_level': urgency,
        'interpretation': desc
    }


def sensitivity_analysis(df_suppliers, df_suppliers_enriched, df_relationships, df_simulation_results):
    """
    Runs resilience scoring across five weight configurations to analyze risk band sensitivity.

    Args:
        df_suppliers (pd.DataFrame): Supplier registry.
        df_suppliers_enriched (pd.DataFrame): Enriched supplier registry.
        df_relationships (pd.DataFrame): Sourcing relationships.
        df_simulation_results (pd.DataFrame): Simulation results.

    Returns:
        pd.DataFrame: DataFrame showing the risk band for each supplier under 5 different configurations.
    """
    configs = {
        'default': {
            'dependency': 0.40,
            'geographic': 0.25,
            'reliability': 0.20,
            'substitutability': 0.15
        },
        'dependency_heavy': {
            'dependency': 0.70,
            'geographic': 0.10,
            'reliability': 0.10,
            'substitutability': 0.10
        },
        'geographic_heavy': {
            'dependency': 0.10,
            'geographic': 0.70,
            'reliability': 0.10,
            'substitutability': 0.10
        },
        'reliability_heavy': {
            'dependency': 0.10,
            'geographic': 0.10,
            'reliability': 0.70,
            'substitutability': 0.10
        },
        'substitutability_heavy': {
            'dependency': 0.10,
            'geographic': 0.10,
            'reliability': 0.10,
            'substitutability': 0.70
        }
    }
    
    result = df_suppliers[['supplier_id', 'supplier_name']].copy()
    
    for config_name, weights in configs.items():
        df_scored = compute_resilience_scores(
            df_suppliers,
            df_suppliers_enriched,
            df_relationships,
            df_simulation_results,
            weights=weights
        )
        result[config_name] = df_scored['risk_band']
        
    return result


def compute_priority_matrix(df_scores, df_simulation_results):
    """
    Computes priority matrix based on resilience score (probability) and simulated exposure (impact).
    
    Args:
        df_scores (pd.DataFrame): Output from compute_resilience_scores.
        df_simulation_results (pd.DataFrame): Simulation results table containing p95_impact.
        
    Returns:
        pd.DataFrame: DataFrame containing supplier priority classification.
    """
    if df_scores.empty or df_simulation_results.empty:
        return pd.DataFrame(columns=[
            'supplier_id', 'supplier_name', 'resilience_score', 'total_p95_exposure',
            'probability_tier', 'impact_tier', 'priority_quadrant'
        ])
        
    # 1. Compute total P95 exposure per supplier
    df_exposure = df_simulation_results.groupby('supplier_id')['p95_impact'].sum().reset_index()
    df_exposure.rename(columns={'p95_impact': 'total_p95_exposure'}, inplace=True)
    
    # 2. Merge with scores
    df_priority = pd.merge(
        df_scores[['supplier_id', 'supplier_name', 'resilience_score']],
        df_exposure,
        on='supplier_id',
        how='inner'
    )
    
    # 3. Assign probability_tier (lower resilience = higher probability of disruption)
    qp25 = df_priority['resilience_score'].quantile(0.25)
    qp50 = df_priority['resilience_score'].quantile(0.50)
    qp75 = df_priority['resilience_score'].quantile(0.75)
    
    def get_prob_tier(score):
        if score <= qp25:
            return 'High Probability'
        elif score <= qp50:
            return 'Medium-High'
        elif score <= qp75:
            return 'Medium-Low'
        else:
            return 'Low Probability'
            
    df_priority['probability_tier'] = df_priority['resilience_score'].apply(get_prob_tier)
    
    # 4. Assign impact_tier (higher exposure = higher impact)
    qi25 = df_priority['total_p95_exposure'].quantile(0.25)
    qi50 = df_priority['total_p95_exposure'].quantile(0.50)
    qi75 = df_priority['total_p95_exposure'].quantile(0.75)
    
    def get_imp_tier(exp):
        if exp > qi75:
            return 'High Impact'
        elif exp > qi50:
            return 'Medium-High'
        elif exp > qi25:
            return 'Medium-Low'
        else:
            return 'Low Impact'
            
    df_priority['impact_tier'] = df_priority['total_p95_exposure'].apply(get_imp_tier)
    
    # 5. Determine priority_quadrant
    def get_quadrant(row):
        p_tier = row['probability_tier']
        i_tier = row['impact_tier']
        
        if p_tier == 'High Probability' and i_tier == 'High Impact':
            return 'Critical Priority'
        elif p_tier == 'High Probability':
            return 'Monitor Closely'
        elif i_tier == 'High Impact':
            return 'Contingency Plan'
        else:
            return 'Routine Review'
            
    df_priority['priority_quadrant'] = df_priority.apply(get_quadrant, axis=1)
    
    return df_priority
