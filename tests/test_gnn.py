"""test_gnn.py — Unit tests for the bipartite GCN (evaluation/gnn_model.py)
and the shared bipartite-matrix helper (src/graph.py::build_bipartite_matrices)."""

import numpy as np
import pandas as pd
import pytest

from src.graph import build_dependency_graph, build_bipartite_matrices
from src.scoring import FACTOR_NAMES
from evaluation.gnn_model import BipartiteGCN, prepare_product_features, train_gnn, predict_gnn


@pytest.fixture
def sample_suppliers():
    return pd.DataFrame([
        {"supplier_id": 1, "supplier_name": "A", "country": "USA", "tier": 1, "reliability_score": 0.9},
        {"supplier_id": 2, "supplier_name": "B", "country": "Germany", "tier": 1, "reliability_score": 0.8},
        {"supplier_id": 3, "supplier_name": "C", "country": "India", "tier": 2, "reliability_score": 0.7},
    ])


@pytest.fixture
def sample_products():
    return pd.DataFrame([
        {"product_id": 10, "sku": "S10", "product_name": "P10", "unit_cost": 5.0, "monthly_demand": 100},
        {"product_id": 20, "sku": "S20", "product_name": "P20", "unit_cost": 10.0, "monthly_demand": 50},
    ])


@pytest.fixture
def sample_relationships():
    return pd.DataFrame([
        {"supplier_id": 1, "product_id": 10, "supply_share": 0.6},
        {"supplier_id": 2, "product_id": 10, "supply_share": 0.4},
        {"supplier_id": 3, "product_id": 20, "supply_share": 1.0},
    ])


@pytest.fixture
def G(sample_relationships, sample_suppliers, sample_products):
    return build_dependency_graph(sample_relationships, sample_suppliers, sample_products)


def test_build_bipartite_matrices_shapes_and_row_sums(G):
    supplier_ids, product_ids, s2p, p2s = build_bipartite_matrices(G)

    assert supplier_ids == [1, 2, 3]
    assert product_ids == [10, 20]
    assert s2p.shape == (3, 2)
    assert p2s.shape == (2, 3)

    # Every supplier supplies something, so every row of s2p sums to 1.
    assert np.allclose(s2p.sum(axis=1), 1.0)
    # Every product has at least one supplier, so every row of p2s sums to 1.
    assert np.allclose(p2s.sum(axis=1), 1.0)


def test_build_bipartite_matrices_empty_graph():
    empty = pd.DataFrame(columns=["supplier_id", "product_id", "supply_share"])
    G_empty = build_dependency_graph(empty, pd.DataFrame(columns=["supplier_id", "supplier_name", "country", "tier", "reliability_score"]), empty)
    supplier_ids, product_ids, s2p, p2s = build_bipartite_matrices(G_empty)

    assert supplier_ids == []
    assert product_ids == []
    assert s2p.shape == (0, 0)
    assert p2s.shape == (0, 0)


def test_bipartite_gcn_forward_shape():
    torch = pytest.importorskip("torch")
    n_s, n_p, hidden = 4, 3, 8
    model = BipartiteGCN(supplier_dim=len(FACTOR_NAMES), product_dim=2, hidden_dim=hidden)

    x_s = torch.rand(n_s, len(FACTOR_NAMES))
    x_p = torch.rand(n_p, 2)
    s2p = torch.rand(n_s, n_p)
    p2s = torch.rand(n_p, n_s)

    out = model(x_s, x_p, s2p, p2s)
    assert out.shape == (n_s,)


def test_train_and_predict_gnn(G, sample_suppliers, sample_products, sample_relationships):
    supplier_ids, product_ids, s2p, p2s = build_bipartite_matrices(G)
    product_features = prepare_product_features(sample_products, product_ids)

    factors = pd.DataFrame(
        np.random.default_rng(0).uniform(0, 1, size=(3, len(FACTOR_NAMES))),
        index=supplier_ids, columns=FACTOR_NAMES,
    )
    ground_truth = pd.Series([100.0, 200.0, 300.0], index=supplier_ids)
    train_records = [{"factors": factors, "ground_truth": ground_truth}]

    model = train_gnn(train_records, supplier_ids, product_ids, s2p, p2s, product_features,
                       hidden_dim=8, n_epochs=10, random_state=0)
    preds = predict_gnn(model, factors, supplier_ids, product_ids, s2p, p2s, product_features)

    assert list(preds.index) == supplier_ids
    assert not preds.isna().any()
