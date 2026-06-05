"""test_graph.py — Unit tests for the graph analysis module."""

import io
import sys
import unittest
import pandas as pd
import networkx as nx
from src.graph import (
    build_dependency_graph,
    compute_pagerank,
    compute_centrality_metrics,
    identify_critical_suppliers,
    graph_summary,
)


class TestGraphModule(unittest.TestCase):
    def setUp(self):
        # Set up mock DataFrames
        self.df_suppliers = pd.DataFrame(
            [
                {
                    "supplier_id": 1,
                    "supplier_name": "Supplier A",
                    "country": "USA",
                    "tier": 1,
                    "reliability_score": 0.95,
                },
                {
                    "supplier_id": 2,
                    "supplier_name": "Supplier B",
                    "country": "Germany",
                    "tier": 2,
                    "reliability_score": 0.88,
                },
                {
                    "supplier_id": 3,
                    "supplier_name": "Supplier C",
                    "country": "China",
                    "tier": 2,
                    "reliability_score": None,
                },
            ]
        )

        self.df_products = pd.DataFrame(
            [
                {
                    "product_id": 10,
                    "sku": "SKU-010",
                    "product_name": "Product X",
                },
                {
                    "product_id": 20,
                    "sku": "SKU-020",
                    "product_name": "Product Y",
                },
            ]
        )

        self.df_relationships = pd.DataFrame(
            [
                {"supplier_id": 1, "product_id": 10, "supply_share": 0.60},
                {"supplier_id": 2, "product_id": 10, "supply_share": 0.40},
                {"supplier_id": 3, "product_id": 20, "supply_share": 1.00},
            ]
        )

    def test_build_dependency_graph(self):
        G = build_dependency_graph(
            self.df_relationships, self.df_suppliers, self.df_products
        )

        # Total nodes: 3 suppliers + 2 products = 5 nodes
        self.assertEqual(G.number_of_nodes(), 5)
        # Total edges: 3 relationships
        self.assertEqual(G.number_of_edges(), 3)

        # Check node attributes
        self.assertTrue(G.has_node("S_1"))
        self.assertEqual(G.nodes["S_1"]["supplier_name"], "Supplier A")
        self.assertEqual(G.nodes["S_1"]["country"], "USA")
        self.assertEqual(G.nodes["S_1"]["tier"], 1)
        self.assertEqual(G.nodes["S_1"]["reliability_score"], 0.95)
        self.assertEqual(G.nodes["S_1"]["type"], "supplier")

        self.assertTrue(G.has_node("S_3"))
        self.assertIsNone(G.nodes["S_3"]["reliability_score"])

        self.assertTrue(G.has_node("P_10"))
        self.assertEqual(G.nodes["P_10"]["sku"], "SKU-010")
        self.assertEqual(G.nodes["P_10"]["type"], "product")

        # Check edge weights
        self.assertTrue(G.has_edge("S_1", "P_10"))
        self.assertAlmostEqual(G["S_1"]["P_10"]["weight"], 0.60)
        self.assertTrue(G.has_edge("S_3", "P_20"))
        self.assertAlmostEqual(G["S_3"]["P_20"]["weight"], 1.00)

    def test_compute_pagerank(self):
        G = build_dependency_graph(
            self.df_relationships, self.df_suppliers, self.df_products
        )
        df_pr = compute_pagerank(G, alpha=0.85)

        # Verify DataFrame format
        self.assertListEqual(
            list(df_pr.columns), ["node_id", "node_type", "pagerank_score"]
        )
        self.assertEqual(len(df_pr), 5)

        # Sum of PageRank scores should be approx 1.0
        self.assertAlmostEqual(df_pr["pagerank_score"].sum(), 1.0, places=4)

        # Verify descending sort order
        scores = df_pr["pagerank_score"].tolist()
        self.assertTrue(all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1)))

    def test_compute_centrality_metrics(self):
        G = build_dependency_graph(
            self.df_relationships, self.df_suppliers, self.df_products
        )
        df_cent = compute_centrality_metrics(G)

        # Verify DataFrame columns
        expected_cols = [
            "node_id",
            "supplier_id",
            "degree_centrality",
            "betweenness_centrality",
            "closeness_centrality",
        ]
        self.assertListEqual(list(df_cent.columns), expected_cols)

        # Verify that only suppliers are in the results
        self.assertEqual(len(df_cent), 3)
        self.assertCountEqual(df_cent["supplier_id"].tolist(), [1, 2, 3])

        # Verification of non-negative centrality values
        for col in [
            "degree_centrality",
            "betweenness_centrality",
            "closeness_centrality",
        ]:
            self.assertTrue(all(df_cent[col] >= 0.0))

    def test_identify_critical_suppliers(self):
        G = build_dependency_graph(
            self.df_relationships, self.df_suppliers, self.df_products
        )
        df_pr = compute_pagerank(G)
        df_cent = compute_centrality_metrics(G)

        # Add is_sole_source flag in df_relationships for supplier 3 on product 20
        df_rels_mock = self.df_relationships.copy()
        df_rels_mock["is_sole_source"] = [False, False, True]

        df_crit = identify_critical_suppliers(
            df_pr, df_cent, df_rels_mock, top_n=2
        )

        # Verify columns & top_n limit
        self.assertEqual(len(df_crit), 2)
        self.assertIn("is_sole_source", df_crit.columns)
        self.assertIn("is_top_20_pagerank", df_crit.columns)

        # Supplier 3 (S_3) has sole source relation
        s3_row = df_crit[df_crit["supplier_id"] == 3]
        if not s3_row.empty:
            self.assertTrue(s3_row["is_sole_source"].values[0])

    def test_graph_summary(self):
        G = build_dependency_graph(
            self.df_relationships, self.df_suppliers, self.df_products
        )

        # Capture output of graph_summary(G)
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            graph_summary(G)
        finally:
            sys.stdout = sys.__stdout__

        output_text = captured_output.getvalue()
        self.assertIn("Total Nodes: 5", output_text)
        self.assertIn("Total Edges: 3", output_text)
        self.assertIn("Number of Supplier Nodes: 3", output_text)
        self.assertIn("Number of Product Nodes: 2", output_text)
        self.assertIn("Is Weakly Connected:", output_text)
        self.assertIn("Top 5 Nodes by PageRank:", output_text)


if __name__ == "__main__":
    unittest.main()
