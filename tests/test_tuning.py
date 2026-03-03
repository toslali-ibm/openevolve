# tests/test_tuning.py
"""Tests for structured threshold tuning v2."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from openevolve.config import Config, TuningConfig


class TestTuningConfig(unittest.TestCase):
    """Test TuningConfig dataclass and YAML loading."""

    def test_default_config(self):
        config = TuningConfig()
        self.assertFalse(config.enabled)
        self.assertEqual(config.max_params, 3)
        self.assertEqual(config.rescue_trials, 5)
        self.assertEqual(config.checkpoint_trials, 10)
        self.assertEqual(config.final_trials, 20)
        self.assertEqual(config.polish_top_k, 3)

    def test_config_from_dict(self):
        config = Config.from_dict(
            {"tuning": {"enabled": True, "rescue_trials": 8, "max_params": 2}}
        )
        self.assertTrue(config.tuning.enabled)
        self.assertEqual(config.tuning.rescue_trials, 8)
        self.assertEqual(config.tuning.max_params, 2)
        # Unset fields keep defaults
        self.assertEqual(config.tuning.checkpoint_trials, 10)
        self.assertEqual(config.tuning.final_trials, 20)

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

    def test_v1_backward_compat_budget_maps_to_rescue_trials(self):
        """v1 configs with 'budget' should map to rescue_trials."""
        config = Config.from_dict(
            {"tuning": {"enabled": True, "budget": 15, "budget_scale_per_param": 5}}
        )
        self.assertEqual(config.tuning.rescue_trials, 15)

    def test_v2_draft_backward_compat(self):
        """v2-draft configs with rescue_budget/polish_budget should map."""
        config = Config.from_dict(
            {
                "tuning": {
                    "enabled": True,
                    "rescue_budget": 7,
                    "polish_budget": 12,
                }
            }
        )
        self.assertEqual(config.tuning.rescue_trials, 7)
        self.assertEqual(config.tuning.checkpoint_trials, 12)


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


from openevolve.tuning import (
    has_tune_annotations,
    rewrite_tune_values,
    strip_tuned_annotations,
    extract_current_tune_values,
    strip_tuned_for_db,
)


class TestHasTuneAnnotations(unittest.TestCase):
    """Test the has_tune_annotations quick check."""

    def test_has_tune(self):
        code = "load = 0.4  # @TUNE [0.0, 1.0]\n"
        self.assertTrue(has_tune_annotations(code))

    def test_no_tune(self):
        code = "x = 42\ndef solve(): return x\n"
        self.assertFalse(has_tune_annotations(code))

    def test_tuned_only_no_tune(self):
        code = "load = 0.67  # @TUNED(was=0.4, gain=+0.12)\n"
        self.assertFalse(has_tune_annotations(code))


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


class TestExtractCurrentTuneValues(unittest.TestCase):
    """Test extracting current values from @TUNE lines."""

    def test_extract_float(self):
        code = "load = 0.67  # @TUNE [0.0, 1.0]\n"
        values = extract_current_tune_values(code)
        self.assertAlmostEqual(values["load"], 0.67)

    def test_extract_int(self):
        code = "batch = 64  # @TUNE [8, 128] int\n"
        values = extract_current_tune_values(code)
        self.assertEqual(values["batch"], 64)

    def test_extract_multiple(self):
        code = "load = 0.67  # @TUNE [0.0, 1.0]\n" "x = 42\n" "batch = 64  # @TUNE [8, 128] int\n"
        values = extract_current_tune_values(code)
        self.assertEqual(len(values), 2)
        self.assertAlmostEqual(values["load"], 0.67)
        self.assertEqual(values["batch"], 64)

    def test_empty_without_tune(self):
        code = "x = 42\ny = 3\n"
        values = extract_current_tune_values(code)
        self.assertEqual(len(values), 0)


class TestStripTunedForDb(unittest.TestCase):
    """Test strip_tuned_for_db() — the @TUNED firewall."""

    def test_strips_tuned_keeps_tune(self):
        """Sensitive param (gain >= threshold): strip @TUNED, keep @TUNE."""
        code = "load = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.12, best_impact=tp:+0.3)"
        result = strip_tuned_for_db(code)
        self.assertIn("@TUNE [0.0, 1.0]", result)
        self.assertNotIn("@TUNED", result)
        self.assertIn("load = 0.67", result)

    def test_strips_both_when_insensitive(self):
        """Insensitive param (gain < threshold): strip both @TUNE and @TUNED."""
        code = "load = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.005, best_impact=tp:+0.01)"
        result = strip_tuned_for_db(code, gain_threshold=0.01)
        self.assertNotIn("@TUNE", result)
        self.assertNotIn("@TUNED", result)
        self.assertIn("load = 0.67", result)

    def test_preserves_non_tuned_lines(self):
        code = "x = 42\nload = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.12)\ny = 3\n"
        result = strip_tuned_for_db(code)
        self.assertIn("x = 42", result)
        self.assertIn("y = 3", result)

    def test_noop_without_tuned(self):
        code = "load = 0.4  # @TUNE [0.0, 1.0]\n"
        result = strip_tuned_for_db(code)
        self.assertEqual(result, code)

    def test_negative_gain_below_threshold(self):
        """Negative gain with small absolute value should also strip @TUNE."""
        code = "load = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=-0.003)"
        result = strip_tuned_for_db(code, gain_threshold=0.01)
        self.assertNotIn("@TUNE", result)


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


class TestTuneProgram(unittest.TestCase):
    """Test the full tune_program() orchestration (v2)."""

    def test_tune_program_no_annotations_returns_unchanged(self):
        """Programs without @TUNE should pass through unchanged."""
        from openevolve.tuning import tune_program

        code = "x = 42\ndef solve(): return x\n"
        config = TuningConfig(enabled=True)

        async def mock_evaluate(program_code, program_id=""):
            return {"combined_score": 0.5}

        result_code, stats, metrics = asyncio.run(tune_program(code, mock_evaluate, config))
        self.assertEqual(result_code, code)
        self.assertFalse(stats.tuning_ran)
        self.assertIsNone(metrics)

    def test_tune_program_returns_metrics(self):
        """v2: tune_program should return best trial metrics."""
        from openevolve.tuning import tune_program

        code = "threshold = 0.1  # @TUNE [0.0, 1.0]\ndef solve(): pass\n"
        config = TuningConfig(enabled=True, rescue_trials=10)

        async def mock_evaluate(program_code, program_id=""):
            import re

            m = re.search(r"threshold\s*=\s*([0-9.]+)", program_code)
            val = float(m.group(1)) if m else 0.0
            score = 1.0 - abs(val - 0.7)
            return {"combined_score": score, "accuracy": score * 0.9}

        result_code, stats, metrics = asyncio.run(tune_program(code, mock_evaluate, config))
        self.assertTrue(stats.tuning_ran)
        self.assertIsNotNone(metrics)
        self.assertIn("combined_score", metrics)

    def test_tune_program_respects_mode_budget(self):
        """Different modes should use different trial budgets."""
        from openevolve.tuning import tune_program

        code = "threshold = 0.5  # @TUNE [0.0, 1.0]\n"
        config = TuningConfig(enabled=True, rescue_trials=3, checkpoint_trials=7, final_trials=15)

        trial_counts = {}

        async def counting_evaluate(program_code, program_id=""):
            mode = counting_evaluate.current_mode
            trial_counts.setdefault(mode, 0)
            trial_counts[mode] += 1
            return {"combined_score": 0.5}

        for mode in ["rescue", "checkpoint", "final"]:
            counting_evaluate.current_mode = mode
            trial_counts[mode] = 0
            asyncio.run(tune_program(code, counting_evaluate, config, mode=mode))

        # Each mode should have different trial counts
        # rescue: 1 baseline + 3 trials = 4 calls
        # checkpoint: 1 baseline + 7 trials = 8 calls
        # final: 1 baseline + 15 trials = 16 calls
        self.assertLess(trial_counts["rescue"], trial_counts["checkpoint"])
        self.assertLess(trial_counts["checkpoint"], trial_counts["final"])

    def test_tune_program_baseline_metrics_reuse(self):
        """v2: pre-computed baseline_metrics should skip redundant baseline eval."""
        from openevolve.tuning import tune_program

        code = "threshold = 0.5  # @TUNE [0.0, 1.0]\n"
        config = TuningConfig(enabled=True, rescue_trials=3)

        eval_count = 0

        async def counting_evaluate(program_code, program_id=""):
            nonlocal eval_count
            eval_count += 1
            return {"combined_score": 0.5}

        # With baseline_metrics, should skip baseline eval
        baseline = {"combined_score": 0.5}
        eval_count = 0
        asyncio.run(tune_program(code, counting_evaluate, config, baseline_metrics=baseline))
        count_with_baseline = eval_count

        # Without baseline_metrics, should do baseline eval
        eval_count = 0
        asyncio.run(tune_program(code, counting_evaluate, config))
        count_without_baseline = eval_count

        # With baseline should have one fewer eval call
        self.assertEqual(count_with_baseline + 1, count_without_baseline)

    def test_tune_program_warm_hint(self):
        """v2: warm hint should seed Optuna with current @TUNE values."""
        from openevolve.tuning import tune_program

        # Current value is 0.7 (close to optimal)
        code = "threshold = 0.7  # @TUNE [0.0, 1.0]\n"
        config = TuningConfig(enabled=True, rescue_trials=5)

        async def mock_evaluate(program_code, program_id=""):
            import re

            m = re.search(r"threshold\s*=\s*([0-9.]+)", program_code)
            val = float(m.group(1)) if m else 0.0
            return {"combined_score": 1.0 - abs(val - 0.7)}

        _, stats, _ = asyncio.run(tune_program(code, mock_evaluate, config))
        self.assertTrue(stats.warm_hint_used)

    def test_tune_program_strips_tuned_for_db(self):
        """v2: result should NOT contain @TUNED annotations."""
        from openevolve.tuning import tune_program

        code = "threshold = 0.1  # @TUNE [0.0, 1.0]\n"
        config = TuningConfig(enabled=True, rescue_trials=10)

        async def mock_evaluate(program_code, program_id=""):
            import re

            m = re.search(r"threshold\s*=\s*([0-9.]+)", program_code)
            val = float(m.group(1)) if m else 0.0
            return {"combined_score": 1.0 - abs(val - 0.7)}

        result_code, stats, _ = asyncio.run(tune_program(code, mock_evaluate, config))
        # @TUNED should be stripped for DB storage
        self.assertNotIn("@TUNED", result_code)
        # But @TUNE should remain (if gain was significant)
        if stats.gain and abs(stats.gain) >= 0.01:
            self.assertIn("@TUNE", result_code)

    def test_tune_program_fallback_on_failure(self):
        """If all trials fail, return original code."""
        from openevolve.tuning import tune_program

        code = "threshold = 0.5  # @TUNE [0.0, 1.0]\n"
        config = TuningConfig(enabled=True, rescue_trials=3)

        async def failing_evaluate(program_code, program_id=""):
            raise RuntimeError("Evaluator crashed")

        result_code, stats, metrics = asyncio.run(tune_program(code, failing_evaluate, config))
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
        config = TuningConfig(enabled=True, rescue_trials=5, max_params=2)

        async def mock_evaluate(program_code, program_id=""):
            return {"combined_score": 0.5}

        result_code, stats, _ = asyncio.run(tune_program(code, mock_evaluate, config))
        self.assertEqual(stats.tune_annotations_found, 4)
        self.assertEqual(stats.tune_annotations_honored, 2)


class TestIterationTuningStats(unittest.TestCase):
    """Test per-iteration tuning stats dataclass (v2)."""

    def test_default_values(self):
        from openevolve.tuning import IterationTuningStats

        stats = IterationTuningStats(iteration=5)
        self.assertEqual(stats.iteration, 5)
        self.assertEqual(stats.mode, "")
        self.assertEqual(stats.tune_annotations_found, 0)
        self.assertFalse(stats.tuning_ran)
        self.assertFalse(stats.warm_hint_used)
        self.assertEqual(stats.selection_reason, "")
        self.assertEqual(stats.annotations_stripped, 0)

    def test_v2_fields(self):
        from openevolve.tuning import IterationTuningStats

        stats = IterationTuningStats(
            iteration=10,
            mode="rescue",
            tuning_ran=True,
            warm_hint_used=True,
            selection_reason="novel_low_score",
            annotations_stripped=1,
        )
        self.assertEqual(stats.mode, "rescue")
        self.assertTrue(stats.warm_hint_used)
        self.assertEqual(stats.selection_reason, "novel_low_score")


class TestTuningTracker(unittest.TestCase):
    """Test cross-iteration tuning tracker (v2)."""

    def test_record_and_summary(self):
        from openevolve.tuning import IterationTuningStats, TuningTracker

        tracker = TuningTracker()
        stats1 = IterationTuningStats(
            iteration=1,
            mode="rescue",
            tune_annotations_found=2,
            tune_annotations_honored=2,
            tuning_ran=True,
            tuning_duration_s=10.0,
            original_score=0.5,
            tuned_score=0.6,
            gain=0.1,
            trials_completed=5,
            trials_failed=0,
            warm_hint_used=True,
            selection_reason="novel_low_score",
        )
        stats2 = IterationTuningStats(
            iteration=2,
            mode="skipped",
            tune_annotations_found=0,
        )
        tracker.record(stats1)
        tracker.record(stats2)
        summary = tracker.summary()
        self.assertEqual(summary["total_iterations_tracked"], 2)
        self.assertEqual(summary["total_iterations_with_tuning"], 1)
        self.assertEqual(summary["rescue_count"], 1)
        self.assertEqual(summary["skip_count"], 1)
        self.assertAlmostEqual(summary["avg_gain_when_tuned"], 0.1)
        self.assertAlmostEqual(summary["rescue_avg_gain"], 0.1)

    def test_tracker_counts_by_mode(self):
        from openevolve.tuning import IterationTuningStats, TuningTracker

        tracker = TuningTracker()
        for mode in ["rescue", "rescue", "checkpoint", "final"]:
            stats = IterationTuningStats(
                iteration=1,
                mode=mode,
                tuning_ran=True,
                tuning_duration_s=1.0,
                original_score=0.5,
                tuned_score=0.55,
                gain=0.05,
                trials_completed=5,
            )
            tracker.record(stats)
        summary = tracker.summary()
        self.assertEqual(summary["rescue_count"], 2)
        self.assertEqual(summary["checkpoint_polish_count"], 1)
        self.assertEqual(summary["final_polish_count"], 1)

    def test_save_load(self):
        from openevolve.tuning import IterationTuningStats, TuningTracker

        tracker = TuningTracker()
        stats = IterationTuningStats(
            iteration=1,
            mode="rescue",
            tuning_ran=True,
            tuning_duration_s=5.0,
            original_score=0.5,
            tuned_score=0.55,
            gain=0.05,
            trials_completed=5,
            trials_failed=0,
        )
        tracker.record(stats)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tuning_tracker.json"
            tracker.save(path)
            self.assertTrue(path.exists())
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["total_iterations_tracked"], 1)
            self.assertEqual(data["rescue_count"], 1)


class TestTuningPromptInjection(unittest.TestCase):
    """Test that tuning instructions are injected into prompts (v2 prompt)."""

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
        # v2: @TUNED should NOT be in the prompt
        self.assertNotIn("@TUNED", result["system"])

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

    def test_v2_prompt_is_minimal(self):
        """v2 prompt should be short — 4 content lines, no @TUNED mentions."""
        from openevolve.prompt.templates import THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE

        lines = [l for l in THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE.strip().split("\n") if l.strip()]
        # Should be very short (header + 4 content lines)
        self.assertLessEqual(len(lines), 6)
        self.assertNotIn("@TUNED", THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE)
        self.assertIn("algorithms", THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE)


class TestDiversityAgainstSet(unittest.TestCase):
    """Test the static diversity computation used for rescue selection."""

    def test_diversity_against_set(self):
        from openevolve.database import ProgramDatabase

        snapshot = {
            "programs": {
                "p1": {"code": "def solve(): return 1\n", "metrics": {"combined_score": 0.5}},
                "p2": {"code": "def solve(): return 2\n", "metrics": {"combined_score": 0.6}},
                "p3": {
                    "code": "def solve():\n  x = 1\n  return x * 2\n",
                    "metrics": {"combined_score": 0.7},
                },
            }
        }
        # Very different code should have high diversity
        very_different = "import os\nimport sys\nclass BigSolver:\n  pass\n" * 5
        div_high = ProgramDatabase.fast_code_diversity_against_set(very_different, snapshot)

        # Similar code should have low diversity
        similar = "def solve(): return 1\n"
        div_low = ProgramDatabase.fast_code_diversity_against_set(similar, snapshot)

        self.assertGreater(div_high, div_low)

    def test_diversity_empty_snapshot(self):
        from openevolve.database import ProgramDatabase

        snapshot = {"programs": {}}
        div = ProgramDatabase.fast_code_diversity_against_set("some code", snapshot)
        self.assertEqual(div, 0.0)


class TestIterationIntegration(unittest.TestCase):
    """Test that tune_program is callable from iteration context."""

    def test_tuning_import(self):
        from openevolve.tuning import tune_program, parse_tune_annotations, has_tune_annotations

        self.assertTrue(callable(tune_program))
        self.assertTrue(callable(parse_tune_annotations))
        self.assertTrue(callable(has_tune_annotations))


if __name__ == "__main__":
    unittest.main()
