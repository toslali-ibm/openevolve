# Structured Threshold Tuning — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the `@TUNE` / `@TUNED` annotation system so OpenEvolve can automatically optimize thresholds in LLM-generated code using Optuna before scoring.

**Architecture:** New `openevolve/tuning.py` module handles parsing, Optuna optimization, and code rewriting. Config gets a `TuningConfig` dataclass. Prompt sampler appends tuning instructions. Iteration flow inserts tuning between code generation and evaluation.

**Tech Stack:** Python 3.10+, Optuna (TPE sampler), unittest, openevolve framework

**Design doc:** `docs/plans/2026-03-02-structured-threshold-tuning-design.md`

---

### Task 1: Add `TuningConfig` to config

**Files:**
- Modify: `openevolve/config.py:367-414`
- Test: `tests/test_tuning.py` (new)

**Step 1: Write the failing test**

Create `tests/test_tuning.py`:

```python
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
        config = Config.from_dict({
            "tuning": {"enabled": True, "budget": 10, "max_params": 2}
        })
        self.assertTrue(config.tuning.enabled)
        self.assertEqual(config.tuning.budget, 10)
        self.assertEqual(config.tuning.max_params, 2)
        # Unset fields keep defaults
        self.assertEqual(config.tuning.budget_scale_per_param, 5)

    def test_config_default_tuning_disabled(self):
        config = Config()
        self.assertFalse(config.tuning.enabled)

    def test_tuning_independent_of_hypothesis(self):
        config = Config.from_dict({
            "hypothesis_driven": False,
            "tuning": {"enabled": True},
        })
        self.assertFalse(config.hypothesis_driven)
        self.assertTrue(config.tuning.enabled)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tuning.py -v`
Expected: FAIL — `TuningConfig` does not exist

**Step 3: Write minimal implementation**

In `openevolve/config.py`, add before `class Config` (after `EvolutionTraceConfig`):

```python
@dataclass
class TuningConfig:
    """Configuration for structured threshold tuning."""

    enabled: bool = False
    budget: int = 20
    max_params: int = 3
    budget_scale_per_param: int = 5
```

In `class Config`, add after the `evolution_trace` field:

```python
    tuning: TuningConfig = field(default_factory=TuningConfig)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tuning.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add openevolve/config.py tests/test_tuning.py
git commit -m "feat(tuning): add TuningConfig dataclass"
```

---

### Task 2: Parse `@TUNE` annotations

**Files:**
- Create: `openevolve/tuning.py`
- Test: `tests/test_tuning.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_tuning.py`:

```python
from openevolve.tuning import parse_tune_annotations, TuneParam


class TestParseTuneAnnotations(unittest.TestCase):
    """Test parsing @TUNE annotations from code."""

    def test_parse_float_range(self):
        code = 'load_cutoff = 0.4  # @TUNE [0.0, 1.0]'
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 1)
        p = params[0]
        self.assertEqual(p.name, "load_cutoff")
        self.assertAlmostEqual(p.value, 0.4)
        self.assertAlmostEqual(p.low, 0.0)
        self.assertAlmostEqual(p.high, 1.0)
        self.assertEqual(p.param_type, "float")

    def test_parse_int_range(self):
        code = 'batch_size = 32  # @TUNE [8, 128] int'
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].param_type, "int")
        self.assertEqual(params[0].low, 8)
        self.assertEqual(params[0].high, 128)

    def test_parse_explicit_float(self):
        code = 'decay = 0.01  # @TUNE [0.001, 0.1] float'
        params = parse_tune_annotations(code)
        self.assertEqual(params[0].param_type, "float")

    def test_parse_categorical(self):
        code = 'strategy = "greedy"  # @TUNE {greedy, round_robin, weighted}'
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 1)
        p = params[0]
        self.assertEqual(p.param_type, "categorical")
        self.assertEqual(p.choices, ["greedy", "round_robin", "weighted"])
        self.assertEqual(p.value, "greedy")

    def test_parse_multiple(self):
        code = (
            'load_cutoff = 0.4  # @TUNE [0.0, 1.0]\n'
            'batch_size = 32  # @TUNE [8, 128] int\n'
            'strategy = "greedy"  # @TUNE {greedy, round_robin, weighted}\n'
        )
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 3)

    def test_max_params_enforced(self):
        code = (
            'a = 1  # @TUNE [0, 10] int\n'
            'b = 2  # @TUNE [0, 10] int\n'
            'c = 3  # @TUNE [0, 10] int\n'
            'd = 4  # @TUNE [0, 10] int\n'
        )
        params = parse_tune_annotations(code, max_params=3)
        self.assertEqual(len(params), 3)
        self.assertEqual(params[-1].name, "c")

    def test_no_tune_returns_empty(self):
        code = 'x = 42\ny = "hello"\n'
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 0)

    def test_ignores_non_assignment_lines(self):
        code = 'if x < 0.5:  # @TUNE [0.0, 1.0]\n    pass'
        params = parse_tune_annotations(code)
        self.assertEqual(len(params), 0)

    def test_preserves_line_number(self):
        code = 'x = 1\nload = 0.4  # @TUNE [0.0, 1.0]\ny = 2\n'
        params = parse_tune_annotations(code)
        self.assertEqual(params[0].line_number, 1)  # 0-indexed
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tuning.py::TestParseTuneAnnotations -v`
Expected: FAIL — `openevolve.tuning` does not exist

**Step 3: Write minimal implementation**

Create `openevolve/tuning.py`:

```python
"""
Structured threshold tuning for OpenEvolve.

Parses @TUNE annotations from LLM-generated code, runs Optuna to find
optimal threshold values, and rewrites code with @TUNED feedback.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)

# Regex for: varname = value  # @TUNE [low, high] [int|float]
_TUNE_RANGE_RE = re.compile(
    r"^(\s*(\w+)\s*=\s*(.+?)\s*)#\s*@TUNE\s+\[([^,\]]+),\s*([^\]]+)\](\s+(?:int|float))?"
)

# Regex for: varname = "value"  # @TUNE {a, b, c}
_TUNE_CAT_RE = re.compile(
    r'^(\s*(\w+)\s*=\s*(.+?)\s*)#\s*@TUNE\s+\{([^}]+)\}'
)

# Regex to strip existing @TUNED(...) annotations
_TUNED_RE = re.compile(r"\s*@TUNED\([^)]*\)")


@dataclass
class TuneParam:
    """A single tunable parameter parsed from code."""

    name: str
    value: object  # original value (float, int, or str)
    line_number: int  # 0-indexed line in code
    full_line: str  # the full original line text
    param_type: str = "float"  # "float", "int", "categorical"
    low: Optional[float] = None
    high: Optional[float] = None
    choices: Optional[List[str]] = None


def parse_tune_annotations(code: str, max_params: int = 3) -> List[TuneParam]:
    """Parse @TUNE annotations from code, returning up to max_params."""
    params: List[TuneParam] = []
    lines = code.split("\n")

    for i, line in enumerate(lines):
        if len(params) >= max_params:
            break
        if "@TUNE" not in line:
            continue

        # Try range pattern first: [low, high]
        m = _TUNE_RANGE_RE.match(line)
        if m:
            name = m.group(2)
            raw_value = m.group(3).strip().strip('"').strip("'")
            low = float(m.group(4).strip())
            high = float(m.group(5).strip())
            type_hint = (m.group(6) or "").strip()

            if type_hint == "int":
                param_type = "int"
                value = int(float(raw_value))
                low, high = int(low), int(high)
            else:
                param_type = "float"
                value = float(raw_value)

            params.append(TuneParam(
                name=name, value=value, line_number=i,
                full_line=line, param_type=param_type,
                low=low, high=high,
            ))
            continue

        # Try categorical pattern: {a, b, c}
        m = _TUNE_CAT_RE.match(line)
        if m:
            name = m.group(2)
            raw_value = m.group(3).strip().strip('"').strip("'")
            choices = [c.strip() for c in m.group(4).split(",")]
            params.append(TuneParam(
                name=name, value=raw_value, line_number=i,
                full_line=line, param_type="categorical",
                choices=choices,
            ))
            continue

    return params


def strip_tuned_annotations(code: str) -> str:
    """Remove all @TUNED(...) annotations from code, preserving @TUNE."""
    return _TUNED_RE.sub("", code)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tuning.py::TestParseTuneAnnotations -v`
Expected: PASS (9 tests)

**Step 5: Commit**

```bash
git add openevolve/tuning.py tests/test_tuning.py
git commit -m "feat(tuning): parse @TUNE annotations from code"
```

---

### Task 3: Rewrite code with optimized values and `@TUNED`

**Files:**
- Modify: `openevolve/tuning.py`
- Test: `tests/test_tuning.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_tuning.py`:

```python
from openevolve.tuning import rewrite_tune_values, strip_tuned_annotations


class TestStripTunedAnnotations(unittest.TestCase):
    """Test stripping @TUNED(...) from code."""

    def test_strip_tuned(self):
        code = 'load = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.12, best_impact=tp:+0.3)'
        result = strip_tuned_annotations(code)
        self.assertIn("@TUNE [0.0, 1.0]", result)
        self.assertNotIn("@TUNED", result)

    def test_strip_preserves_non_tuned_lines(self):
        code = 'x = 42\nload = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.1)\ny = 3\n'
        result = strip_tuned_annotations(code)
        self.assertIn("x = 42", result)
        self.assertIn("y = 3", result)

    def test_noop_without_tuned(self):
        code = 'load = 0.4  # @TUNE [0.0, 1.0]\n'
        result = strip_tuned_annotations(code)
        self.assertEqual(result, code)


class TestRewriteTuneValues(unittest.TestCase):
    """Test rewriting threshold values and adding @TUNED annotations."""

    def test_rewrite_float(self):
        code = 'load = 0.4  # @TUNE [0.0, 1.0]\n'
        params = parse_tune_annotations(code)
        new_values = {"load": 0.67}
        original_score = 0.5
        best_score = 0.62
        best_metrics = {"throughput": 1.3}
        original_metrics = {"throughput": 1.0}
        result = rewrite_tune_values(
            code, params, new_values,
            original_score, best_score,
            original_metrics, best_metrics,
        )
        self.assertIn("load = 0.67", result)
        self.assertIn("@TUNED(was=0.4", result)
        self.assertIn("gain=+0.12", result)

    def test_rewrite_int(self):
        code = 'batch = 32  # @TUNE [8, 128] int\n'
        params = parse_tune_annotations(code)
        new_values = {"batch": 64}
        result = rewrite_tune_values(
            code, params, new_values,
            0.5, 0.6, {"x": 1.0}, {"x": 1.5},
        )
        self.assertIn("batch = 64", result)

    def test_rewrite_categorical(self):
        code = 'strategy = "greedy"  # @TUNE {greedy, round_robin, weighted}\n'
        params = parse_tune_annotations(code)
        new_values = {"strategy": "weighted"}
        result = rewrite_tune_values(
            code, params, new_values,
            0.5, 0.6, {"x": 1.0}, {"x": 1.5},
        )
        self.assertIn('strategy = "weighted"', result)
        self.assertIn("@TUNED(was=greedy", result)

    def test_non_tune_lines_unchanged(self):
        code = 'x = 42\nload = 0.4  # @TUNE [0.0, 1.0]\ny = 3\n'
        params = parse_tune_annotations(code)
        new_values = {"load": 0.67}
        result = rewrite_tune_values(
            code, params, new_values,
            0.5, 0.6, {"tp": 1.0}, {"tp": 1.3},
        )
        self.assertIn("x = 42", result)
        self.assertIn("y = 3", result)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tuning.py::TestRewriteTuneValues -v`
Expected: FAIL — `rewrite_tune_values` does not exist

**Step 3: Write minimal implementation**

Add to `openevolve/tuning.py`:

```python
def _compute_best_impact(
    original_metrics: dict, best_metrics: dict
) -> str:
    """Find the single metric with the largest absolute delta."""
    best_metric = None
    best_delta = 0.0
    for key in best_metrics:
        if key in original_metrics:
            orig = original_metrics[key]
            best = best_metrics[key]
            if isinstance(orig, (int, float)) and isinstance(best, (int, float)):
                delta = best - orig
                if abs(delta) > abs(best_delta):
                    best_delta = delta
                    best_metric = key
    if best_metric is None:
        return ""
    sign = "+" if best_delta >= 0 else ""
    # Format: round to reasonable precision
    if abs(best_delta) >= 1:
        delta_str = f"{sign}{best_delta:.1f}"
    else:
        delta_str = f"{sign}{best_delta:.4f}"
    return f"{best_metric}:{delta_str}"


def rewrite_tune_values(
    code: str,
    params: List[TuneParam],
    new_values: dict,
    original_score: float,
    best_score: float,
    original_metrics: dict,
    best_metrics: dict,
) -> str:
    """Rewrite @TUNE lines with optimized values and @TUNED annotations."""
    gain = best_score - original_score
    gain_str = f"{'+' if gain >= 0 else ''}{gain:.2f}"
    impact_str = _compute_best_impact(original_metrics, best_metrics)

    lines = code.split("\n")
    param_by_line = {p.line_number: p for p in params}

    for line_num, param in param_by_line.items():
        if line_num >= len(lines):
            continue
        new_val = new_values.get(param.name)
        if new_val is None:
            continue

        old_line = lines[line_num]
        # Preserve indentation
        indent = old_line[: len(old_line) - len(old_line.lstrip())]

        # Build the assignment part
        if param.param_type == "categorical":
            assign = f'{indent}{param.name} = "{new_val}"'
        elif param.param_type == "int":
            assign = f'{indent}{param.name} = {int(new_val)}'
        else:
            assign = f'{indent}{param.name} = {round(new_val, 4)}'

        # Preserve the @TUNE annotation from the original line
        tune_match = re.search(r"#\s*@TUNE\s+(?:\[[^\]]+\]|\{[^}]+\})(?:\s+(?:int|float))?", old_line)
        tune_part = tune_match.group(0) if tune_match else ""

        # Build @TUNED annotation
        was_val = param.value
        tuned_parts = [f"was={was_val}", f"gain={gain_str}"]
        if impact_str:
            tuned_parts.append(f"best_impact={impact_str}")
        tuned_annotation = f"@TUNED({', '.join(tuned_parts)})"

        lines[line_num] = f"{assign}  {tune_part} {tuned_annotation}"

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tuning.py::TestRewriteTuneValues tests/test_tuning.py::TestStripTunedAnnotations -v`
Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add openevolve/tuning.py tests/test_tuning.py
git commit -m "feat(tuning): rewrite code with optimized values and @TUNED"
```

---

### Task 4: Optuna integration — `tune_program()`

**Files:**
- Modify: `openevolve/tuning.py`
- Test: `tests/test_tuning.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_tuning.py`:

```python
import asyncio


class TestTuneProgram(unittest.TestCase):
    """Test the full tune_program() orchestration."""

    def test_tune_program_no_annotations_returns_unchanged(self):
        """Programs without @TUNE should pass through unchanged."""
        from openevolve.tuning import tune_program
        from openevolve.config import TuningConfig

        code = "x = 42\ndef solve(): return x\n"
        config = TuningConfig(enabled=True, budget=5)

        async def mock_evaluate(program_code, program_id=""):
            return {"combined_score": 0.5}

        result = asyncio.run(tune_program(code, mock_evaluate, config))
        self.assertEqual(result, code)

    def test_tune_program_optimizes_float(self):
        """Should find a better value for a tunable float."""
        from openevolve.tuning import tune_program
        from openevolve.config import TuningConfig

        # The evaluator rewards values close to 0.7
        code = 'threshold = 0.1  # @TUNE [0.0, 1.0]\ndef solve(): pass\n'
        config = TuningConfig(enabled=True, budget=20)

        async def mock_evaluate(program_code, program_id=""):
            # Parse the threshold value from the code
            import re
            m = re.search(r"threshold\s*=\s*([0-9.]+)", program_code)
            val = float(m.group(1)) if m else 0.0
            # Score peaks at 0.7
            score = 1.0 - abs(val - 0.7)
            return {"combined_score": score}

        result = asyncio.run(tune_program(code, mock_evaluate, config))
        self.assertIn("@TUNED", result)
        self.assertIn("was=0.1", result)

    def test_tune_program_fallback_on_failure(self):
        """If all trials fail, return original code."""
        from openevolve.tuning import tune_program
        from openevolve.config import TuningConfig

        code = 'threshold = 0.5  # @TUNE [0.0, 1.0]\n'
        config = TuningConfig(enabled=True, budget=3)

        async def failing_evaluate(program_code, program_id=""):
            raise RuntimeError("Evaluator crashed")

        result = asyncio.run(tune_program(code, failing_evaluate, config))
        # Should return original code unchanged
        self.assertNotIn("@TUNED", result)
        self.assertIn("threshold = 0.5", result)

    def test_tune_program_respects_max_params(self):
        """Only first max_params annotations should be tuned."""
        from openevolve.tuning import tune_program
        from openevolve.config import TuningConfig

        code = (
            'a = 1  # @TUNE [0, 10] int\n'
            'b = 2  # @TUNE [0, 10] int\n'
            'c = 3  # @TUNE [0, 10] int\n'
            'd = 4  # @TUNE [0, 10] int\n'
        )
        config = TuningConfig(enabled=True, budget=5, max_params=2)

        async def mock_evaluate(program_code, program_id=""):
            return {"combined_score": 0.5}

        result = asyncio.run(tune_program(code, mock_evaluate, config))
        # a and b should have @TUNED, c and d should not
        lines = result.split("\n")
        tuned_lines = [l for l in lines if "@TUNED" in l]
        self.assertEqual(len(tuned_lines), 2)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tuning.py::TestTuneProgram -v`
Expected: FAIL — `tune_program` does not exist

**Step 3: Write minimal implementation**

Add to `openevolve/tuning.py`:

```python
import asyncio
from typing import Callable, Awaitable


async def tune_program(
    code: str,
    evaluate_fn: Callable[[str, str], Awaitable[dict]],
    config: "TuningConfig",
) -> str:
    """Optimize @TUNE thresholds using Optuna, return rewritten code.

    Args:
        code: Child program code with @TUNE annotations.
        evaluate_fn: Async function(code, program_id) -> metrics dict.
        config: TuningConfig with budget, max_params, etc.

    Returns:
        Code with optimized values and @TUNED annotations.
        Falls back to original code if tuning fails.
    """
    # Strip any existing @TUNED from inherited parent annotations
    code = strip_tuned_annotations(code)

    # Parse @TUNE annotations
    params = parse_tune_annotations(code, max_params=config.max_params)
    if not params:
        return code

    try:
        import optuna
    except ImportError:
        raise ImportError(
            "Optuna is required for threshold tuning. "
            "Install it with: pip install openevolve[tuning]"
        )

    # Suppress Optuna's verbose logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    n_trials = config.budget + len(params) * config.budget_scale_per_param

    # Evaluate original code first to get baseline
    try:
        original_metrics = await evaluate_fn(code, "tune_baseline")
        original_score = original_metrics.get("combined_score", 0.0)
    except Exception:
        logger.warning("[TUNING] Baseline evaluation failed, skipping tuning")
        return code

    # Track best result
    best_score = original_score
    best_values = {p.name: p.value for p in params}
    best_metrics = original_metrics.copy()

    def objective(trial):
        """Optuna objective: suggest values, evaluate, return score."""
        values = {}
        for p in params:
            if p.param_type == "float":
                values[p.name] = trial.suggest_float(p.name, p.low, p.high)
            elif p.param_type == "int":
                values[p.name] = trial.suggest_int(p.name, int(p.low), int(p.high))
            elif p.param_type == "categorical":
                values[p.name] = trial.suggest_categorical(p.name, p.choices)

        # Rewrite code with trial values (no @TUNED yet, just values)
        trial_code = _rewrite_values_only(code, params, values)

        # Evaluate — run async evaluate in a new event loop
        try:
            trial_id = f"tune_trial_{trial.number}"
            loop = asyncio.new_event_loop()
            try:
                metrics = loop.run_until_complete(evaluate_fn(trial_code, trial_id))
            finally:
                loop.close()
            score = metrics.get("combined_score", 0.0)
            # Store metrics for later use
            trial.set_user_attr("metrics", metrics)
            return score
        except Exception as e:
            logger.debug(f"[TUNING] Trial {trial.number} failed: {e}")
            return float("-inf")

    # Run Optuna study in executor to avoid blocking async loop
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(),
    )

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: study.optimize(objective, n_trials=n_trials, show_progress_bar=False),
    )

    # Check if any trial beat the original
    try:
        best_trial = study.best_trial
        if best_trial.value is not None and best_trial.value > original_score:
            best_score = best_trial.value
            best_values = best_trial.params
            best_metrics = best_trial.user_attrs.get("metrics", original_metrics)
    except ValueError:
        # No completed trials
        logger.warning("[TUNING] No trials completed, using original values")
        return code

    # If no improvement, still annotate with gain=0
    result = rewrite_tune_values(
        code, params, best_values,
        original_score, best_score,
        original_metrics, best_metrics,
    )

    gain = best_score - original_score
    logger.info(
        f"[TUNING] Optimized {len(params)} params over {n_trials} trials: "
        f"score {original_score:.4f} → {best_score:.4f} (gain={gain:+.4f})"
    )

    return result


def _rewrite_values_only(code: str, params: List[TuneParam], values: dict) -> str:
    """Rewrite just the values (no @TUNED annotation). Used during trial loop."""
    lines = code.split("\n")
    param_by_line = {p.line_number: p for p in params}

    for line_num, param in param_by_line.items():
        if line_num >= len(lines):
            continue
        new_val = values.get(param.name)
        if new_val is None:
            continue

        old_line = lines[line_num]
        indent = old_line[: len(old_line) - len(old_line.lstrip())]

        if param.param_type == "categorical":
            assign = f'{indent}{param.name} = "{new_val}"'
        elif param.param_type == "int":
            assign = f'{indent}{param.name} = {int(new_val)}'
        else:
            assign = f'{indent}{param.name} = {round(new_val, 4)}'

        # Preserve the comment part (everything from # onward)
        comment_match = re.search(r"#.*$", old_line)
        comment = comment_match.group(0) if comment_match else ""

        lines[line_num] = f"{assign}  {comment}"

    return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tuning.py::TestTuneProgram -v`
Expected: PASS (4 tests)

**Step 5: Run ALL tuning tests to check nothing broke**

Run: `python -m pytest tests/test_tuning.py -v`
Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add openevolve/tuning.py tests/test_tuning.py
git commit -m "feat(tuning): Optuna integration and tune_program orchestrator"
```

---

### Task 5: Tuning stats, logging, and validation

**Files:**
- Modify: `openevolve/tuning.py`
- Modify: `openevolve/iteration.py`
- Test: `tests/test_tuning.py` (append)

**Why:** During experiments you need confidence that tuning actually ran, what it found, and how long it took. This mirrors the `IterationHypothesisStats` / `HypothesisTracker` pattern from the hypothesis pipeline.

**Step 1: Write the failing tests**

Append to `tests/test_tuning.py`:

```python
from openevolve.tuning import IterationTuningStats, TuningTracker


class TestIterationTuningStats(unittest.TestCase):
    """Test per-iteration tuning stats dataclass."""

    def test_default_values(self):
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
            param_changes={"load": {"was": 0.4, "now": 0.67}, "batch": {"was": 32, "now": 64}},
        )
        self.assertTrue(stats.tuning_ran)
        self.assertAlmostEqual(stats.gain, 0.12)
        self.assertEqual(len(stats.param_changes), 2)


class TestTuningTracker(unittest.TestCase):
    """Test cross-iteration tuning tracker."""

    def test_record_and_summary(self):
        tracker = TuningTracker()
        stats1 = IterationTuningStats(
            iteration=1, tune_annotations_found=2, tune_annotations_honored=2,
            tuning_ran=True, tuning_duration_s=10.0,
            original_score=0.5, tuned_score=0.6, gain=0.1,
            trials_completed=25, trials_failed=0,
            param_changes={"x": {"was": 0.1, "now": 0.5}},
        )
        stats2 = IterationTuningStats(
            iteration=2, tune_annotations_found=0, tune_annotations_honored=0,
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
        import tempfile
        tracker = TuningTracker()
        stats = IterationTuningStats(
            iteration=1, tuning_ran=True, tuning_duration_s=5.0,
            original_score=0.5, tuned_score=0.55, gain=0.05,
            trials_completed=20, trials_failed=1,
        )
        tracker.record(stats)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tuning_tracker.json"
            tracker.save(path)
            self.assertTrue(path.exists())
            import json
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["total_iterations_tracked"], 1)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tuning.py::TestIterationTuningStats tests/test_tuning.py::TestTuningTracker -v`
Expected: FAIL — classes don't exist

**Step 3: Write implementation**

Add to `openevolve/tuning.py`:

```python
import json
import time
from pathlib import Path
from dataclasses import asdict


@dataclass
class IterationTuningStats:
    """Per-iteration tuning pipeline statistics."""
    iteration: int = 0
    # Annotations detected in child code
    tune_annotations_found: int = 0
    tune_annotations_honored: int = 0  # min(found, max_params)
    # Whether tuning actually ran
    tuning_ran: bool = False
    tuning_duration_s: Optional[float] = None
    # Score before and after tuning
    original_score: Optional[float] = None
    tuned_score: Optional[float] = None
    gain: Optional[float] = None
    # Trial stats
    trials_completed: int = 0
    trials_failed: int = 0
    # Per-param changes: {name: {was: X, now: Y}}
    param_changes: dict = field(default_factory=dict)


@dataclass
class TuningTracker:
    """Aggregates tuning statistics across iterations."""
    iterations: list = field(default_factory=list)
    total_iterations: int = 0
    total_iterations_with_tuning: int = 0
    total_trials: int = 0
    total_gain: float = 0.0
    total_tuning_duration_s: float = 0.0

    def record(self, stats: IterationTuningStats) -> None:
        """Record stats for one iteration and update totals."""
        self.iterations.append(asdict(stats))
        self.total_iterations += 1
        if stats.tuning_ran:
            self.total_iterations_with_tuning += 1
            self.total_trials += stats.trials_completed + stats.trials_failed
            if stats.gain is not None:
                self.total_gain += stats.gain
            if stats.tuning_duration_s is not None:
                self.total_tuning_duration_s += stats.tuning_duration_s

        # Log per-iteration summary
        if stats.tuning_ran:
            logger.info(
                f"[TUNE-TRACK] iter={stats.iteration} | "
                f"annotations={stats.tune_annotations_found}→{stats.tune_annotations_honored} "
                f"trials={stats.trials_completed}ok/{stats.trials_failed}fail "
                f"score={stats.original_score:.4f}→{stats.tuned_score:.4f} "
                f"gain={stats.gain:+.4f} "
                f"duration={stats.tuning_duration_s:.1f}s "
                f"params={list(stats.param_changes.keys())}"
            )
        else:
            logger.info(
                f"[TUNE-TRACK] iter={stats.iteration} | "
                f"annotations={stats.tune_annotations_found} — tuning skipped"
            )

    def summary(self) -> dict:
        """Return a summary dict for persistence."""
        avg_gain = (
            self.total_gain / self.total_iterations_with_tuning
            if self.total_iterations_with_tuning > 0 else 0.0
        )
        avg_duration = (
            self.total_tuning_duration_s / self.total_iterations_with_tuning
            if self.total_iterations_with_tuning > 0 else 0.0
        )
        return {
            "total_iterations_tracked": self.total_iterations,
            "total_iterations_with_tuning": self.total_iterations_with_tuning,
            "total_trials": self.total_trials,
            "avg_gain_when_tuned": round(avg_gain, 4),
            "avg_tuning_duration_s": round(avg_duration, 2),
            "per_iteration": self.iterations,
        }

    def save(self, path: Path) -> None:
        """Save tracker state to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.summary(), f, indent=2)
        logger.info(f"[TUNE-TRACK] Saved tuning tracker to {path}")
```

Then update `tune_program()` to **return stats alongside the code**. Change the signature and add stats collection:

```python
async def tune_program(
    code: str,
    evaluate_fn: Callable[[str, str], Awaitable[dict]],
    config: "TuningConfig",
) -> tuple[str, IterationTuningStats]:
    """Returns (optimized_code, stats)."""
    stats = IterationTuningStats()
    start_time = time.time()

    code = strip_tuned_annotations(code)
    all_params = parse_tune_annotations(code, max_params=100)  # count all
    params = all_params[:config.max_params]
    stats.tune_annotations_found = len(all_params)
    stats.tune_annotations_honored = len(params)

    if not params:
        return code, stats

    # ... (existing Optuna logic, but track trials) ...

    # After study completes:
    completed = [t for t in study.trials if t.value is not None and t.value > float("-inf")]
    failed = len(study.trials) - len(completed)
    stats.trials_completed = len(completed)
    stats.trials_failed = failed
    stats.tuning_ran = True
    stats.tuning_duration_s = time.time() - start_time
    stats.original_score = original_score
    stats.tuned_score = best_score
    stats.gain = best_score - original_score
    stats.param_changes = {
        p.name: {"was": p.value, "now": best_values.get(p.name, p.value)}
        for p in params
    }

    return result, stats
```

Update `iteration.py` to collect and pass stats to a `TuningTracker` (same pattern as `HypothesisTracker`):

In the `Result` dataclass, add:

```python
    tuning_stats: "IterationTuningStats" = None
```

In the tuning integration block:

```python
        if config.tuning.enabled:
            try:
                child_code, tuning_stats = await tune_program(
                    child_code,
                    evaluator.evaluate_program,
                    config.tuning,
                )
                tuning_stats.iteration = iteration
                result.tuning_stats = tuning_stats
            except ImportError as e:
                logger.error(f"[TUNING] {e}")
                return None
            except Exception as e:
                logger.warning(f"[TUNING] Tuning failed, using original code: {e}")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tuning.py -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add openevolve/tuning.py openevolve/iteration.py tests/test_tuning.py
git commit -m "feat(tuning): add IterationTuningStats and TuningTracker for observability"
```

---

### Task 6: Add `THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE` (prompt)

**Files:**
- Modify: `openevolve/prompt/templates.py:48` (after HYPOTHESIS_INSTRUCTIONS_TEMPLATE)
- Modify: `openevolve/prompt/sampler.py:110-120` (add tuning injection)
- Test: `tests/test_tuning.py` (append)

**Step 1: Write the failing tests**

Append to `tests/test_tuning.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tuning.py::TestTuningPromptInjection -v`
Expected: FAIL — `tuning_enabled` kwarg not handled

**Step 3: Write implementation**

Add to `openevolve/prompt/templates.py` after line 48 (after `HYPOTHESIS_INSTRUCTIONS_TEMPLATE`):

```python
# Threshold tuning instructions appended to system message when tuning.enabled=True
THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE = """

## Threshold Tuning

You may annotate up to 3 variable assignments with `@TUNE` to declare tunable thresholds.
An optimizer will search the declared ranges before scoring your program.

### Syntax

```
var = value  # @TUNE [min, max]          # float (default)
var = value  # @TUNE [min, max] int      # integer
var = value  # @TUNE [min, max] float    # explicit float
var = "val"  # @TUNE {opt1, opt2, opt3}  # categorical
```

### What happens

After you generate code, the optimizer will try different values within your declared ranges and pick the best ones. So focus on picking **good ranges**, not perfect values.

### Reading feedback

After tuning, you will see `@TUNED` annotations:
```
threshold_a = 0.72  # @TUNE [0.0, 1.0] @TUNED(was=0.5, gain=+0.11, best_impact=accuracy:+0.05)
max_retries = 7  # @TUNE [1, 10] int @TUNED(was=3, gain=+0.11, best_impact=success_rate:+0.1)
```

- `gain` = total score improvement from tuning all parameters jointly
- `best_impact` = the single metric this parameter affected most

### Rules

- Max 3 `@TUNE` per program. Choose the most impactful parameters. Hardcode the rest.
- `@TUNE` must appear on a simple assignment line (`name = value`).
- Focus on parameters where you're uncertain: decision boundaries, cutoffs, weights, scaling factors.
- Don't tune constants you know theoretically (e.g., pi, array sizes).
- Don't manually change `@TUNED` annotations from the parent — the optimizer handles those.
"""
```

Add to `openevolve/prompt/sampler.py` after the hypothesis injection block (after line 120):

```python
        # Append tuning instructions if enabled AND not already present in config
        tuning_enabled = kwargs.pop("tuning_enabled", False)
        if tuning_enabled:
            if "@TUNE" not in system_message:
                from openevolve.prompt.templates import THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE
                system_message = system_message + THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE
                logger.info("[TUNING] Appended threshold tuning template to system prompt")
            else:
                logger.info("[TUNING] tuning_enabled=true, config already contains @TUNE instructions (skipping template)")
        else:
            logger.debug("[TUNING] tuning_enabled=false, no tuning instructions in prompt")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tuning.py::TestTuningPromptInjection -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add openevolve/prompt/templates.py openevolve/prompt/sampler.py tests/test_tuning.py
git commit -m "feat(tuning): add threshold tuning prompt template and injection"
```

---

### Task 7: Integrate tuning into iteration flow

**Files:**
- Modify: `openevolve/iteration.py:1-27` (imports) and `openevolve/iteration.py:147-157` (insert tuning step)

**Step 1: Write the failing test**

Append to `tests/test_tuning.py`:

```python
class TestIterationIntegration(unittest.TestCase):
    """Test that tune_program is called in the right place in the iteration flow."""

    def test_tuning_import(self):
        """Verify tuning module is importable from iteration context."""
        from openevolve.tuning import tune_program, parse_tune_annotations
        self.assertTrue(callable(tune_program))
        self.assertTrue(callable(parse_tune_annotations))
```

This is a basic smoke test. The real integration test requires the full iteration machinery, which is tested via end-to-end runs.

**Step 2: Run test to verify it passes (it should already pass)**

Run: `python -m pytest tests/test_tuning.py::TestIterationIntegration -v`
Expected: PASS

**Step 3: Modify iteration.py**

Add import at top of `openevolve/iteration.py` (after line 26):

```python
from openevolve.tuning import tune_program
```

Add tuning step in `run_iteration_with_shared_db` after the code-length check (after line 153) and before the evaluation (line 155):

```python
        # Tune thresholds if enabled
        if config.tuning.enabled:
            try:
                child_code = await tune_program(
                    child_code,
                    evaluator.evaluate_program,
                    config.tuning,
                )
            except ImportError as e:
                logger.error(f"[TUNING] {e}")
                return None
            except Exception as e:
                logger.warning(f"[TUNING] Tuning failed, using original code: {e}")
```

Also pass `tuning_enabled` to `build_prompt` in the prompt building section (line 71-84). Add after `hypothesis_driven=config.hypothesis_driven`:

```python
            tuning_enabled=config.tuning.enabled,
```

**Step 4: Run the full test suite to check nothing broke**

Run: `python -m pytest tests/ -v --timeout=60`
Expected: PASS (all existing tests still pass)

**Step 5: Commit**

```bash
git add openevolve/iteration.py tests/test_tuning.py
git commit -m "feat(tuning): integrate tune_program into iteration flow"
```

---

### Task 8: Add `optuna` as optional dependency

**Files:**
- Modify: `pyproject.toml:22-31`

**Step 1: Add the optional dependency group**

In `pyproject.toml`, after the `[project.optional-dependencies]` section's `dev` list, add:

```toml
tuning = [
    "optuna>=3.0.0",
]
```

**Step 2: Verify installation works**

Run: `pip install -e ".[tuning]"`
Expected: Installs optuna

**Step 3: Run full test suite**

Run: `python -m pytest tests/test_tuning.py -v`
Expected: PASS (all tuning tests)

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(tuning): add optuna as optional dependency"
```

---

### Task 9: Run full test suite and format

**Step 1: Format code**

Run: `python -m black openevolve/tuning.py openevolve/config.py openevolve/iteration.py openevolve/prompt/templates.py openevolve/prompt/sampler.py tests/test_tuning.py`

**Step 2: Run complete test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests including new ones)

**Step 3: Commit any formatting changes**

```bash
git add -u
git commit -m "style: format tuning code with black"
```

---

## Summary

| Task | What | Files | Tests |
|------|------|-------|-------|
| 1 | `TuningConfig` dataclass | `config.py` | 4 |
| 2 | Parse `@TUNE` annotations | `tuning.py` (new) | 9 |
| 3 | Rewrite code with `@TUNED` | `tuning.py` | 7 |
| 4 | Optuna `tune_program()` | `tuning.py` | 4 |
| 5 | `IterationTuningStats` + `TuningTracker` | `tuning.py`, `iteration.py` | 4 |
| 6 | Prompt template + injection | `templates.py`, `sampler.py` | 3 |
| 7 | Iteration flow integration | `iteration.py` | 1 + E2E |
| 8 | Optional dependency | `pyproject.toml` | — |
| 9 | Format + full test suite | all | all |

Total: ~32 new unit tests across 9 tasks.

### What you'll see in experiment logs

When tuning is active, every iteration logs a `[TUNE-TRACK]` line:

```
[TUNE-TRACK] iter=5 | annotations=3→3 trials=25ok/0fail score=0.4200→0.5100 gain=+0.0900 duration=18.3s params=['load_cutoff', 'batch_size', 'strategy']
[TUNE-TRACK] iter=6 | annotations=0 — tuning skipped
```

The `TuningTracker` persists a JSON summary (like hypothesis tracker) with:
- Total iterations with/without tuning
- Average gain when tuned
- Average tuning duration
- Per-iteration detail: annotations found/honored, trials ok/fail, score delta, duration, param changes
