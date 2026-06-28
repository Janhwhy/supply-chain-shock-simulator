import pandas as pd
from src.playbook import generate_playbook
from src.db import read_table
df_priority = read_table("risk_priority_matrix")
df_scores = read_table("resilience_scores")
df_sim = read_table("simulation_results")
# we don't have df_worst_case locally as a table, we can mock it or just pass df_sim
df_worst = pd.DataFrame([{'supplier_id': 27, 'worst_case_scenario': 'port_strike', 'total_p95_exposure': 1000}])
pb = generate_playbook(df_priority, df_scores, df_sim, df_worst)
print(pb[pb['supplier_id'] == 27].to_dict('records'))
