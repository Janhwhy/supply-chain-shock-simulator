"""gnn_model.py — A small bipartite Graph Convolutional Network (GCN) that
predicts each supplier's P95 exposure directly from the dependency graph,
learning the propagation weights that compute_risk_propagation (see
src/graph.py) has to hand-set.

Motivation
----------
compute_risk_propagation diffuses each supplier's own risk score across the
bipartite supplier<->product graph with a fixed, hand-chosen per-hop damping
factor. That is a reasonable heuristic, but the "right" amount of diffusion
and how much each hop should matter is exactly the kind of thing a model
should learn from data instead of a human picking a number. This module
implements that: the same bipartite message-passing structure
(build_bipartite_matrices, src/graph.py), but with learned linear
transforms at each hop and a learned regression head, trained end-to-end
against the same Monte Carlo P95 exposure ground truth every other model in
this project is trained on.

The propagation rule (per hop: renormalized-adjacency matrix multiply,
followed by a learned linear transform and a nonlinearity) follows
Kipf & Welling, "Semi-Supervised Classification with Graph Convolutional
Networks" (ICLR 2017), adapted to two node types (supplier, product) instead
of one homogeneous graph — implemented directly with plain PyTorch tensor
ops rather than a graph-learning framework (e.g. PyTorch Geometric), since
the graph here is small (~100 suppliers, ~500 products) and a framework
dependency buys nothing at this scale while adding real install fragility.

Training setup: the graph topology (which supplier supplies which product)
is fixed across every seed — only the node *features* (that seed's
bootstrap-derived risk factors) and the regression *target* (that seed's
realized P95 exposure) vary. This is the standard "transductive GNN,
many labeled snapshots of the same graph" setup: every train_records entry
contributes one (features, target) pair sharing the same model weights.
"""

import numpy as np
import pandas as pd
import torch
import torch.nn as nn


class BipartiteGCN(nn.Module):
    """2-hop bipartite GCN: supplier -> product -> supplier message passing,
    mirroring compute_risk_propagation's own hop structure, but with learned
    (not hand-set) weights at every step."""

    def __init__(self, supplier_dim, product_dim, hidden_dim=16):
        super().__init__()
        self.proj_s = nn.Linear(supplier_dim, hidden_dim)
        self.proj_p = nn.Linear(product_dim, hidden_dim)
        self.w_p = nn.Linear(hidden_dim, hidden_dim)   # products, after receiving from suppliers
        self.w_s = nn.Linear(hidden_dim, hidden_dim)   # suppliers, after receiving from products
        self.out = nn.Linear(hidden_dim, 1)
        self.relu = nn.ReLU()

    def forward(self, x_s, x_p, s2p, p2s):
        """
        Args:
            x_s: (n_suppliers, supplier_dim) supplier node features.
            x_p: (n_products, product_dim) product node features.
            s2p: (n_suppliers, n_products) row-normalized supplier->product matrix.
            p2s: (n_products, n_suppliers) column-normalized product->supplier matrix.

        Returns:
            (n_suppliers,) predicted P95 exposure per supplier.
        """
        h_s = self.relu(self.proj_s(x_s))
        h_p = self.relu(self.proj_p(x_p))

        # Hop 1: suppliers -> shared products (message = renormalized adjacency @ features)
        msg_p = s2p.T @ h_s
        h_p = self.relu(self.w_p(msg_p) + h_p)

        # Hop 2: products -> co-suppliers
        msg_s = p2s.T @ h_p
        h_s = self.relu(self.w_s(msg_s) + h_s)

        return self.out(h_s).squeeze(-1)


def prepare_product_features(df_products, product_ids):
    """Static per-graph product features (unit_cost, monthly_demand), min-max
    normalized, aligned to product_ids order from build_bipartite_matrices."""
    df = df_products.set_index("product_id").reindex(product_ids)
    feats = df[["unit_cost", "monthly_demand"]].fillna(0.0).to_numpy(dtype=float)
    f_min, f_max = feats.min(axis=0), feats.max(axis=0)
    span = np.where(f_max == f_min, 1.0, f_max - f_min)
    return (feats - f_min) / span


def _factors_to_tensor(factors, supplier_ids):
    from src.scoring import FACTOR_NAMES
    aligned = factors.reindex(supplier_ids).fillna(0.0)[FACTOR_NAMES]
    return torch.tensor(aligned.to_numpy(dtype=float), dtype=torch.float32)


def train_gnn(train_records, supplier_ids, product_ids, s2p, p2s, product_features,
              hidden_dim=16, n_epochs=250, lr=0.01, random_state=42):
    """Trains a BipartiteGCN across every train seed's (factors, ground_truth)
    snapshot, sharing weights across seeds. Returns the trained model."""
    from src.scoring import FACTOR_NAMES

    torch.manual_seed(random_state)
    model = BipartiteGCN(supplier_dim=len(FACTOR_NAMES), product_dim=product_features.shape[1],
                          hidden_dim=hidden_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    s2p_t = torch.tensor(s2p, dtype=torch.float32)
    p2s_t = torch.tensor(p2s, dtype=torch.float32)
    x_p = torch.tensor(product_features, dtype=torch.float32)

    snapshots = []
    for rec in train_records:
        x_s = _factors_to_tensor(rec["factors"], supplier_ids)
        y = rec["ground_truth"].reindex(supplier_ids).fillna(0.0).to_numpy(dtype=float)
        # Scale the regression target to O(1) for stable training; GBT/MLP/LTR
        # don't need this since trees/pairwise-ranking are scale-invariant, but
        # raw revenue units (often in the millions) blow up gradient-based training.
        snapshots.append((x_s, torch.tensor(y, dtype=torch.float32)))

    y_all = torch.cat([y for _, y in snapshots])
    y_scale = float(y_all.std()) or 1.0

    model.train()
    for epoch in range(n_epochs):
        optimizer.zero_grad()
        total_loss = 0.0
        for x_s, y in snapshots:
            pred = model(x_s, x_p, s2p_t, p2s_t)
            loss = loss_fn(pred, y / y_scale)
            total_loss = total_loss + loss
        total_loss = total_loss / len(snapshots)
        total_loss.backward()
        optimizer.step()

    model.eval()
    model._y_scale = y_scale  # stash for predict_gnn
    return model


def predict_gnn(model, factors, supplier_ids, product_ids, s2p, p2s, product_features):
    """Scores one factor matrix with a trained BipartiteGCN. Returns a
    pd.Series indexed by supplier_id, higher = riskier (predicted exposure)."""
    s2p_t = torch.tensor(s2p, dtype=torch.float32)
    p2s_t = torch.tensor(p2s, dtype=torch.float32)
    x_p = torch.tensor(product_features, dtype=torch.float32)
    x_s = _factors_to_tensor(factors, supplier_ids)

    model.eval()
    with torch.no_grad():
        pred = model(x_s, x_p, s2p_t, p2s_t).numpy() * getattr(model, "_y_scale", 1.0)

    return pd.Series(pred, index=supplier_ids)
