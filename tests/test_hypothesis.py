# tests/test_hypothesis.py
"""Tests for the core hypothesis module."""
import json
import tempfile
import unittest
from pathlib import Path

from openevolve.hypothesis import (
    extract_hypothesis_comment_block,
    rescue_hypotheses,
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


class TestExtractHypothesisCommentBlock(unittest.TestCase):
    """Test extracting hypothesis comment lines from LLM responses."""

    def test_extract_python_comments(self):
        text = (
            "Here is my improved code:\n"
            "# HYPOTHESIS-1: Simulated annealing improves distance_score\n"
            "# MECHANISM-1: Cooling schedule helps escape local minima\n"
            "# EXPECT-1: distance_score > 0.8\n"
            "\nimport numpy as np\n"
        )
        lines = extract_hypothesis_comment_block(text)
        self.assertEqual(len(lines), 3)
        self.assertIn("HYPOTHESIS-1", lines[0])
        self.assertIn("MECHANISM-1", lines[1])
        self.assertIn("EXPECT-1", lines[2])

    def test_extract_go_comments(self):
        text = (
            "// HYPOTHESIS-1: Cache affinity reduces latency\n"
            "// MECHANISM-1: Prefix reuse avoids recomputation\n"
            "// EXPECT-1: avg_e2e_ms < 5000\n"
        )
        lines = extract_hypothesis_comment_block(text)
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("//"))

    def test_extract_multiline_mechanism(self):
        text = (
            "# HYPOTHESIS-1: Better search\n"
            "# MECHANISM-1: First line of mechanism\n"
            "#   continuation line one\n"
            "#   continuation line two\n"
            "# EXPECT-1: metric > 0.5\n"
        )
        lines = extract_hypothesis_comment_block(text)
        self.assertEqual(len(lines), 5)
        self.assertIn("continuation line one", lines[2])
        self.assertIn("continuation line two", lines[3])

    def test_extract_multiple_hypotheses(self):
        text = (
            "# HYPOTHESIS-1: First claim\n"
            "# MECHANISM-1: First mechanism\n"
            "# EXPECT-1: metric_a > 0.5\n"
            "# HYPOTHESIS-2: Second claim\n"
            "# MECHANISM-2: Second mechanism\n"
            "# EXPECT-2: metric_b < 10.0\n"
        )
        lines = extract_hypothesis_comment_block(text)
        self.assertEqual(len(lines), 6)

    def test_extract_empty_when_none(self):
        text = "Just some code without hypotheses\nx = 1\n"
        lines = extract_hypothesis_comment_block(text)
        self.assertEqual(len(lines), 0)

    def test_extract_from_gemini_style_response(self):
        """Reproduce the real Gemini pattern: hypotheses as preamble before diffs."""
        text = (
            "# EVOLVE-BLOCK-START\n"
            "# HYPOTHESIS-1: SA with local exploitation improves value_score\n"
            "# MECHANISM-1: Combining exploration with Gaussian perturbations\n"
            "#   allows escaping local minima\n"
            "# EXPECT-1: combined_score > 1.3\n"
            "\nimport numpy as np\n\n"
            "<<<<<<< SEARCH\n"
            "def search_algorithm():\n"
            "    pass\n"
            "=======\n"
            "def search_algorithm():\n"
            "    return 42\n"
            ">>>>>>> REPLACE\n"
        )
        lines = extract_hypothesis_comment_block(text)
        self.assertEqual(len(lines), 4)  # H1, M1 + continuation, E1
        self.assertIn("HYPOTHESIS-1", lines[0])


class TestRescueHypotheses(unittest.TestCase):
    """Test rescuing hypotheses from LLM response into evolved code."""

    def test_noop_when_code_already_has_hypotheses(self):
        """Claude path: hypotheses already in REPLACE block, no rescue needed."""
        code = (
            "# EVOLVE-BLOCK-START\n"
            "# HYPOTHESIS-1: Good search\n"
            "# MECHANISM-1: Better algorithm\n"
            "# EXPECT-1: score > 0.8\n"
            "def search(): pass\n"
            "# EVOLVE-BLOCK-END\n"
        )
        llm_response = "# HYPOTHESIS-1: Good search\n# MECHANISM-1: Better\n# EXPECT-1: score > 0.8\n"
        result = rescue_hypotheses(code, llm_response)
        self.assertEqual(result, code)

    def test_noop_when_no_hypotheses_in_response(self):
        code = "# EVOLVE-BLOCK-START\ndef f(): pass\n# EVOLVE-BLOCK-END\n"
        llm_response = "Just some code changes"
        result = rescue_hypotheses(code, llm_response)
        self.assertEqual(result, code)

    def test_inject_python_hypotheses(self):
        """Gemini path: hypotheses in response preamble, missing from code."""
        code = (
            "# EVOLVE-BLOCK-START\n"
            "import numpy as np\n"
            "def search(): pass\n"
            "# EVOLVE-BLOCK-END\n"
        )
        llm_response = (
            "# HYPOTHESIS-1: SA improves distance_score\n"
            "# MECHANISM-1: Cooling schedule escapes local minima\n"
            "# EXPECT-1: distance_score > 0.8\n"
            "\n<<<<<<< SEARCH\ndef search(): pass\n=======\ndef search(): return 42\n>>>>>>> REPLACE\n"
        )
        result = rescue_hypotheses(code, llm_response)
        self.assertIn("HYPOTHESIS-1", result)
        self.assertIn("MECHANISM-1", result)
        self.assertIn("EXPECT-1", result)
        # Hypotheses should appear after EVOLVE-BLOCK-START
        lines = result.split("\n")
        start_idx = next(i for i, l in enumerate(lines) if "EVOLVE-BLOCK-START" in l)
        self.assertIn("HYPOTHESIS-1", lines[start_idx + 1])

    def test_inject_go_hypotheses_with_tab_indent(self):
        """Go code with tab indentation should preserve indent."""
        code = (
            '\tGO_CODE = """\n'
            "\t// EVOLVE-BLOCK-START\n"
            "\tinputLen := len(req.InputTokens)\n"
            "\t// EVOLVE-BLOCK-END\n"
            '"""'
        )
        llm_response = (
            "// HYPOTHESIS-1: Weight tuning reduces latency\n"
            "// MECHANISM-1: Adaptive weights match request characteristics\n"
            "// EXPECT-1: avg_e2e_ms < 3000\n"
            "\n<<<<<<< SEARCH\ninputLen := len(req.InputTokens)\n"
            "=======\ninputLen := len(req.InputTokens)\nw0 := 0.5\n>>>>>>> REPLACE\n"
        )
        result = rescue_hypotheses(code, llm_response)
        self.assertIn("HYPOTHESIS-1", result)
        # Verify tab indentation was applied
        lines = result.split("\n")
        hyp_line = next(l for l in lines if "HYPOTHESIS-1" in l)
        self.assertTrue(hyp_line.startswith("\t"))

    def test_inject_multiline_mechanism(self):
        code = "# EVOLVE-BLOCK-START\ndef f(): pass\n# EVOLVE-BLOCK-END\n"
        llm_response = (
            "# HYPOTHESIS-1: Better approach\n"
            "# MECHANISM-1: First line\n"
            "#   continuation line\n"
            "# EXPECT-1: score > 0.9\n"
        )
        result = rescue_hypotheses(code, llm_response)
        self.assertIn("HYPOTHESIS-1", result)
        self.assertIn("continuation line", result)

    def test_noop_when_no_evolve_block(self):
        code = "def f(): pass\n"
        llm_response = "# HYPOTHESIS-1: Claim\n# MECHANISM-1: Mech\n# EXPECT-1: x > 1\n"
        result = rescue_hypotheses(code, llm_response)
        self.assertEqual(result, code)

    def test_parse_hypotheses_works_after_rescue(self):
        """End-to-end: rescued hypotheses should be parseable."""
        code = "# EVOLVE-BLOCK-START\ndef f(): pass\n# EVOLVE-BLOCK-END\n"
        llm_response = (
            "# HYPOTHESIS-1: Improves combined_score\n"
            "# MECHANISM-1: Better algorithm\n"
            "# EXPECT-1: combined_score > 1.3\n"
        )
        rescued = rescue_hypotheses(code, llm_response)
        parsed = parse_hypotheses(rescued, valid_metrics={"combined_score"})
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["metric"], "combined_score")
        self.assertEqual(parsed[0]["operator"], ">")
        self.assertAlmostEqual(parsed[0]["threshold"], 1.3)


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


class TestInjectResultComments(unittest.TestCase):
    """Test injecting RESULT-N lines into code after evaluation."""

    def test_inject_python_results(self):
        from openevolve.hypothesis import inject_result_comments
        code = (
            "# EVOLVE-BLOCK-START\n"
            "# HYPOTHESIS-1: Better search improves score\n"
            "# MECHANISM-1: Multi-start covers more basins\n"
            "# EXPECT-1: combined_score > 0.8\n"
            "def solve(): pass\n"
            "# EVOLVE-BLOCK-END\n"
        )
        metrics = {"combined_score": 0.9, "distance_score": 0.7}
        result = inject_result_comments(code, metrics)
        self.assertIn("RESULT-1: CONFIRMED", result)
        self.assertIn("actual=0.9", result)
        # RESULT should appear right after EXPECT
        lines = result.splitlines()
        expect_idx = next(i for i, l in enumerate(lines) if "EXPECT-1" in l)
        self.assertIn("RESULT-1", lines[expect_idx + 1])

    def test_inject_go_results(self):
        from openevolve.hypothesis import inject_result_comments
        code = (
            "// EVOLVE-BLOCK-START\n"
            "// HYPOTHESIS-1: Cache affinity reduces latency\n"
            "// MECHANISM-1: Prefix reuse avoids recomputation\n"
            "// EXPECT-1: avg_e2e_ms < 5000\n"
            "func route() {}\n"
            "// EVOLVE-BLOCK-END\n"
        )
        metrics = {"avg_e2e_ms": 4500.0}
        result = inject_result_comments(code, metrics)
        self.assertIn("// RESULT-1: CONFIRMED", result)

    def test_inject_refuted(self):
        from openevolve.hypothesis import inject_result_comments
        code = (
            "# HYPOTHESIS-1: Reduces latency\n"
            "# MECHANISM-1: Better routing\n"
            "# EXPECT-1: avg_e2e_ms < 3000\n"
            "x = 1\n"
        )
        metrics = {"avg_e2e_ms": 5000.0}
        result = inject_result_comments(code, metrics)
        self.assertIn("RESULT-1: REFUTED", result)
        self.assertIn("actual=5000.0", result)

    def test_inject_multiple_hypotheses(self):
        from openevolve.hypothesis import inject_result_comments
        code = (
            "# HYPOTHESIS-1: First claim\n"
            "# MECHANISM-1: First mechanism\n"
            "# EXPECT-1: metric_a > 0.5\n"
            "# HYPOTHESIS-2: Second claim\n"
            "# MECHANISM-2: Second mechanism\n"
            "# EXPECT-2: metric_b < 10.0\n"
            "x = 1\n"
        )
        metrics = {"metric_a": 0.8, "metric_b": 15.0}
        result = inject_result_comments(code, metrics)
        self.assertIn("RESULT-1: CONFIRMED", result)
        self.assertIn("RESULT-2: REFUTED", result)

    def test_noop_when_no_hypotheses(self):
        from openevolve.hypothesis import inject_result_comments
        code = "def solve(): pass\n"
        metrics = {"score": 0.5}
        result = inject_result_comments(code, metrics)
        self.assertEqual(result, code)

    def test_noop_when_results_already_present(self):
        from openevolve.hypothesis import inject_result_comments
        code = (
            "# HYPOTHESIS-1: Some claim\n"
            "# MECHANISM-1: Some mechanism\n"
            "# EXPECT-1: score > 0.5\n"
            "# RESULT-1: CONFIRMED (actual=0.8)\n"
            "x = 1\n"
        )
        metrics = {"score": 0.3}
        result = inject_result_comments(code, metrics)
        # Should NOT overwrite existing RESULT
        self.assertIn("RESULT-1: CONFIRMED (actual=0.8)", result)
        self.assertNotIn("REFUTED", result)

    def test_inconclusive_when_metric_missing(self):
        from openevolve.hypothesis import inject_result_comments
        code = (
            "# HYPOTHESIS-1: Claim\n"
            "# MECHANISM-1: Mechanism\n"
            "# EXPECT-1: nonexistent_metric < 10\n"
            "x = 1\n"
        )
        metrics = {"other_metric": 5.0}
        result = inject_result_comments(code, metrics)
        self.assertIn("RESULT-1: INCONCLUSIVE", result)

    def test_preserves_indentation(self):
        from openevolve.hypothesis import inject_result_comments
        code = (
            "\t// HYPOTHESIS-1: Claim\n"
            "\t// MECHANISM-1: Mechanism\n"
            "\t// EXPECT-1: score < 100\n"
            "\tfunc route() {}\n"
        )
        metrics = {"score": 80.0}
        result = inject_result_comments(code, metrics)
        lines = result.splitlines()
        result_line = next(l for l in lines if "RESULT-1" in l)
        self.assertTrue(result_line.startswith("\t"))


class TestV3InlineResultsPipeline(unittest.TestCase):
    """End-to-end test of V3: hypotheses + results live in code."""

    def test_full_pipeline_python(self):
        """Simulate: rescue → eval → inject → result visible in code."""
        from openevolve.hypothesis import inject_result_comments

        llm_response = (
            "# HYPOTHESIS-1: Multi-start search improves combined_score\n"
            "# MECHANISM-1: Random restarts escape local minima\n"
            "# EXPECT-1: combined_score > 0.8\n"
            "\n<<<<<<< SEARCH\ndef run_search(): pass\n=======\n"
            "def run_search(): return (-1.7, 0.68, -1.5)\n>>>>>>> REPLACE\n"
        )
        code_after_diff = (
            "# EVOLVE-BLOCK-START\n"
            "def run_search(): return (-1.7, 0.68, -1.5)\n"
            "# EVOLVE-BLOCK-END\n"
        )

        # Step 1: Rescue hypotheses into code
        rescued = rescue_hypotheses(code_after_diff, llm_response)
        self.assertIn("HYPOTHESIS-1", rescued)
        self.assertIn("EXPECT-1", rescued)

        # Step 2: Evaluate (simulated) — returns metrics
        actual_metrics = {"combined_score": 0.92, "distance_score": 0.85}

        # Step 3: Framework injects RESULT lines
        final_code = inject_result_comments(rescued, actual_metrics)

        # Verify RESULT is in the code
        self.assertIn("RESULT-1: CONFIRMED", final_code)
        self.assertIn("actual=0.92", final_code)

        # Step 4: When shown to next LLM, hypotheses are still parseable
        parsed = parse_hypotheses(final_code, valid_metrics={"combined_score", "distance_score"})
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["claim"], "Multi-start search improves combined_score")

    def test_full_pipeline_go(self):
        """Same flow with Go comment syntax."""
        from openevolve.hypothesis import inject_result_comments

        code = (
            "// EVOLVE-BLOCK-START\n"
            "// HYPOTHESIS-1: Cache affinity reduces latency\n"
            "// MECHANISM-1: Prefix reuse avoids recomputation\n"
            "// EXPECT-1: avg_e2e_ms < 5000\n"
            "func route(req Request) int { return 0 }\n"
            "// EVOLVE-BLOCK-END\n"
        )
        metrics = {"avg_e2e_ms": 4200.0, "avg_p95_ms": 5100.0}

        final_code = inject_result_comments(code, metrics)

        self.assertIn("// RESULT-1: CONFIRMED", final_code)
        self.assertIn("actual=4200.0", final_code)

        # Still parseable
        parsed = parse_hypotheses(final_code, valid_metrics={"avg_e2e_ms"})
        self.assertEqual(len(parsed), 1)

    def test_idempotent_injection(self):
        """Injecting twice should not double-stamp."""
        from openevolve.hypothesis import inject_result_comments

        code = (
            "# HYPOTHESIS-1: Claim\n"
            "# MECHANISM-1: Mechanism\n"
            "# EXPECT-1: score > 0.5\n"
            "x = 1\n"
        )
        metrics = {"score": 0.8}
        once = inject_result_comments(code, metrics)
        twice = inject_result_comments(once, metrics)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count("RESULT-1"), 1)


if __name__ == "__main__":
    unittest.main()
