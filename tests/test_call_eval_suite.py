"""
Unit tests for AI Call Eval Suite and Golden Dataset.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts.harness.evaluate_call_prompts import (
    calculate_metrics,
    generate_markdown_report,
    load_golden_dataset,
)


class TestCallEvalSuite(unittest.TestCase):
    def test_golden_dataset_structure(self):
        dataset_path = Path("data/golden_call_eval_dataset.json")
        self.assertTrue(dataset_path.exists(), "data/golden_call_eval_dataset.json must exist")
        samples = load_golden_dataset(str(dataset_path))
        self.assertGreaterEqual(len(samples), 20, "Golden dataset must have at least 20 samples")

        for sample in samples:
            self.assertIn("id", sample)
            self.assertIn("transcript", sample)
            self.assertIn("expected_score", sample)
            self.assertIn("expected_category", sample)
            self.assertGreater(len(sample["transcript"]), 50)
            self.assertGreater(sample["expected_score"], 0)

    def test_calculate_metrics(self):
        mock_results = [
            {
                "expected_score": 80,
                "predicted_score": 82,
                "expected_category": "Mijoz",
                "predicted_category": "Mijoz",
                "expected_objections": ["Narx"],
                "predicted_objections": ["Narx"],
            },
            {
                "expected_score": 50,
                "predicted_score": 55,
                "expected_category": "Hamkor",
                "predicted_category": "Hamkor",
                "expected_objections": [],
                "predicted_objections": [],
            },
        ]
        metrics = calculate_metrics(mock_results)
        self.assertEqual(metrics["total_evaluated"], 2)
        self.assertEqual(metrics["mean_absolute_error"], 3.5)
        self.assertEqual(metrics["category_accuracy_pct"], 100.0)
        self.assertEqual(metrics["objection_accuracy_pct"], 100.0)
        self.assertTrue(metrics["calibration_grade"].startswith("A"))


    def test_generate_markdown_report(self):
        metrics = {
            "total_evaluated": 1,
            "mean_absolute_error": 2.0,
            "category_accuracy_pct": 100.0,
            "objection_accuracy_pct": 100.0,
            "calibration_grade": "A",
        }
        results = [{
            "id": 999,
            "manager_name": "Sotuvchi",
            "expected_score": 75,
            "predicted_score": 77,
            "predicted_category": "Mijoz",
            "summary": "Sinov xulosasi",
        }]
        md = generate_markdown_report(metrics, results)
        self.assertIn("# AI Call Eval Suite", md)
        self.assertIn("MAE", md)
        self.assertIn("Sotuvchi", md)


if __name__ == "__main__":
    unittest.main()
