# tests/test_tuning.py
"""Tests for structured threshold tuning."""

import unittest

from openevolve.config import Config, TuningConfig


class TestTuningConfig(unittest.TestCase):
    """Test TuningConfig dataclass and YAML loading."""

    def test_default_config(self):
        config = TuningConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.budget, 20)
        self.assertEqual(config.max_params, 3)
        self.assertEqual(config.budget_scale_per_param, 5)

    def test_config_from_dict(self):
        config = Config.from_dict({"tuning": {"enabled": True, "budget": 10, "max_params": 2}})
        self.assertTrue(config.tuning.enabled)
        self.assertEqual(config.tuning.budget, 10)
        self.assertEqual(config.tuning.max_params, 2)
        # Unset fields keep defaults
        self.assertEqual(config.tuning.budget_scale_per_param, 5)

    def test_config_default_tuning_disabled(self):
        config = Config()
        self.assertFalse(config.tuning.enabled)

    def test_tuning_independent_of_hypothesis(self):
        config = Config.from_dict(
            {
                "hypothesis_driven": False,
                "tuning": {"enabled": True},
            }
        )
        self.assertFalse(config.hypothesis_driven)
        self.assertTrue(config.tuning.enabled)


from openevolve.tuning import parse_tune_annotations, TuneParam


class TestParseTuneAnnotations(unittest.TestCase):
    """Test parsing @TUNE annotations from code."""

    def test_parse_float_range(self):
        code = "load_cutoff = 0.4  # @TUNE [0.0, 1.0]"
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 1)
        p = params[0]
        self.assertEqual(p.name, "load_cutoff")
        self.assertAlmostEqual(p.value, 0.4)
        self.assertAlmostEqual(p.low, 0.0)
        self.assertAlmostEqual(p.high, 1.0)
        self.assertEqual(p.param_type, "float")

    def test_parse_int_range(self):
        code = "batch_size = 32  # @TUNE [8, 128] int"
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].param_type, "int")
        self.assertEqual(params[0].low, 8)
        self.assertEqual(params[0].high, 128)

    def test_parse_explicit_float(self):
        code = "decay = 0.01  # @TUNE [0.001, 0.1] float"
        params = parse_tune_annotations(code)
        self.assertEqual(params[0].param_type, "float")

    def test_parse_multiple(self):
        code = (
            "load_cutoff = 0.4  # @TUNE [0.0, 1.0]\n"
            "batch_size = 32  # @TUNE [8, 128] int\n"
            "decay = 0.01  # @TUNE [0.001, 0.1] float\n"
        )
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 3)

    def test_ignores_categorical(self):
        code = 'strategy = "greedy"  # @TUNE {greedy, round_robin, weighted}'
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 0)

    def test_max_params_enforced(self):
        code = (
            "a = 1  # @TUNE [0, 10] int\n"
            "b = 2  # @TUNE [0, 10] int\n"
            "c = 3  # @TUNE [0, 10] int\n"
            "d = 4  # @TUNE [0, 10] int\n"
        )
        params = parse_tune_annotations(code, max_params=3)
        self.assertEqual(len(params), 3)
        self.assertEqual(params[-1].name, "c")

    def test_no_tune_returns_empty(self):
        code = 'x = 42\ny = "hello"\n'
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 0)

    def test_ignores_non_assignment_lines(self):
        code = "if x < 0.5:  # @TUNE [0.0, 1.0]\n    pass"
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 0)

    def test_preserves_line_number(self):
        code = "x = 1\nload = 0.4  # @TUNE [0.0, 1.0]\ny = 2\n"
        params = parse_tune_annotations(code)
        self.assertEqual(params[0].line_number, 1)  # 0-indexed


from openevolve.tuning import rewrite_tune_values, strip_tuned_annotations


class TestStripTunedAnnotations(unittest.TestCase):
    """Test stripping @TUNED(...) from code."""

    def test_strip_tuned(self):
        code = "load = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.12, best_impact=tp:+0.3)"
        result = strip_tuned_annotations(code)
        self.assertIn("@TUNE [0.0, 1.0]", result)
        self.assertNotIn("@TUNED", result)

    def test_strip_preserves_non_tuned_lines(self):
        code = "x = 42\nload = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.1)\ny = 3\n"
        result = strip_tuned_annotations(code)
        self.assertIn("x = 42", result)
        self.assertIn("y = 3", result)

    def test_noop_without_tuned(self):
        code = "load = 0.4  # @TUNE [0.0, 1.0]\n"
        result = strip_tuned_annotations(code)
        self.assertEqual(result, code)


class TestRewriteTuneValues(unittest.TestCase):
    """Test rewriting threshold values and adding @TUNED annotations."""

    def test_rewrite_float(self):
        code = "load = 0.4  # @TUNE [0.0, 1.0]\n"
        params = parse_tune_annotations(code)
        new_values = {"load": 0.67}
        original_score = 0.5
        best_score = 0.62
        best_metrics = {"throughput": 1.3}
        original_metrics = {"throughput": 1.0}
        result = rewrite_tune_values(
            code,
            params,
            new_values,
            original_score,
            best_score,
            original_metrics,
            best_metrics,
        )
        self.assertIn("load = 0.67", result)
        self.assertIn("@TUNED(was=0.4", result)
        self.assertIn("gain=+0.12", result)

    def test_rewrite_int(self):
        code = "batch = 32  # @TUNE [8, 128] int\n"
        params = parse_tune_annotations(code)
        new_values = {"batch": 64}
        result = rewrite_tune_values(
            code,
            params,
            new_values,
            0.5,
            0.6,
            {"x": 1.0},
            {"x": 1.5},
        )
        self.assertIn("batch = 64", result)

    def test_non_tune_lines_unchanged(self):
        code = "x = 42\nload = 0.4  # @TUNE [0.0, 1.0]\ny = 3\n"
        params = parse_tune_annotations(code)
        new_values = {"load": 0.67}
        result = rewrite_tune_values(
            code,
            params,
            new_values,
            0.5,
            0.6,
            {"tp": 1.0},
            {"tp": 1.3},
        )
        self.assertIn("x = 42", result)
        self.assertIn("y = 3", result)


import asyncio
import json
import tempfile
from pathlib import Path


class TestTuneProgram(unittest.TestCase):
    """Test the full tune_program() orchestration."""

    def test_tune_program_no_annotations_returns_unchanged(self):
        """Programs without @TUNE should pass through unchanged."""
        from openevolve.tuning import tune_program

        code = "x = 42\ndef solve(): return x\n"
        config = TuningConfig(enabled=True, budget=5)

        async def mock_evaluate(program_code, program_id=""):
            return {"combined_score": 0.5}

        result_code, stats = asyncio.run(tune_program(code, mock_evaluate, config))
        self.assertEqual(result_code, code)
        self.assertFalse(stats.tuning_ran)

    def test_tune_program_optimizes_float(self):
        """Should find a better value for a tunable float."""
        from openevolve.tuning import tune_program

        # The evaluator rewards values close to 0.7
        code = "threshold = 0.1  # @TUNE [0.0, 1.0]\ndef solve(): pass\n"
        config = TuningConfig(enabled=True, budget=20)

        async def mock_evaluate(program_code, program_id=""):
            import re

            m = re.search(r"threshold\s*=\s*([0-9.]+)", program_code)
            val = float(m.group(1)) if m else 0.0
            # Score peaks at 0.7
            score = 1.0 - abs(val - 0.7)
            return {"combined_score": score}

        result_code, stats = asyncio.run(tune_program(code, mock_evaluate, config))
        self.assertIn("@TUNED", result_code)
        self.assertIn("was=0.1", result_code)
        self.assertTrue(stats.tuning_ran)
        self.assertGreater(stats.trials_completed, 0)

    def test_tune_program_fallback_on_failure(self):
        """If all trials fail, return original code."""
        from openevolve.tuning import tune_program

        code = "threshold = 0.5  # @TUNE [0.0, 1.0]\n"
        config = TuningConfig(enabled=True, budget=3)

        async def failing_evaluate(program_code, program_id=""):
            raise RuntimeError("Evaluator crashed")

        result_code, stats = asyncio.run(tune_program(code, failing_evaluate, config))
        # Baseline also fails, so should return original code
        self.assertNotIn("@TUNED", result_code)
        self.assertIn("threshold = 0.5", result_code)

    def test_tune_program_respects_max_params(self):
        """Only first max_params annotations should be tuned."""
        from openevolve.tuning import tune_program

        code = (
            "a = 1  # @TUNE [0, 10] int\n"
            "b = 2  # @TUNE [0, 10] int\n"
            "c = 3  # @TUNE [0, 10] int\n"
            "d = 4  # @TUNE [0, 10] int\n"
        )
        config = TuningConfig(enabled=True, budget=5, max_params=2)

        async def mock_evaluate(program_code, program_id=""):
            return {"combined_score": 0.5}

        result_code, stats = asyncio.run(tune_program(code, mock_evaluate, config))
        # a and b should have @TUNED, c and d should not
        lines = result_code.split("\n")
        tuned_lines = [l for l in lines if "@TUNED" in l]
        self.assertEqual(len(tuned_lines), 2)
        self.assertEqual(stats.tune_annotations_found, 4)
        self.assertEqual(stats.tune_annotations_honored, 2)


class TestIterationTuningStats(unittest.TestCase):
    """Test per-iteration tuning stats dataclass."""

    def test_default_values(self):
        from openevolve.tuning import IterationTuningStats

        stats = IterationTuningStats(iteration=5)
        self.assertEqual(stats.iteration, 5)
        self.assertEqual(stats.tune_annotations_found, 0)
        self.assertEqual(stats.tune_annotations_honored, 0)
        self.assertFalse(stats.tuning_ran)
        self.assertIsNone(stats.tuning_duration_s)
        self.assertIsNone(stats.original_score)
        self.assertIsNone(stats.tuned_score)
        self.assertIsNone(stats.gain)
        self.assertEqual(stats.trials_completed, 0)
        self.assertEqual(stats.trials_failed, 0)
        self.assertEqual(stats.param_changes, {})

    def test_stats_with_values(self):
        from openevolve.tuning import IterationTuningStats

        stats = IterationTuningStats(
            iteration=10,
            tune_annotations_found=4,
            tune_annotations_honored=3,
            tuning_ran=True,
            tuning_duration_s=12.5,
            original_score=0.5,
            tuned_score=0.62,
            gain=0.12,
            trials_completed=25,
            trials_failed=2,
            param_changes={
                "load": {"was": 0.4, "now": 0.67},
                "batch": {"was": 32, "now": 64},
            },
        )
        self.assertTrue(stats.tuning_ran)
        self.assertAlmostEqual(stats.gain, 0.12)
        self.assertEqual(len(stats.param_changes), 2)


class TestTuningTracker(unittest.TestCase):
    """Test cross-iteration tuning tracker."""

    def test_record_and_summary(self):
        from openevolve.tuning import IterationTuningStats, TuningTracker

        tracker = TuningTracker()
        stats1 = IterationTuningStats(
            iteration=1,
            tune_annotations_found=2,
            tune_annotations_honored=2,
            tuning_ran=True,
            tuning_duration_s=10.0,
            original_score=0.5,
            tuned_score=0.6,
            gain=0.1,
            trials_completed=25,
            trials_failed=0,
            param_changes={"x": {"was": 0.1, "now": 0.5}},
        )
        stats2 = IterationTuningStats(
            iteration=2,
            tune_annotations_found=0,
            tune_annotations_honored=0,
            tuning_ran=False,
        )
        tracker.record(stats1)
        tracker.record(stats2)
        summary = tracker.summary()
        self.assertEqual(summary["total_iterations_tracked"], 2)
        self.assertEqual(summary["total_iterations_with_tuning"], 1)
        self.assertAlmostEqual(summary["avg_gain_when_tuned"], 0.1)
        self.assertAlmostEqual(summary["avg_tuning_duration_s"], 10.0)

    def test_save_load(self):
        from openevolve.tuning import IterationTuningStats, TuningTracker

        tracker = TuningTracker()
        stats = IterationTuningStats(
            iteration=1,
            tuning_ran=True,
            tuning_duration_s=5.0,
            original_score=0.5,
            tuned_score=0.55,
            gain=0.05,
            trials_completed=20,
            trials_failed=1,
        )
        tracker.record(stats)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tuning_tracker.json"
            tracker.save(path)
            self.assertTrue(path.exists())
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["total_iterations_tracked"], 1)


class TestTuningPromptInjection(unittest.TestCase):
    """Test that tuning instructions are injected into prompts."""

    def test_tuning_enabled_appends_template(self):
        from openevolve.config import PromptConfig
        from openevolve.prompt.sampler import PromptSampler

        config = PromptConfig()
        config.system_message = "You are a helpful assistant."
        sampler = PromptSampler(config)
        result = sampler.build_prompt(
            current_program="x = 1",
            tuning_enabled=True,
        )
        self.assertIn("@TUNE", result["system"])
        self.assertIn("@TUNED", result["system"])

    def test_tuning_disabled_no_template(self):
        from openevolve.config import PromptConfig
        from openevolve.prompt.sampler import PromptSampler

        config = PromptConfig()
        config.system_message = "You are a helpful assistant."
        sampler = PromptSampler(config)
        result = sampler.build_prompt(
            current_program="x = 1",
            tuning_enabled=False,
        )
        self.assertNotIn("@TUNE", result["system"])

    def test_tuning_and_hypothesis_coexist(self):
        from openevolve.config import PromptConfig
        from openevolve.prompt.sampler import PromptSampler

        config = PromptConfig()
        config.system_message = "You are a helpful assistant."
        sampler = PromptSampler(config)
        result = sampler.build_prompt(
            current_program="x = 1",
            hypothesis_driven=True,
            tuning_enabled=True,
        )
        self.assertIn("HYPOTHESIS-N", result["system"])
        self.assertIn("@TUNE", result["system"])


class TestIterationIntegration(unittest.TestCase):
    """Test that tune_program is callable from iteration context."""

    def test_tuning_import(self):
        from openevolve.tuning import tune_program, parse_tune_annotations

        self.assertTrue(callable(tune_program))
        self.assertTrue(callable(parse_tune_annotations))


if __name__ == "__main__":
    unittest.main()
