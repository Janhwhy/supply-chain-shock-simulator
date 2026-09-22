"""graph.py — Graph construction and network centrality analysis for the supply chain."""

import networkx as nx
import pandas as pd
import numpy as np
from src.db import get_engine, read_table


def build_dependency_graph(df_relationships, df_suppliers, df_products):
    """
    Builds a weighted directed bipartite network of suppliers and products.

    Supplier nodes are prefixed with 'S_' to avoid key collisions with products.
    Product nodes are prefixed with 'P_'.

    Args:
        df_relationships (pd.DataFrame): Sourcing relationships containing:
            - supplier_id (int)
            - product_id (int)
            - supply_share (float)
        df_suppliers (pd.DataFrame): Supplier registry containing:
            - supplier_id (int)
            - supplier_name (str)
            - country (str)
            - tier (int)
            - reliability_score (float)
        df_products (pd.DataFrame): Product registry containing:
            - product_id (int)
            - sku (str)
            - product_name (str)

    Returns:
        nx.DiGraph: Bipartite directed graph with weighted edges from suppliers to products.
    """
    G = nx.DiGraph()

    # Add supplier nodes with their metadata attributes
    for _, row in df_suppliers.iterrows():
        supplier_id = int(row["supplier_id"])
        node_id = f"S_{supplier_id}"
        G.add_node(
            node_id,
            supplier_name=row["supplier_name"],
            country=row["country"],
            tier=int(row["tier"]) if pd.notnull(row["tier"]) else None,
            reliability_score=(
                float(row["reliability_score"])
                if pd.notnull(row["reliability_score"])
                else None
            ),
            type="supplier",
        )

    # Add product nodes with their metadata attributes if present
    for _, row in df_products.iterrows():
        product_id = int(row["product_id"])
        node_id = f"P_{product_id}"
        sku = row.get("sku", None)
        product_name = row.get("product_name", None)
        G.add_node(
            node_id,
            sku=sku,
            product_name=product_name,
            type="product",
        )

    # Add directed edges from suppliers to products with weight=supply_share
    for _, row in df_relationships.iterrows():
        supplier_id = int(row["supplier_id"])
        product_id = int(row["product_id"])
        u = f"S_{supplier_id}"
        v = f"P_{product_id}"
        weight = float(row["supply_share"])
        G.add_edge(u, v, weight=weight)

    return G


def compute_pagerank(G, alpha=0.85):
    """
    Computes PageRank centrality for all nodes in the dependency graph.

    Args:
        G (nx.DiGraph): The supply chain directed graph.
        alpha (float): Damping factor. Default is 0.85.

    Returns:
        pd.DataFrame: Sorted DataFrame with columns:
            - node_id (str)
            - node_type (str)
            - pagerank_score (float)
    """
    if len(G) == 0:
        return pd.DataFrame(columns=["node_id", "node_type", "pagerank_score"])

    # Compute pagerank utilizing edge weights
    pr_scores = nx.pagerank(G, alpha=alpha, weight="weight")

    records = []
    for node, score in pr_scores.items():
        node_type = G.nodes[node].get("type", "unknown")
        records.append(
            {
                "node_id": node,
                "node_type": node_type,
                "pagerank_score": score,
            }
        )

    df_pr = pd.DataFrame(records)
    df_pr = df_pr.sort_values(by="pagerank_score", ascending=False).reset_index(
        drop=True
    )
    return df_pr


def compute_centrality_metrics(G):
    """
    Computes degree, betweenness, and closeness centrality for supplier nodes only.

    Args:
        G (nx.DiGraph): The supply chain directed graph.

    Returns:
        pd.DataFrame: DataFrame containing supplier metrics:
            - node_id (str)
            - supplier_id (int)
            - degree_centrality (float)
            - betweenness_centrality (float)
            - closeness_centrality (float)
    """
    # Filter for supplier nodes
    supplier_nodes = [
        n for n, d in G.nodes(data=True) if d.get("type") == "supplier"
    ]

    if not supplier_nodes or len(G) == 0:
        return pd.DataFrame(
            columns=[
                "node_id",
                "supplier_id",
                "degree_centrality",
                "betweenness_centrality",
                "closeness_centrality",
            ]
        )

    # Compute network-wide centrality metrics
    deg_cent = nx.degree_centrality(G)
    bet_cent = nx.betweenness_centrality(G)
    clo_cent = nx.closeness_centrality(G)

    records = []
    for node in supplier_nodes:
        # Extract integer supplier_id from node_id string (e.g. 'S_1' -> 1)
        try:
            supplier_id = int(node.split("_")[1])
        except (IndexError, ValueError):
            supplier_id = node

        records.append(
            {
                "node_id": node,
                "supplier_id": supplier_id,
                "degree_centrality": float(deg_cent.get(node, 0.0)),
                "betweenness_centrality": float(bet_cent.get(node, 0.0)),
                "closeness_centrality": float(clo_cent.get(node, 0.0)),
            }
        )

    return pd.DataFrame(records)


def build_bipartite_matrices(G):
    """
    Builds the normalized bipartite adjacency matrices shared by every
    graph-propagation method on this project (the hand-designed diffusion in
    compute_risk_propagation below, and the learned GNN in
    evaluation/gnn_model.py) — single source of truth for "how the bipartite
    adjacency is built" so both stay consistent with the same graph.

    Args:
        G (nx.DiGraph): The supply chain directed graph (supplier -> product,
            weight=supply_share), as built by build_dependency_graph.

    Returns:
        tuple:
            - supplier_ids (list[int]): supplier_id per row of s2p / column of p2s.
            - product_ids (list[int]): product_id per column of s2p / row of p2s.
            - s2p (np.ndarray): row-normalized supplier -> product matrix
              (each supplier's outgoing weights sum to 1).
            - p2s (np.ndarray): column-normalized product -> supplier matrix
              (each product's outgoing weights, to its co-suppliers, sum to 1).
    """
    supplier_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "supplier"]
    product_nodes = [n for n, d in G.nodes(data=True) if d.get("type") == "product"]

    if not supplier_nodes or not product_nodes:
        return [], [], np.zeros((0, 0)), np.zeros((0, 0))

    supplier_ids = [int(n.split("_", 1)[1]) for n in supplier_nodes]
    product_ids = [int(n.split("_", 1)[1]) for n in product_nodes]
    s_idx = {n: i for i, n in enumerate(supplier_nodes)}
    p_idx = {n: i for i, n in enumerate(product_nodes)}

    # Raw supplier -> product weight matrix (supply_share on each edge)
    raw = np.zeros((len(supplier_nodes), len(product_nodes)))
    for u, v, data in G.edges(data=True):
        if u in s_idx and v in p_idx:
            raw[s_idx[u], p_idx[v]] = data.get("weight", 0.0)

    # Row-normalize: supplier -> its products, weighted by relative supply share
    row_sums = raw.sum(axis=1, keepdims=True)
    s2p = np.divide(raw, row_sums, out=np.zeros_like(raw), where=row_sums != 0)

    # Column-normalize the same edges (transposed): product -> its co-suppliers
    col_sums = raw.sum(axis=0, keepdims=True)
    p2s = np.divide(raw.T, col_sums.T, out=np.zeros_like(raw.T), where=col_sums.T != 0)

    return supplier_ids, product_ids, s2p, p2s


def compute_risk_propagation(G, base_risk, n_hops=3, damping=0.5):
    """
    Diffuses each supplier's own risk score across the bipartite supplier-product
    graph to surface correlated ("systemic") exposure: a supplier that shares
    products with other high-risk suppliers inherits some of that risk, since a
    shock large enough to hit the shared product's supply base tends to hit
    co-suppliers together (same disruption channel). Existing single-hop factors
    (e.g. substitutability_risk) only count how many alternatives a product has,
    not how risky those alternatives are, so they miss this effect entirely.

    Hand-designed propagation (fixed per-hop damping) — contrast with the
    learned version of the same idea in evaluation/gnn_model.py::BipartiteGCN,
    which uses this same bipartite structure (build_bipartite_matrices) but
    learns the propagation weights from data instead of hand-setting them.

    Args:
        G (nx.DiGraph): The supply chain directed graph (supplier -> product,
            weight=supply_share), as built by build_dependency_graph.
        base_risk (pd.Series): Risk score per supplier_id (0-1) used as the
            propagation seed, e.g. the existing composite risk factors.
        n_hops (int): Number of supplier->product->supplier round trips to
            diffuse risk across. Default 3.
        damping (float): Per-hop decay applied to each successive hop's
            contribution. Default 0.5.

    Returns:
        pd.DataFrame: DataFrame with columns:
            - supplier_id (int)
            - propagated_risk_score (float, 0 to 1, min-max normalized)
    """
    supplier_ids, product_ids, s2p, p2s = build_bipartite_matrices(G)

    if not supplier_ids or not product_ids:
        return pd.DataFrame(columns=["supplier_id", "propagated_risk_score"])

    r0 = base_risk.reindex(supplier_ids).fillna(0.0).to_numpy(dtype=float)
    accumulated = r0.copy()
    current = r0.copy()
    for hop in range(1, n_hops + 1):
        product_risk = current @ s2p  # suppliers -> shared products
        current = product_risk @ p2s  # products -> co-suppliers
        accumulated += (damping ** hop) * current

    a_min, a_max = accumulated.min(), accumulated.max()
    if a_max == a_min:
        scaled = np.zeros_like(accumulated)
    else:
        scaled = (accumulated - a_min) / (a_max - a_min)

    return pd.DataFrame({"supplier_id": supplier_ids, "propagated_risk_score": scaled})


def identify_critical_suppliers(
    df_pagerank, df_centrality, df_relationships, top_n=10
):
    """
    Combines PageRank and centrality metrics to rank and flag critical suppliers.

    Flags suppliers that are sole source for any product, or whose PageRank score
    places them in the top 20% of the entire network.

    Args:
        df_pagerank (pd.DataFrame): PageRank results for all nodes.
        df_centrality (pd.DataFrame): Centrality metrics for supplier nodes.
        df_relationships (pd.DataFrame): Relationship DataFrame containing 'is_sole_source'.
        top_n (int): Number of top suppliers to return. Default is 10.

    Returns:
        pd.DataFrame: Ranked and filtered critical supplier DataFrame with merged attributes.
    """
    # 1. Filter PageRank to supplier nodes only and parse supplier_id
    df_pr_sups = df_pagerank[df_pagerank["node_type"] == "supplier"].copy()
    if df_pr_sups.empty:
        return pd.DataFrame()

    def parse_id(val):
        if isinstance(val, str) and "_" in val:
            return int(val.split("_")[1])
        return int(val)

    df_pr_sups["supplier_id"] = df_pr_sups["node_id"].apply(parse_id)

    # 2. Merge PageRank and Centrality metrics on supplier_id
    df_merged = pd.merge(
        df_pr_sups, df_centrality, on="supplier_id", how="inner", suffixes=("", "_cent")
    )
    if "node_id_cent" in df_merged.columns:
        df_merged = df_merged.drop(columns=["node_id_cent"])

    # 3. Flag suppliers that are sole source for any product in relationships
    # Group by supplier_id and check if is_sole_source is True anywhere
    if "is_sole_source" in df_relationships.columns:
        sole_source_series = df_relationships.groupby("supplier_id")[
            "is_sole_source"
        ].any()
        sole_source_dict = sole_source_series.to_dict()
    else:
        sole_source_dict = {}

    df_merged["is_sole_source"] = (
        df_merged["supplier_id"].map(sole_source_dict).fillna(False).astype(bool)
    )

    # 4. Flag suppliers whose PageRank puts them in the top 20% of the network
    # We check against the overall network PageRank scores (df_pagerank)
    if not df_pagerank.empty:
        pr_threshold = df_pagerank["pagerank_score"].quantile(0.80)
        df_merged["is_top_20_pagerank"] = (
            df_merged["pagerank_score"] >= pr_threshold
        )
    else:
        df_merged["is_top_20_pagerank"] = False

    # 5. Sort descending by PageRank score and return top_n
    df_ranked = df_merged.sort_values(
        by="pagerank_score", ascending=False
    ).reset_index(drop=True)
    return df_ranked.head(top_n)


def graph_summary(G):
    """
    Computes and prints summary statistics for the dependency graph.

    Args:
        G (nx.DiGraph): The supply chain directed graph.
    """
    total_nodes = G.number_of_nodes()
    total_edges = G.number_of_edges()

    supplier_nodes = [
        n for n, d in G.nodes(data=True) if d.get("type") == "supplier"
    ]
    product_nodes = [
        n for n, d in G.nodes(data=True) if d.get("type") == "product"
    ]

    num_suppliers = len(supplier_nodes)
    num_products = len(product_nodes)

    # Average degree calculation (sum of in_degree + out_degree / total_nodes)
    degrees = dict(G.degree())
    avg_degree = (
        sum(degrees.values()) / total_nodes if total_nodes > 0 else 0.0
    )

    # Density
    density = nx.density(G)

    # Connectivity
    # For a directed graph, we check if it is weakly connected
    is_weakly_connected = nx.is_weakly_connected(G) if total_nodes > 0 else False

    # PageRank for top 5 nodes
    df_pr = compute_pagerank(G)
    top_5 = df_pr.head(5)

    print(f"Total Nodes: {total_nodes}")
    print(f"Total Edges: {total_edges}")
    print(f"Number of Supplier Nodes: {num_suppliers}")
    print(f"Number of Product Nodes: {num_products}")
    print(f"Average Degree: {avg_degree:.4f}")
    print(f"Density: {density:.6f}")
    print(f"Is Weakly Connected: {is_weakly_connected}")

    print("\nTop 5 Nodes by PageRank:")
    for idx, row in top_5.iterrows():
        print(
            f"  {idx + 1}. Node ID: {row['node_id']} "
            f"({row['node_type']}) - "
            f"PageRank Score: {row['pagerank_score']:.6f}"
        )


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()
    print("Connecting to the database...")
    try:
        df_sups = read_table("suppliers")
        df_prods = read_table("products")
        df_rels = read_table("supply_relationships")
        print("Database load successful.")
    except Exception as e:
        print(f"Database read failed: {e}")
        print("Attempting to load CSV backups from data/raw/synthetic/...")
        try:
            import os
            csv_dir = os.path.abspath(
                os.path.join(
                    os.path.dirname(__file__), "..", "data", "raw", "synthetic"
                )
            )
            df_sups = pd.read_csv(os.path.join(csv_dir, "suppliers.csv"))
            df_prods = pd.read_csv(os.path.join(csv_dir, "products.csv"))
            df_rels = pd.read_csv(os.path.join(csv_dir, "supply_relationships.csv"))
            print("CSV load successful.")
        except Exception as csv_err:
            print(f"Failed to load CSV backups: {csv_err}")
            sys.exit(1)

    print("\n--- Constructing Dependency Graph ---")
    G = build_dependency_graph(df_rels, df_sups, df_prods)

    print("\n--- Graph Summary ---")
    graph_summary(G)

    print("\n--- Top 10 Critical Suppliers ---")
    df_pr = compute_pagerank(G)
    df_cent = compute_centrality_metrics(G)
    df_crit = identify_critical_suppliers(df_pr, df_cent, df_rels, top_n=10)

    # Merge with suppliers to show details nicely
    df_display = df_crit.merge(
        df_sups[["supplier_id", "supplier_name", "country", "tier"]],
        on="supplier_id",
    )
    print(
        df_display[
            [
                "supplier_id",
                "supplier_name",
                "country",
                "tier",
                "pagerank_score",
                "is_sole_source",
                "is_top_20_pagerank",
            ]
        ].to_string(index=False)
    )
