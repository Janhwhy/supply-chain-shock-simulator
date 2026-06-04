-- PostgreSQL Database Schema for ShockProof Supply Chain Shock Simulator

-- ============================================================================
-- 1. Core Schema Tables
-- ============================================================================

-- Table: suppliers
CREATE TABLE suppliers (
    supplier_id SERIAL PRIMARY KEY,
    supplier_name VARCHAR(255) NOT NULL,
    country VARCHAR(100) NOT NULL,
    tier INTEGER CHECK (tier IN (1, 2)),
    reliability_score NUMERIC(4,3), -- Populated during ETL
    avg_delay_days NUMERIC(6,2),
    delay_volatility NUMERIC(6,2),
    rejection_rate NUMERIC(5,4),
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE suppliers IS 'Stores upstream supply chain suppliers, their profiles, and computed performance baselines.';

-- Table: products
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    sku VARCHAR(100) UNIQUE NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(150) NOT NULL,
    unit_cost NUMERIC(10,2) NOT NULL,
    monthly_demand INTEGER NOT NULL,
    safety_stock_days INTEGER DEFAULT 30,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE products IS 'Maintains the product catalog, standard costs, and target stock requirements.';

-- Table: supply_relationships
CREATE TABLE supply_relationships (
    relationship_id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    supply_share NUMERIC(5,4) NOT NULL CHECK (supply_share >= 0 AND supply_share <= 1),
    is_sole_source BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_supplier_product UNIQUE (supplier_id, product_id)
);

COMMENT ON TABLE supply_relationships IS 'Defines the bipartite mapping of products to their sourcing suppliers and allocation shares.';

-- Table: transactions
CREATE TABLE transactions (
    transaction_id BIGSERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(supplier_id),
    product_id INTEGER REFERENCES products(product_id),
    order_date DATE NOT NULL,
    promised_delivery_date DATE NOT NULL,
    actual_delivery_date DATE,
    quantity_ordered INTEGER NOT NULL,
    quantity_delivered INTEGER,
    quantity_rejected INTEGER DEFAULT 0,
    unit_cost_at_order NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE transactions IS 'Historical order and delivery ledger used to evaluate supplier reliability and delays.';

-- ============================================================================
-- 2. Core Indexes
-- ============================================================================
CREATE INDEX idx_transactions_supplier_id ON transactions(supplier_id);
CREATE INDEX idx_transactions_product_id ON transactions(product_id);
CREATE INDEX idx_transactions_order_date ON transactions(order_date);
CREATE INDEX idx_supply_relationships_supplier_id ON supply_relationships(supplier_id);
CREATE INDEX idx_supply_relationships_product_id ON supply_relationships(product_id);

-- ============================================================================
-- 3. Results Schema Tables
-- ============================================================================

-- Table: simulation_results
CREATE TABLE simulation_results (
    result_id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    scenario_name VARCHAR(150) NOT NULL,
    p50_impact NUMERIC(15,2) NOT NULL,
    p95_impact NUMERIC(15,2) NOT NULL,
    run_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE simulation_results IS 'Saves aggregated monetary impact profiles for each supplier under different disruption scenarios.';

-- Table: resilience_scores
CREATE TABLE resilience_scores (
    score_id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    dependency_risk NUMERIC(4,3) NOT NULL,
    geo_risk NUMERIC(4,3) NOT NULL,
    reliability_risk NUMERIC(4,3) NOT NULL,
    substitutability_risk NUMERIC(4,3) NOT NULL,
    composite_score NUMERIC(4,3) NOT NULL,
    score_date TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE resilience_scores IS 'Tracks the decomposed risk metrics and final composite resilience scores computed for each supplier.';

-- Table: mitigation_playbook
CREATE TABLE mitigation_playbook (
    playbook_id SERIAL PRIMARY KEY,
    supplier_id INTEGER REFERENCES suppliers(supplier_id) ON DELETE CASCADE,
    scenario VARCHAR(150) NOT NULL,
    recommended_action TEXT NOT NULL,
    estimated_cost NUMERIC(12,2) NOT NULL,
    p95_impact NUMERIC(15,2) NOT NULL,
    roi NUMERIC(6,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE mitigation_playbook IS 'Stores optimal mitigation actions, estimated costs, residual impacts, and return on investment.';
