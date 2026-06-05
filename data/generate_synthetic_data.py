"""generate_synthetic_data.py — Generates realistic synthetic supply chain data calibrated from the DataCo dataset."""

import os
import datetime
import numpy as np
import pandas as pd
from faker import Faker
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Set random seed for full reproducibility
np.random.seed(42)
fake = Faker()
fake.seed_instance(42)

# Load environment variables
load_dotenv()

# Database Connection Parameters
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "shockproof")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

NUM_SUPPLIERS = 100
NUM_PRODUCTS = 500

# ============================================================================
# Calibrated Parameters from DataCo Analysis
# ============================================================================
DELAY_MEAN = 0.565807
DELAY_STD = 1.490962

LATE_DELIVERY_RATES = {
    'Camping & Hiking': 0.5453,
    'Cardio Equipment': 0.5450,
    'Cleats': 0.5497,
    'Fishing': 0.5493,
    'Indoor/Outdoor Games': 0.5475,
    "Men's Footwear": 0.5449,
    'Water Sports': 0.5481,
    "Women's Apparel": 0.5456
}

MONTHLY_DEMAND_MULTIPLIERS = [
    0.8928, 1.0333, 1.1234, 1.0785, 1.1059, 1.0376, 
    1.1060, 1.1011, 1.0615, 0.8366, 0.8008, 0.8225
]

COUNTRY_SHARES = {
    'Estados Unidos': 0.1417,
    'México': 0.0750,
    'Francia': 0.0721,
    'Alemania': 0.0516,
    'Brasil': 0.0453,
    'Australia': 0.0437,
    'Reino Unido': 0.0396,
    'China': 0.0298,
    'Italia': 0.0266,
    'India': 0.0248
}

CATEGORY_DEMAND_LAMBDAS = {
    'Camping & Hiking': 404,
    'Cardio Equipment': 1106,
    'Cleats': 2169,
    'Fishing': 510,
    'Indoor/Outdoor Games': 1700,
    "Men's Footwear": 654,
    'Water Sports': 457,
    "Women's Apparel": 1852
}

# ============================================================================
# 1. Generate Suppliers Table
# ============================================================================
print("Generating suppliers table...")
suppliers = []

# 1.1. Designated critical supplier for Cleats (Fasteners)
suppliers.append({
    'supplier_id': 1,
    'supplier_name': f"{fake.company()} (Critical)",
    'country': 'Estados Unidos',
    'tier': 1,
    'reliability_score': None,
    'avg_delay_days': None,
    'delay_volatility': None,
    'rejection_rate': None
})

# 1.2. Exactly 3 co-located suppliers in coastal China province (Guangdong)
for i in range(2, 5):
    suppliers.append({
        'supplier_id': i,
        'supplier_name': f"{fake.company()} (geo_cluster)",
        'country': 'China',
        'tier': 2,
        'reliability_score': None,
        'avg_delay_days': None,
        'delay_volatility': None,
        'rejection_rate': None
    })

# 1.3. Remaining suppliers distributed by country weights and tiers
remaining_count = NUM_SUPPLIERS - 4
t1_count = int(np.round(remaining_count * (14 / 46)))
t2_count = remaining_count - t1_count
remaining_tiers = [1] * t1_count + [2] * t2_count
np.random.shuffle(remaining_tiers)

countries_pool = list(COUNTRY_SHARES.keys())
countries_weights = list(COUNTRY_SHARES.values())
countries_weights = np.array(countries_weights) / sum(countries_weights) # Normalize

for i in range(5, NUM_SUPPLIERS + 1):
    country = np.random.choice(countries_pool, p=countries_weights)
    suppliers.append({
        'supplier_id': i,
        'supplier_name': fake.company(),
        'country': country,
        'tier': remaining_tiers[i - 5],
        'reliability_score': None,
        'avg_delay_days': None,
        'delay_volatility': None,
        'rejection_rate': None
    })

df_suppliers = pd.DataFrame(suppliers)

# ============================================================================
# 2. Generate Products Table
# ============================================================================
print("Generating products table...")
products = []

# Scale counts to NUM_PRODUCTS dynamically
base_counts = {
    'Cleats': 20,              # Fastener category (Critical)
    'Cardio Equipment': 15,    # Geo-cluster category (Coastal China dependent)
    'Camping & Hiking': 27,
    'Fishing': 28,
    'Indoor/Outdoor Games': 27,
    "Men's Footwear": 28,
    'Water Sports': 27,
    "Women's Apparel": 28
}
scale = NUM_PRODUCTS / 200.0
cat_counts = {k: int(np.round(v * scale)) for k, v in base_counts.items()}
diff = NUM_PRODUCTS - sum(cat_counts.values())
if diff != 0:
    largest_cat = max(cat_counts, key=cat_counts.get)
    cat_counts[largest_cat] += diff

product_id_counter = 1
for cat, count in cat_counts.items():
    # Sample unit costs from log-normal distribution
    costs = np.random.lognormal(mean=4.4617, sigma=0.8595, size=count)
    costs = np.maximum(costs, 1.0) # Ensure minimal unit cost of 1.0
    
    # Sample monthly demands from Poisson distribution
    demands = np.random.poisson(lam=CATEGORY_DEMAND_LAMBDAS[cat], size=count)
    demands = np.maximum(demands, 30) # Ensure minimal monthly demand of 30
    
    for idx in range(count):
        safety_stock = 45 if cat == 'Cleats' else 30
        
        products.append({
            'product_id': product_id_counter,
            'sku': f"SKU-{product_id_counter:03d}",
            'product_name': f"{fake.word().capitalize()} {cat.split()[0]}",
            'category': cat,
            'unit_cost': float(np.round(costs[idx], 2)),
            'monthly_demand': int(demands[idx]),
            'safety_stock_days': safety_stock
        })
        product_id_counter += 1

df_products = pd.DataFrame(products)

# ============================================================================
# 3. Generate Supply Relationships Table
# ============================================================================
print("Generating supply relationships table...")
relationships = []

distant_t2_suppliers = df_suppliers[
    (df_suppliers['tier'] == 2) & (df_suppliers['country'] != 'Estados Unidos')
]['supplier_id'].tolist()

co_located_ids = [2, 3, 4]
all_supplier_ids = df_suppliers['supplier_id'].tolist()
other_supplier_ids = [sid for sid in all_supplier_ids if sid not in co_located_ids]

for _, prod in df_products.iterrows():
    p_id = prod['product_id']
    cat = prod['category']
    
    if cat == 'Cleats':
        # Fastener category: Critical supplier (1) gets 71%
        # 2 other geographically distant Tier-2 suppliers split the remaining 29%
        selected_distant = np.random.choice(distant_t2_suppliers, size=2, replace=False)
        
        relationships.append({
            'supplier_id': 1,
            'product_id': p_id,
            'supply_share': 0.7100,
            'is_sole_source': True
        })
        relationships.append({
            'supplier_id': int(selected_distant[0]),
            'product_id': p_id,
            'supply_share': 0.1500,
            'is_sole_source': False
        })
        relationships.append({
            'supplier_id': int(selected_distant[1]),
            'product_id': p_id,
            'supply_share': 0.1400,
            'is_sole_source': False
        })
        
    elif cat == 'Cardio Equipment':
        # Geo-cluster category: co-located suppliers (2, 3, 4) get combined 70% share
        # Remaining 30% goes to 1 other random supplier
        shares_3 = np.random.dirichlet([1.0, 1.0, 1.0]) * 0.70
        other_supplier = np.random.choice(other_supplier_ids)
        
        relationships.append({
            'supplier_id': 2,
            'product_id': p_id,
            'supply_share': float(np.round(shares_3[0], 4)),
            'is_sole_source': False
        })
        relationships.append({
            'supplier_id': 3,
            'product_id': p_id,
            'supply_share': float(np.round(shares_3[1], 4)),
            'is_sole_source': False
        })
        relationships.append({
            'supplier_id': 4,
            'product_id': p_id,
            'supply_share': float(np.round(shares_3[2], 4)),
            'is_sole_source': False
        })
        relationships.append({
            'supplier_id': int(other_supplier),
            'product_id': p_id,
            'supply_share': 0.3000,
            'is_sole_source': False
        })
        
        # Adjust combined share to sum to exactly 1.0 due to rounding
        prod_rels = [r for r in relationships if r['product_id'] == p_id]
        total_share = sum(r['supply_share'] for r in prod_rels)
        diff = 1.0 - total_share
        prod_rels[0]['supply_share'] = float(np.round(prod_rels[0]['supply_share'] + diff, 4))
        
        # Update is_sole_source flag based on final adjusted shares
        for r in prod_rels:
            if r['supply_share'] > 0.60:
                r['is_sole_source'] = True
                
    else:
        # All other products: 2-4 random suppliers with Dirichlet-distributed shares
        k = np.random.choice([2, 3, 4])
        selected_sups = np.random.choice(all_supplier_ids, size=k, replace=False)
        shares = np.random.dirichlet([1.5] * k)
        shares = np.round(shares, 4)
        
        # Adjust to sum exactly to 1.0
        diff = 1.0 - sum(shares)
        shares[0] += diff
        
        for idx, sup_id in enumerate(selected_sups):
            share = float(shares[idx])
            relationships.append({
                'supplier_id': int(sup_id),
                'product_id': p_id,
                'supply_share': share,
                'is_sole_source': True if share > 0.60 else False
            })

df_relationships = pd.DataFrame(relationships)

# ============================================================================
# 4. Generate Transactions Table
# ============================================================================
print("Generating transactions table...")
transactions = []
start_date = datetime.date.today() - datetime.timedelta(days=730)

supplier_tiers = df_suppliers.set_index('supplier_id')['tier'].to_dict()
product_details = df_products.set_index('product_id')[['monthly_demand', 'category', 'unit_cost']].to_dict('index')

for day_idx in range(730):
    curr_date = start_date + datetime.timedelta(days=day_idx)
    month = curr_date.month
    multiplier = MONTHLY_DEMAND_MULTIPLIERS[month - 1]
    
    for idx, rel in df_relationships.iterrows():
        sup_id = rel['supplier_id']
        p_id = rel['product_id']
        share = rel['supply_share']
        
        p_info = product_details[p_id]
        monthly_demand = p_info['monthly_demand']
        cat = p_info['category']
        unit_cost = p_info['unit_cost']
        
        # Daily expected quantity for this relationship
        base_qty = (monthly_demand / 30.0) * share * multiplier
        qty_ordered = np.random.poisson(lam=base_qty)
        
        if qty_ordered <= 0:
            continue
            
        # Sample lead time
        lead_time = np.random.choice([2, 3, 4])
        promised_date = curr_date + datetime.timedelta(days=int(lead_time))
        
        # Delay calculation scaled by supplier tier reliability factor
        tier = supplier_tiers[sup_id]
        rel_factor = 0.8 if tier == 1 else 1.0
        
        sampled_delay = np.random.normal(loc=DELAY_MEAN * rel_factor, scale=DELAY_STD)
        delay_days = int(np.round(sampled_delay))
        
        actual_date = promised_date + datetime.timedelta(days=delay_days)
        
        # Rejection logic using late delivery rate as proxy
        late_rate = LATE_DELIVERY_RATES.get(cat, 0.55)
        rejection_prob = late_rate * 0.05
        
        qty_rejected = np.random.binomial(n=qty_ordered, p=rejection_prob)
        qty_delivered = qty_ordered - qty_rejected
        
        transactions.append({
            'supplier_id': int(sup_id),
            'product_id': int(p_id),
            'order_date': curr_date,
            'promised_delivery_date': promised_date,
            'actual_delivery_date': actual_date,
            'quantity_ordered': int(qty_ordered),
            'quantity_delivered': int(qty_delivered),
            'quantity_rejected': int(qty_rejected),
            'unit_cost_at_order': float(unit_cost)
        })

df_transactions = pd.DataFrame(transactions)

# ============================================================================
# 5. Database and CSV Backups
# ============================================================================
print("Applying schema to database and writing synthetic data...")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    print("Dropping existing tables if any...")
    conn.execute(text("DROP TABLE IF EXISTS transactions CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS supply_relationships CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS products CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS suppliers CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS simulation_results CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS resilience_scores CASCADE;"))
    conn.execute(text("DROP TABLE IF EXISTS mitigation_playbook CASCADE;"))
    conn.commit()

# Apply schema from data/schema.sql
print("Executing data/schema.sql...")
with open("data/schema.sql", "r") as f:
    schema_sql = f.read()

with engine.connect() as conn:
    conn.execute(text(schema_sql))
    conn.commit()

# Write DataFrames to PostgreSQL
print("Writing data to database...")
df_suppliers.to_sql('suppliers', con=engine, if_exists='append', index=False)
df_products.to_sql('products', con=engine, if_exists='append', index=False)
df_relationships.to_sql('supply_relationships', con=engine, if_exists='append', index=False)
df_transactions.to_sql('transactions', con=engine, if_exists='append', index=False)

# Sync sequence counters in PostgreSQL
print("Syncing PostgreSQL serial sequences...")
with engine.connect() as conn:
    conn.execute(text("SELECT setval('suppliers_supplier_id_seq', COALESCE((SELECT MAX(supplier_id) FROM suppliers), 1));"))
    conn.execute(text("SELECT setval('products_product_id_seq', COALESCE((SELECT MAX(product_id) FROM products), 1));"))
    conn.execute(text("SELECT setval('supply_relationships_relationship_id_seq', COALESCE((SELECT MAX(relationship_id) FROM supply_relationships), 1));"))
    conn.execute(text("SELECT setval('transactions_transaction_id_seq', COALESCE((SELECT MAX(transaction_id) FROM transactions), 1));"))
    conn.commit()

# Save CSV backups
print("Saving CSV backups to data/raw/synthetic/...")
os.makedirs("data/raw/synthetic", exist_ok=True)
df_suppliers.to_csv("data/raw/synthetic/suppliers.csv", index=False)
df_products.to_csv("data/raw/synthetic/products.csv", index=False)
df_relationships.to_csv("data/raw/synthetic/supply_relationships.csv", index=False)
df_transactions.to_csv("data/raw/synthetic/transactions.csv", index=False)
print("Data generation and storage completed successfully!")

# ============================================================================
# 6. Data Quality Report
# ============================================================================
print("\n==================================================================")
print("                      DATA QUALITY REPORT                         ")
print("==================================================================")

# 6.1. Row Counts
print(f"Row Counts:")
print(f"  - suppliers:            {len(df_suppliers)}")
print(f"  - products:             {len(df_products)}")
print(f"  - supply_relationships: {len(df_relationships)}")
print(f"  - transactions:         {len(df_transactions)}")

# 6.2. Supply share sum verification per product (sum == 1.0 +- 0.001)
share_sums = df_relationships.groupby('product_id')['supply_share'].sum()
all_valid = all((share_sums >= 0.999) & (share_sums <= 1.001))
print(f"\nSupply Share Sum Verification:")
print(f"  - All product supply share sums equal 1.0 ± 0.001: {all_valid}")
print(f"  - Min share sum: {share_sums.min():.4f}")
print(f"  - Max share sum: {share_sums.max():.4f}")

# 6.3. Null counts for all non-nullable columns
print(f"\nNull Counts for Non-Nullable Columns:")
print(f"  - suppliers:")
print(f"      supplier_name: {df_suppliers['supplier_name'].isnull().sum()}")
print(f"      country:       {df_suppliers['country'].isnull().sum()}")
print(f"  - products:")
print(f"      sku:            {df_products['sku'].isnull().sum()}")
print(f"      product_name:   {df_products['product_name'].isnull().sum()}")
print(f"      category:       {df_products['category'].isnull().sum()}")
print(f"      unit_cost:      {df_products['unit_cost'].isnull().sum()}")
print(f"      monthly_demand: {df_products['monthly_demand'].isnull().sum()}")
print(f"  - supply_relationships:")
print(f"      supplier_id:  {df_relationships['supplier_id'].isnull().sum()}")
print(f"      product_id:   {df_relationships['product_id'].isnull().sum()}")
print(f"      supply_share: {df_relationships['supply_share'].isnull().sum()}")
print(f"  - transactions:")
print(f"      supplier_id:            {df_transactions['supplier_id'].isnull().sum()}")
print(f"      product_id:             {df_transactions['product_id'].isnull().sum()}")
print(f"      order_date:             {df_transactions['order_date'].isnull().sum()}")
print(f"      promised_delivery_date: {df_transactions['promised_delivery_date'].isnull().sum()}")
print(f"      quantity_ordered:       {df_transactions['quantity_ordered'].isnull().sum()}")

# 6.4. Top 5 most fragile products by maximum single-supplier share
max_shares = df_relationships.groupby('product_id')['supply_share'].max().reset_index()
df_fragile = max_shares.merge(df_products, on='product_id')
df_fragile = df_fragile.sort_values(by='supply_share', ascending=False).head(5)

print(f"\nTop 5 Most Fragile Products (by Max Single-Supplier Share):")
for idx, row in df_fragile.iterrows():
    print(f"  - {row['sku']} ({row['product_name']}): Category = {row['category']}, Max Share = {row['supply_share']:.2f}")
print("==================================================================")
