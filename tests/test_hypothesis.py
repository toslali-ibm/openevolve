# tests/test_hypothesis.py
"""Tests for the core hypothesis module."""
import json
import tempfile
import unittest
from pathlib import Path

from openevolve.hypothesis import (
    parse_hypotheses,
    test_hypotheses,
    load_ledger,
    update_ledger,
    generate_knowledge_base_summary,
    format_hypothesis_results,
)


class TestParseHypotheses(unittest.TestCase):
    """Test hypothesis parsing from code comments."""

    def test_parse_python_comments(self):
        code = """
# HYPOTHESIS-1: Local search improves distance_score
# MECHANISM-1: Gradient descent from random starts finds nearby minima
# EXPECT-1: distance_score < 0.8
x = 1
"""
        result = parse_hypotheses(code, valid_metrics={"distance_score", "value_score"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], 1)
        self.assertEqual(result[0]["metric"], "distance_score")
        self.assertAlmostEqual(result[0]["threshold"], 0.8)

    def test_parse_go_comments(self):
        code = """
// HYPOTHESIS-1: Cache affinity reduces latency
// MECHANISM-1: Requests with large prefixes benefit from cache reuse
// EXPECT-1: avg_e2e_ms < 5000
"""
        result = parse_hypotheses(code, valid_metrics={"avg_e2e_ms"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["claim"], "Cache affinity reduces latency")

    def test_parse_multiple_hypotheses(self):
        code = """
# HYPOTHESIS-1: First claim
# MECHANISM-1: First mechanism
# EXPECT-1: metric_a < 10.0
# HYPOTHESIS-2: Second claim
# MECHANISM-2: Second mechanism
# EXPECT-2: metric_b < 20.0
"""
        result = parse_hypotheses(code, valid_metrics={"metric_a", "metric_b"})
        self.assertEqual(len(result), 2)

    def test_skip_invalid_metric(self):
        code = """
# HYPOTHESIS-1: Some claim
# MECHANISM-1: Some mechanism
# EXPECT-1: nonexistent_metric < 10.0
"""
        result = parse_hypotheses(code, valid_metrics={"valid_metric"})
        self.assertEqual(len(result), 0)

    def test_skip_incomplete_hypothesis(self):
        code = """
# HYPOTHESIS-1: Claim without expect
# MECHANISM-1: Some mechanism
"""
        result = parse_hypotheses(code, valid_metrics={"any"})
        self.assertEqual(len(result), 0)

    def test_multiline_mechanism(self):
        code = """
# HYPOTHESIS-1: Some claim
# MECHANISM-1: First line of mechanism
#   continuation of mechanism
#   more continuation
# EXPECT-1: metric_a < 5.0
"""
        result = parse_hypotheses(code, valid_metrics={"metric_a"})
        self.assertEqual(len(result), 1)
        self.assertIn("First line", result[0]["mechanism"])
        self.assertIn("continuation", result[0]["mechanism"])

    def test_parse_greater_than_operator(self):
        code = """
# HYPOTHESIS-1: Better search improves value_score
# MECHANISM-1: Multi-start search covers more basins
# EXPECT-1: value_score > 0.8
"""
        result = parse_hypotheses(code, valid_metrics={"value_score"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["operator"], ">")
        self.assertAlmostEqual(result[0]["threshold"], 0.8)

    def test_parse_less_than_operator_default(self):
        code = """
# HYPOTHESIS-1: Reduces latency
# MECHANISM-1: Cache routing
# EXPECT-1: avg_e2e_ms < 5000
"""
        result = parse_hypotheses(code, valid_metrics={"avg_e2e_ms"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["operator"], "<")

    def test_parse_mixed_operators(self):
        code = """
# HYPOTHESIS-1: Reduces latency
# MECHANISM-1: Cache routing
# EXPECT-1: avg_e2e_ms < 5000
# HYPOTHESIS-2: Improves accuracy
# MECHANISM-2: Better search
# EXPECT-2: accuracy > 0.95
"""
        result = parse_hypotheses(code, valid_metrics={"avg_e2e_ms", "accuracy"})
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["operator"], "<")
        self.assertEqual(result[1]["operator"], ">")


class TestTestHypotheses(unittest.TestCase):
    """Test hypothesis verdict logic."""

    def test_confirmed(self):
        hypotheses = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x", "threshold": 10.0}]
        results = test_hypotheses(hypotheses, {"x": 8.0}, {"x": 12.0})
        self.assertEqual(results[0]["verdict"], "CONFIRMED")

    def test_refuted(self):
        hypotheses = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x", "threshold": 10.0}]
        results = test_hypotheses(hypotheses, {"x": 15.0}, {"x": 12.0})
        self.assertEqual(results[0]["verdict"], "REFUTED")

    def test_inconclusive_missing_metric(self):
        hypotheses = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x", "threshold": 10.0}]
        results = test_hypotheses(hypotheses, {}, {"x": 12.0})
        self.assertEqual(results[0]["verdict"], "INCONCLUSIVE")

    def test_delta_vs_baseline(self):
        hypotheses = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x", "threshold": 10.0}]
        results = test_hypotheses(hypotheses, {"x": 9.0}, {"x": 10.0})
        self.assertAlmostEqual(results[0]["delta_vs_baseline_pct"], -10.0)

    def test_confirmed_greater_than(self):
        hypotheses = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x", "operator": ">", "threshold": 0.8}]
        results = test_hypotheses(hypotheses, {"x": 0.9}, {"x": 0.7})
        self.assertEqual(results[0]["verdict"], "CONFIRMED")

    def test_refuted_greater_than(self):
        hypotheses = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x", "operator": ">", "threshold": 0.8}]
        results = test_hypotheses(hypotheses, {"x": 0.5}, {"x": 0.7})
        self.assertEqual(results[0]["verdict"], "REFUTED")

    def test_operator_preserved_in_result(self):
        hypotheses = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x", "operator": ">", "threshold": 0.8}]
        results = test_hypotheses(hypotheses, {"x": 0.9}, {"x": 0.7})
        self.assertEqual(results[0]["operator"], ">")


class TestLedger(unittest.TestCase):
    """Test ledger persistence."""

    def test_load_empty(self):
        ledger = load_ledger(Path("/nonexistent/path.json"))
        self.assertEqual(ledger, {"baseline": {}, "entries": []})

    def test_update_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = load_ledger(path)
            h_results = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x",
                          "threshold": 10.0, "actual": 8.0, "baseline_value": 12.0,
                          "delta_vs_baseline_pct": -33.3, "verdict": "CONFIRMED"}]
            update_ledger(ledger, h_results, -100.0, path)
            reloaded = load_ledger(path)
            self.assertEqual(len(reloaded["entries"]), 1)
            self.assertAlmostEqual(reloaded["entries"][0]["overall_combined_score"], -100.0)


class TestKnowledgeBaseSummary(unittest.TestCase):
    """Test knowledge base summary generation."""

    def test_empty_ledger(self):
        summary = generate_knowledge_base_summary({"baseline": {}, "entries": []})
        self.assertIn("No hypothesis data yet", summary)

    def test_confirmed_section(self):
        ledger = {
            "baseline": {"x": 10.0},
            "entries": [
                {"hypotheses": [{"id": 1, "claim": "good strategy", "mechanism": "works",
                                 "metric": "x", "verdict": "CONFIRMED",
                                 "delta_vs_baseline_pct": -15.0}]},
                {"hypotheses": [{"id": 1, "claim": "good strategy", "mechanism": "works",
                                 "metric": "x", "verdict": "CONFIRMED",
                                 "delta_vs_baseline_pct": -10.0}]},
            ],
        }
        summary = generate_knowledge_base_summary(ledger)
        self.assertIn("CONFIRMED STRATEGIES", summary)
        self.assertIn("good strategy", summary)

    def test_baseline_values_shown(self):
        ledger = {"baseline": {"x": 42.0}, "entries": []}
        summary = generate_knowledge_base_summary(ledger)
        self.assertIn("42.0", summary)


class TestConfigHypothesisDriven(unittest.TestCase):
    """Test hypothesis_driven config flag."""

    def test_config_hypothesis_driven_default(self):
        from openevolve.config import Config
        config = Config()
        self.assertTrue(config.hypothesis_driven)

    def test_config_hypothesis_driven_from_dict(self):
        from openevolve.config import Config
        config = Config.from_dict({"hypothesis_driven": False})
        self.assertFalse(config.hypothesis_driven)


class TestPromptInjection(unittest.TestCase):
    """Test that hypothesis instructions are injected into prompts correctly."""

    def test_hypothesis_driven_true_appends_template(self):
        from openevolve.config import PromptConfig
        from openevolve.prompt.sampler import PromptSampler
        config = PromptConfig()
        config.system_message = "You are a helpful assistant."
        sampler = PromptSampler(config)
        result = sampler.build_prompt(
            current_program="x = 1",
            hypothesis_driven=True,
        )
        self.assertIn("HYPOTHESIS-N", result["system"])
        self.assertIn("MECHANISM-N", result["system"])
        self.assertIn("EXPECT-N", result["system"])

    def test_hypothesis_driven_false_no_template(self):
        from openevolve.config import PromptConfig
        from openevolve.prompt.sampler import PromptSampler
        config = PromptConfig()
        config.system_message = "You are a helpful assistant."
        sampler = PromptSampler(config)
        result = sampler.build_prompt(
            current_program="x = 1",
            hypothesis_driven=False,
        )
        self.assertNotIn("HYPOTHESIS-N", result["system"])

    def test_hypothesis_driven_skips_if_already_present(self):
        from openevolve.config import PromptConfig
        from openevolve.prompt.sampler import PromptSampler
        config = PromptConfig()
        config.system_message = "You must write HYPOTHESIS comments."
        sampler = PromptSampler(config)
        result = sampler.build_prompt(
            current_program="x = 1",
            hypothesis_driven=True,
        )
        # Should not double-inject — the generic template has "HYPOTHESIS-N"
        # but since config already contains "HYPOTHESIS", it should skip injection
        count = result["system"].count("HYPOTHESIS-N")
        self.assertEqual(count, 0)  # template NOT appended


if __name__ == "__main__":
    unittest.main()
