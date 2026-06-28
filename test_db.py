from src.db import read_query
df = read_query("SELECT * FROM mitigation_playbook WHERE supplier_id = 27")
print(df.to_dict('records'))
