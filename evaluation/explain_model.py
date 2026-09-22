"""explain_model.py — SHAP-based feature attribution ("why is this supplier
risky, not just how risky") for whichever model evaluation/train_ml_models.py
persisted as the winner.

Motivation
----------
Every score in this project up to now answers "how risky" — a single
number. None of them answer "why": which of the six risk factors is actually
driving that number for a given supplier. That's a real gap for anyone who
has to act on the score (a supplier ops lead doesn't want a 0.83, they want
"driven mostly by revenue-weighted concentration and network propagation").
SHAP (Lundberg & Lee, "A Unified Approach to Interpreting Model
Predictions," NeurIPS 2017) is the standard way to close that gap: it
attributes a model's prediction for one input to each feature, with the
attributions summing back to (prediction - average prediction) — a
game-theoretic (Shapley value) fair split of "credit" across features.

Usage here mirrors how the cited literature applies it (AI in Supply Chain
Risk Assessment, arXiv 2401.10895; Explainability in supply chain
operational risk management, ScienceDirect): TreeExplainer (fast, exact) for
gbt, a black-box Explainer for mlp/ltr, and — since none of the SHAP
literature this project could find addresses graph-structured models
directly — a purpose-built graph-aware explainer for gnn (see
_gnn_predict_fn below) that perturbs one supplier's own features while
holding the rest of the graph fixed and forward-passing the whole graph per
perturbation, rather than pretending the GNN's prediction is a function of
one row in isolation the way the tabular models' predictions are.
"""

import numpy as np
import pandas as pd
import shap

from src.scoring import FACTOR_NAMES


def _tabular_predict_fn(model, model_name):
    if model_name == "ltr":
        return lambda X: model.decision_function(X)
    return lambda X: model.predict(X)


def _gnn_predict_fn(model, gnn_context, target_supplier_id):
    """Closes over one target supplier: each call substitutes a candidate
    feature row for that supplier into the full (fixed) graph snapshot,
    forward-passes the whole graph, and returns that supplier's prediction —
    a graph-aware analogue of a plain row-wise tabular predict function."""
    try:
        # Sibling import — works when this module is imported as a bare
        # top-level module (evaluation/ is the running script's directory,
        # e.g. `python evaluation/train_ml_models.py`).
        from gnn_model import predict_gnn
    except ImportError:
        # Namespace-package import — works when this module is imported as
        # `evaluation.explain_model` from a different working directory
        # (e.g. api/main.py, which only puts the repo root on sys.path).
        from evaluation.gnn_model import predict_gnn
    supplier_ids, product_ids, s2p, p2s, product_features, base_factors = gnn_context

    def f(X):
        out = np.zeros(len(X))
        for i, row in enumerate(X):
            perturbed = base_factors.copy()
            perturbed.loc[target_supplier_id, FACTOR_NAMES] = row
            preds = predict_gnn(model, perturbed, supplier_ids, product_ids, s2p, p2s, product_features)
            out[i] = preds.loc[target_supplier_id]
        return out

    return f


def compute_shap_values(model, model_name, factors, target_supplier_id=None,
                         gnn_context=None, max_background=50):
    """
    Computes signed SHAP feature attributions (positive = pushes predicted
    risk up) for the given model.

    Args:
        model: the trained model object (from evaluation/train_ml_models.py
            or evaluation/gnn_model.py).
        model_name (str): one of "gbt", "mlp", "ltr", "gnn".
        factors (pd.DataFrame): the full current risk-factor matrix (index=
            supplier_id, columns=FACTOR_NAMES) — also used as the SHAP
            background distribution, so attributions read as "relative to
            the current supplier population."
        target_supplier_id (int, optional): explain only this one supplier
            (cheap — used for live API serving). None explains every
            supplier in `factors` in one batched call (used offline).
        gnn_context (tuple, optional): required when model_name == "gnn":
            (supplier_ids, product_ids, s2p, p2s, product_features,
            base_factors) as produced alongside evaluation/gnn_model.py's
            train_gnn/predict_gnn.
        max_background (int): caps the background sample size for speed.

    Returns:
        pd.DataFrame indexed by supplier_id, columns=FACTOR_NAMES.
    """
    background = factors[FACTOR_NAMES].to_numpy()
    if len(background) > max_background:
        rng = np.random.default_rng(0)
        background = background[rng.choice(len(background), max_background, replace=False)]

    rows = factors[FACTOR_NAMES] if target_supplier_id is None else factors.loc[[target_supplier_id], FACTOR_NAMES]

    if model_name == "gbt":
        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(rows.to_numpy())
    elif model_name == "gnn":
        if gnn_context is None:
            raise ValueError("gnn_context is required to explain a gnn model")
        all_values = []
        for sid in rows.index:
            predict_fn = _gnn_predict_fn(model, gnn_context, sid)
            explainer = shap.Explainer(predict_fn, background)
            all_values.append(explainer(rows.loc[[sid]].to_numpy()).values[0])
        values = np.array(all_values)
    else:
        explainer = shap.Explainer(_tabular_predict_fn(model, model_name), background)
        values = explainer(rows.to_numpy()).values

    return pd.DataFrame(values, index=rows.index, columns=FACTOR_NAMES)


def top_factors(shap_row, n=3):
    """Turns one supplier's SHAP row (a pd.Series) into a small ranked list
    of {factor, contribution} dicts, largest absolute contribution first —
    the shape the API/frontend actually consume."""
    ordered = shap_row.reindex(shap_row.abs().sort_values(ascending=False).index)
    return [{"factor": f, "contribution": float(v)} for f, v in ordered.head(n).items()]
