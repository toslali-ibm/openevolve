
# Hypothesis-Driven Evolution A/B Experiment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build infrastructure to run a controlled A/B experiment comparing hypothesis-driven evolution vs vanilla OpenEvolve, then produce publication-quality analysis.

**Architecture:** Move generic hypothesis logic (ledger, knowledge base, testing) from `examples/blis_router/hypothesis.py` into `openevolve/hypothesis.py` as a core module. Add `hypothesis_driven: true` config flag (default on). Evaluators opt-in by calling core functions and returning artifacts. Experiment runner launches independent runs with isolated output dirs and collects CSVs for analysis.

**Tech Stack:** Python, OpenEvolve, Gemini Flash API, matplotlib/seaborn, scipy.stats, pandas

**Design doc:** `docs/plans/2026-02-25-hypothesis-ab-experiment-design.md`

---

### Task 0: Create Experiment Branch

Branch off `blis` to isolate all experiment work. The `blis` branch retains your existing results untouched.

**Step 1: Create branch**

```bash
git checkout blis
git checkout -b hypothesis-experiment
```

**Step 2: Verify you're on the new branch**

```bash
git branch --show-current
```

Expected: `hypothesis-experiment`

All subsequent tasks happen on this branch. If anything goes wrong, `blis` is safe.

---

### Task 1: Core Hypothesis Module

Move hypothesis logic to `openevolve/hypothesis.py` as a generic, language-agnostic module.

**Files:**
- Create: `openevolve/hypothesis.py`
- Create: `tests/test_hypothesis.py`

**Step 1: Write the failing test**

```python
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


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hypothesis.py -v`
Expected: FAIL with ImportError (module doesn't exist yet)

**Step 3: Write minimal implementation**

Create `openevolve/hypothesis.py` — generalized from `examples/blis_router/hypothesis.py`:

```python
"""
Generic hypothesis parsing, testing, and ledger management for OpenEvolve.

Evaluators use this module to:
1. Parse HYPOTHESIS/MECHANISM/EXPECT comments from evolved code (any language)
2. Test hypotheses against actual vs baseline metrics
3. Maintain a persistent ledger of outcomes
4. Generate a knowledge base summary for LLM feedback

The comment format works with any language's comment syntax:
    # HYPOTHESIS-1: <claim>          (Python, Ruby, Shell)
    // HYPOTHESIS-1: <claim>         (Go, C, Rust, JS)
    -- HYPOTHESIS-1: <claim>         (SQL, Lua, Haskell)
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Regex that matches any single-line comment prefix: //, #, or --
_COMMENT_PREFIX = r"(?://|#|--)\s*"


def parse_hypotheses(code: str, valid_metrics: set[str]) -> list:
    """Parse HYPOTHESIS-N, MECHANISM-N, EXPECT-N comment blocks from code.

    Supports //, #, and -- comment styles. Returns only complete hypotheses
    (all three fields present) with valid metric names.

    Args:
        code: Source code string containing hypothesis comments.
        valid_metrics: Set of metric names that EXPECT lines may reference.

    Returns:
        List of dicts with keys: id, claim, mechanism, metric, threshold.
    """
    fields: dict[int, dict] = {}
    lines = code.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # HYPOTHESIS-N: <claim>
        m = re.match(rf"^{_COMMENT_PREFIX}HYPOTHESIS-(\d+):\s*(.+)$", line)
        if m:
            hid = int(m.group(1))
            fields.setdefault(hid, {})["claim"] = m.group(2).strip()
            i += 1
            continue

        # MECHANISM-N: <mechanism> (possibly multi-line)
        m = re.match(rf"^{_COMMENT_PREFIX}MECHANISM-(\d+):\s*(.+)$", line)
        if m:
            hid = int(m.group(1))
            parts = [m.group(2).strip()]
            # Consume continuation lines: comment prefix followed by 3+ spaces
            while i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                cont = re.match(r"^(?://|#|--)\s{3,}(.+)$", next_line)
                if cont:
                    parts.append(cont.group(1).strip())
                    i += 1
                else:
                    break
            fields.setdefault(hid, {})["mechanism"] = " ".join(parts)
            i += 1
            continue

        # EXPECT-N: <metric> < <threshold>
        m = re.match(
            rf"^{_COMMENT_PREFIX}EXPECT-(\d+):\s*(\S+)\s*<\s*([0-9]+(?:\.[0-9]+)?)\s*$",
            line,
        )
        if m:
            hid = int(m.group(1))
            entry = fields.setdefault(hid, {})
            entry["metric"] = m.group(2).strip()
            entry["threshold"] = float(m.group(3))
            i += 1
            continue

        i += 1

    results = []
    for hid in sorted(fields):
        f = fields[hid]
        if all(k in f for k in ("claim", "mechanism", "metric", "threshold")):
            if f["metric"] not in valid_metrics:
                logger.warning(
                    "Hypothesis %d references unknown metric %r; skipping", hid, f["metric"]
                )
                continue
            results.append(
                {
                    "id": hid,
                    "claim": f["claim"],
                    "mechanism": f["mechanism"],
                    "metric": f["metric"],
                    "threshold": f["threshold"],
                }
            )
    return results


def test_hypotheses(hypotheses: list, actual_metrics: dict, baseline_metrics: dict) -> list:
    """Test each hypothesis against actual evaluation results and baseline.

    Verdicts: CONFIRMED (actual < threshold), REFUTED, INCONCLUSIVE (metric missing).
    """
    results = []
    for h in hypotheses:
        metric = h["metric"]
        threshold = h["threshold"]
        actual = actual_metrics.get(metric)
        baseline_value = baseline_metrics.get(metric)

        if actual is None:
            verdict = "INCONCLUSIVE"
            delta_pct = None
        else:
            verdict = "CONFIRMED" if actual < threshold else "REFUTED"
            if baseline_value is not None and baseline_value != 0:
                delta_pct = ((actual - baseline_value) / baseline_value) * 100.0
            else:
                delta_pct = None

        results.append(
            {
                "id": h["id"],
                "claim": h["claim"],
                "mechanism": h["mechanism"],
                "metric": metric,
                "threshold": threshold,
                "actual": actual,
                "baseline_value": baseline_value,
                "delta_vs_baseline_pct": delta_pct,
                "verdict": verdict,
            }
        )
    return results


def load_ledger(ledger_path: Path) -> dict:
    """Load hypothesis ledger from disk, or return empty structure."""
    ledger_path = Path(ledger_path)
    if ledger_path.exists():
        with open(ledger_path, "r") as f:
            return json.load(f)
    return {"baseline": {}, "entries": []}


def update_ledger(
    ledger: dict, hypothesis_results: list, overall_combined_score: float, ledger_path: Path
) -> dict:
    """Append hypothesis results to ledger and persist to disk."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_combined_score": overall_combined_score,
        "hypotheses": hypothesis_results,
    }
    ledger["entries"].append(entry)

    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "w") as f:
        json.dump(ledger, f, indent=2)
    return ledger


def generate_knowledge_base_summary(ledger: dict, top_n: int = 5) -> str:
    """Generate text summary of hypothesis outcomes grouped by target metric.

    Sections: CONFIRMED STRATEGIES, REFUTED STRATEGIES, INCONCLUSIVE, BASELINE VALUES.
    """
    entries = ledger.get("entries", [])
    if not entries:
        lines = ["HYPOTHESIS KNOWLEDGE BASE:", "", "No hypothesis data yet."]
        baseline = ledger.get("baseline", {})
        if baseline:
            lines.append("")
            lines.append("BASELINE VALUES (initial program):")
            for k, v in sorted(baseline.items()):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    agg: dict[tuple[str, str], list[dict]] = {}
    for entry in entries:
        for h in entry.get("hypotheses", []):
            key = (h["metric"], h["claim"])
            agg.setdefault(key, []).append(
                {
                    "verdict": h["verdict"],
                    "delta_pct": h.get("delta_vs_baseline_pct"),
                    "mechanism": h.get("mechanism", ""),
                }
            )

    stats = []
    for (metric, claim), records in agg.items():
        total = len(records)
        confirmed = sum(1 for r in records if r["verdict"] == "CONFIRMED")
        confirm_rate = confirmed / total if total > 0 else 0.0
        deltas = [r["delta_pct"] for r in records if r["delta_pct"] is not None]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        mechanism = records[0]["mechanism"]
        stats.append(
            {
                "metric": metric,
                "claim": claim,
                "mechanism": mechanism,
                "total": total,
                "confirmed": confirmed,
                "confirm_rate": confirm_rate,
                "avg_delta": avg_delta,
            }
        )

    confirmed_strategies = [s for s in stats if s["confirm_rate"] >= 0.5]
    refuted_strategies = [s for s in stats if s["confirm_rate"] < 0.5 and s["total"] >= 2]
    inconclusive = [s for s in stats if s["total"] < 2 and s["confirm_rate"] < 0.5]

    confirmed_strategies.sort(key=lambda s: s["avg_delta"])
    refuted_strategies.sort(key=lambda s: -s["avg_delta"])
    confirmed_strategies = confirmed_strategies[:top_n]
    refuted_strategies = refuted_strategies[:top_n]
    inconclusive = inconclusive[:top_n]

    lines = []
    if confirmed_strategies:
        lines.append("=== CONFIRMED STRATEGIES ===")
        for s in confirmed_strategies:
            lines.append(
                f"  [{s['metric']}] {s['claim']} "
                f"(confirmed {s['confirmed']}/{s['total']}, avg_delta={s['avg_delta']:+.1f}%)"
            )
            if s["mechanism"]:
                lines.append(f"    mechanism: {s['mechanism']}")
        lines.append("")

    if refuted_strategies:
        lines.append("=== REFUTED STRATEGIES ===")
        for s in refuted_strategies:
            lines.append(
                f"  [{s['metric']}] {s['claim']} "
                f"(confirmed {s['confirmed']}/{s['total']}, avg_delta={s['avg_delta']:+.1f}%)"
            )
            if s["mechanism"]:
                lines.append(f"    mechanism: {s['mechanism']}")
        lines.append("")

    if inconclusive:
        lines.append("=== INCONCLUSIVE ===")
        for s in inconclusive:
            lines.append(f"  [{s['metric']}] {s['claim']} (total={s['total']})")
        lines.append("")

    baseline = ledger.get("baseline", {})
    if baseline:
        lines.append("=== BASELINE VALUES ===")
        for k, v in sorted(baseline.items()):
            lines.append(f"  {k}: {v}")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_hypothesis_results(
    hypothesis_results: list, overall_score: float, baseline_score: float
) -> str:
    """Format this iteration's hypothesis verdicts as human-readable text."""
    lines = ["--- Hypothesis Verdicts ---"]
    for h in hypothesis_results:
        actual_str = f"{h['actual']:.1f}" if h["actual"] is not None else "N/A"
        delta_str = ""
        if h["delta_vs_baseline_pct"] is not None:
            delta_str = f" (delta={h['delta_vs_baseline_pct']:+.1f}% vs baseline)"
        lines.append(
            f"  H{h['id']} [{h['verdict']}]: "
            f"EXPECT {h['metric']} < {h['threshold']:.1f}, "
            f"ACTUAL {actual_str}{delta_str}"
        )
        lines.append(f"    claim: {h['claim']}")

    score_delta = overall_score - baseline_score
    score_delta_pct = (score_delta / abs(baseline_score) * 100.0) if baseline_score != 0 else 0.0
    lines.append(
        f"  OVERALL: combined_score={overall_score:.2f} "
        f"(delta={score_delta:+.2f}, {score_delta_pct:+.1f}% vs baseline={baseline_score:.2f})"
    )
    return "\n".join(lines)
```

The key difference from the BLIS version: `parse_hypotheses()` takes `valid_metrics` as a parameter instead of using a module constant, and supports `#`, `//`, and `--` comment prefixes.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hypothesis.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add openevolve/hypothesis.py tests/test_hypothesis.py
git commit -m "feat: add core hypothesis module (generalized from blis_router)"
```

---

### Task 2: Add hypothesis_driven Config Flag

**Files:**
- Modify: `openevolve/config.py:380-412` (Config class)

**Step 1: Write the failing test**

```python
# Add to tests/test_hypothesis.py or a new test

def test_config_hypothesis_driven_default():
    from openevolve.config import Config
    config = Config()
    assert config.hypothesis_driven is True

def test_config_hypothesis_driven_from_yaml():
    from openevolve.config import Config
    config = Config.from_dict({"hypothesis_driven": False})
    assert config.hypothesis_driven is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hypothesis.py::test_config_hypothesis_driven_default -v`
Expected: FAIL with AttributeError

**Step 3: Write minimal implementation**

In `openevolve/config.py`, add to the `Config` class (after line 411, before `@classmethod`):

```python
    # Hypothesis-driven evolution
    hypothesis_driven: bool = True
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_hypothesis.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add openevolve/config.py tests/test_hypothesis.py
git commit -m "feat: add hypothesis_driven config flag (default True)"
```

---

### Task 3: Hypothesis Prompt Template Injection

When `hypothesis_driven: true`, append generic hypothesis instructions to the system message.

**Files:**
- Modify: `openevolve/prompt/templates.py:11-14` (add hypothesis template)
- Modify: `openevolve/prompt/sampler.py:102-108` (inject when enabled)

**Step 1: Add hypothesis prompt template**

Add to `openevolve/prompt/templates.py` after line 17:

```python
# Hypothesis instructions appended to system message when hypothesis_driven=True
HYPOTHESIS_INSTRUCTIONS_TEMPLATE = """

## Hypothesis-Driven Evolution

You MUST include at least 1 hypothesis (max 3) as comments at the TOP of the EVOLVE-BLOCK, BEFORE any code.

Format (each hypothesis needs all 3 lines, using the appropriate comment syntax for the language):
  # HYPOTHESIS-N: <one-line claim about what will improve and why>
  # MECHANISM-N: <causal explanation - what signal/behavior drives the improvement>
  # EXPECT-N: <metric_name> < <threshold>

Rules:
  - N starts at 1 and increments
  - metric_name must be one of the metrics shown in your performance feedback
  - threshold is a number; the hypothesis is CONFIRMED if actual < threshold
  - Set thresholds based on baseline values shown in the HYPOTHESIS KNOWLEDGE BASE artifact (if present)
  - Be specific: "improves performance" is too vague; "reduces avg_e2e_ms by routing large requests to less-loaded instances" is good
  - If a strategy was REFUTED in the knowledge base, explain why your new approach differs
  - Build on CONFIRMED strategies; combine proven techniques
  - If no knowledge base is shown yet (first iteration), set thresholds 5-10% below the current metrics
"""
```

**Step 2: Modify prompt sampler to inject hypothesis instructions**

In `openevolve/prompt/sampler.py`, the `build_prompt()` method needs to accept a `hypothesis_driven` flag and append instructions. Modify lines 102-108:

```python
        # Use system template override if set
        if self.system_template_override:
            system_message = self.template_manager.get_template(self.system_template_override)
        else:
            system_message = self.config.system_message
            # If system_message is a template name rather than content, get the template
            if system_message in self.template_manager.templates:
                system_message = self.template_manager.get_template(system_message)

        # Append hypothesis instructions if enabled
        hypothesis_driven = kwargs.pop("hypothesis_driven", False)
        if hypothesis_driven:
            from openevolve.prompt.templates import HYPOTHESIS_INSTRUCTIONS_TEMPLATE
            system_message = system_message + HYPOTHESIS_INSTRUCTIONS_TEMPLATE
```

**Step 3: Pass hypothesis_driven from iteration.py**

In `openevolve/iteration.py`, where `build_prompt()` is called (around line 62-74), the `hypothesis_driven` flag from config needs to be passed. Find the `build_prompt()` call and add `hypothesis_driven=config.hypothesis_driven` to kwargs. The config is available via `database.config`.

**Step 4: Run tests to verify nothing breaks**

Run: `python -m unittest discover tests -v`
Expected: All existing tests PASS

**Step 5: Commit**

```bash
git add openevolve/prompt/templates.py openevolve/prompt/sampler.py openevolve/iteration.py
git commit -m "feat: inject hypothesis instructions into system prompt when enabled"
```

---

### Task 4: Migrate BLIS Router to Core Hypothesis Module

Delete the local `examples/blis_router/hypothesis.py` and update the evaluator to import from the core module. The core module is functionally identical for Go/`//` comments — no behavior change.

**Files:**
- Delete: `examples/blis_router/hypothesis.py`
- Modify: `examples/blis_router/evaluator.py:26-33` (change import)
- Modify: `examples/blis_router/evaluator.py:337-344` (pass valid_metrics)

**Step 1: Update import in evaluator.py**

Change lines 26-33 from:
```python
from hypothesis import (
    parse_hypotheses,
    ...
)
```
To:
```python
from openevolve.hypothesis import (
    parse_hypotheses,
    ...
)
```

**Step 2: Define VALID_METRICS and update parse_hypotheses calls**

Add near the top of evaluator.py:
```python
VALID_METRICS = {
    "cache_warmup_e2e_ms",
    "load_spikes_e2e_ms",
    "multiturn_e2e_ms",
    "avg_e2e_ms",
    "avg_p95_ms",
}
```

Find all calls to `parse_hypotheses(go_code)` and change to:
```python
hypotheses = parse_hypotheses(go_code, valid_metrics=VALID_METRICS)
```

**Step 3: Delete the old local hypothesis.py**

```bash
git rm examples/blis_router/hypothesis.py
```

**Step 4: Verify BLIS router still works**

Run: `python -c "from examples.blis_router.evaluator import evaluate; print('import OK')"`
Expected: "import OK"

Also run existing BLIS hypothesis tests if any:
Run: `python -m pytest tests/test_blis_hypothesis.py -v` (skip if file doesn't exist)

**Step 5: Commit**

```bash
git add examples/blis_router/evaluator.py
git commit -m "refactor: migrate blis_router to core hypothesis module, delete local copy"
```

---

### Task 5: Create BLIS Router Experiment Configs

**Files:**
- Create: `examples/blis_router/config_experiment_treatment.yaml`
- Create: `examples/blis_router/config_experiment_control.yaml`

**Step 1: Create treatment config (hypothesis-driven, Gemini Flash)**

```yaml
# BLIS Router - Treatment (Hypothesis-Driven) - Gemini Flash
max_iterations: 10
checkpoint_interval: 5

llm:
  primary_model: "gemini/gemini-2.0-flash"
  primary_model_weight: 1.0
  api_base: "https://generativelanguage.googleapis.com/v1beta/openai/"
  temperature: 1.0
  max_tokens: 32000
  timeout: 120

prompt:
  system_message: |
    <COPY THE FULL system_message FROM examples/blis_router/config.yaml>
    <INCLUDING all hypothesis instructions>
  num_top_programs: 3
  num_diverse_programs: 2

database:
  population_size: 100
  archive_size: 15
  num_islands: 3
  elite_selection_ratio: 0.3
  exploitation_ratio: 0.65

evaluator:
  timeout: 60
  parallel_evaluations: 1

diff_based_evolution: true
max_code_length: 40000
hypothesis_driven: true
```

**Step 2: Create control config (vanilla, Gemini Flash)**

Same as treatment but:
- `hypothesis_driven: false`
- `system_message`: stripped of all hypothesis-related instructions (remove "HYPOTHESIS REQUIREMENTS" section and hypothesis rules)

**Step 3: Commit**

```bash
git add examples/blis_router/config_experiment_treatment.yaml examples/blis_router/config_experiment_control.yaml
git commit -m "feat: add BLIS router experiment configs (treatment + control)"
```

---

### Task 6: Adapt Function Minimization for Hypothesis-Driven Mode

**Files:**
- Modify: `examples/function_minimization/evaluator.py:45-255` (add hypothesis pipeline)
- Create: `examples/function_minimization/config_experiment_treatment.yaml`
- Create: `examples/function_minimization/config_experiment_control.yaml`

**Step 1: Add hypothesis support to evaluator**

Add hypothesis imports and logic to `examples/function_minimization/evaluator.py`. After the existing evaluation logic computes metrics (around line 215), add:

```python
from openevolve.hypothesis import (
    parse_hypotheses,
    test_hypotheses,
    load_ledger,
    update_ledger,
    generate_knowledge_base_summary,
    format_hypothesis_results,
)

VALID_METRICS = {"value_score", "distance_score", "reliability_score", "combined_score"}
```

In the `evaluate()` function, after the EvaluationResult is built but before returning:

1. Read the program source code
2. Parse hypotheses from it
3. Load/compute baseline (cache on first run)
4. Test hypotheses against actual metrics and baseline
5. Update ledger
6. Generate knowledge base summary
7. Add to artifacts

```python
    # --- Hypothesis pipeline ---
    try:
        with open(program_path, "r") as f:
            source_code = f.read()

        hypotheses = parse_hypotheses(source_code, valid_metrics=VALID_METRICS)

        if hypotheses:
            script_dir = Path(__file__).parent
            baseline_path = script_dir / "baseline_metrics.json"
            ledger_path = script_dir / "openevolve_output" / "hypothesis_ledger.json"

            # Load or compute baseline
            if baseline_path.exists():
                with open(baseline_path, "r") as f:
                    baseline_metrics = json.load(f)
            else:
                # First run: current metrics become baseline
                baseline_metrics = {
                    "value_score": value_score,
                    "distance_score": distance_score,
                    "reliability_score": reliability_score,
                    "combined_score": combined_score,
                }
                with open(baseline_path, "w") as f:
                    json.dump(baseline_metrics, f, indent=2)

            actual_metrics = {
                "value_score": value_score,
                "distance_score": distance_score,
                "reliability_score": reliability_score,
                "combined_score": combined_score,
            }

            h_results = test_hypotheses(hypotheses, actual_metrics, baseline_metrics)
            baseline_score = baseline_metrics.get("combined_score", 0)
            hypothesis_results_text = format_hypothesis_results(h_results, combined_score, baseline_score)

            ledger = load_ledger(ledger_path)
            if not ledger["baseline"] and baseline_metrics:
                ledger["baseline"] = baseline_metrics
            update_ledger(ledger, h_results, combined_score, ledger_path)
            knowledge_base_text = generate_knowledge_base_summary(ledger)

            artifacts["hypothesis_results"] = hypothesis_results_text
            artifacts["hypothesis_knowledge_base"] = knowledge_base_text
        else:
            # Still show knowledge base even without hypotheses
            script_dir = Path(__file__).parent
            ledger_path = script_dir / "openevolve_output" / "hypothesis_ledger.json"
            if ledger_path.exists():
                ledger = load_ledger(ledger_path)
                knowledge_base_text = generate_knowledge_base_summary(ledger)
                if knowledge_base_text:
                    artifacts["hypothesis_knowledge_base"] = knowledge_base_text
    except Exception as e:
        logger.warning(f"Hypothesis pipeline error (non-fatal): {e}")
```

**Step 2: Create treatment config**

```yaml
# Function Minimization - Treatment (Hypothesis-Driven) - Gemini Flash
max_iterations: 10
checkpoint_interval: 5

llm:
  primary_model: "gemini/gemini-2.0-flash"
  primary_model_weight: 1.0
  api_base: "https://generativelanguage.googleapis.com/v1beta/openai/"
  temperature: 0.7
  max_tokens: 16000
  timeout: 120

prompt:
  system_message: |
    You are an expert programmer specializing in optimization algorithms.
    Your task is to improve a function minimization algorithm to find the global minimum
    of a complex function with many local minima.
    The function is f(x, y) = sin(x) * cos(y) + sin(x*y) + (x^2 + y^2)/20.
    Focus on improving the search_algorithm function to reliably find the global minimum.

    Available metrics for EXPECT (lower = better for distance/value, higher = better for scores):
      - value_score: how close found value is to global minimum (higher = better)
      - distance_score: proximity in parameter space (higher = better)
      - reliability_score: success rate across trials (higher = better)
      - combined_score: weighted combination (higher = better)

database:
  population_size: 50
  archive_size: 20
  num_islands: 3
  elite_selection_ratio: 0.2
  exploitation_ratio: 0.7

evaluator:
  timeout: 60
  cascade_thresholds: [1.3]
  parallel_evaluations: 3

diff_based_evolution: true
max_code_length: 20000
hypothesis_driven: true
```

**Step 3: Create control config**

Same but `hypothesis_driven: false` and no metric hints in system_message.

**Step 4: Commit**

```bash
git add examples/function_minimization/evaluator.py examples/function_minimization/config_experiment_treatment.yaml examples/function_minimization/config_experiment_control.yaml
git commit -m "feat: add hypothesis support to function_minimization + experiment configs"
```

---

### Task 7: Experiment Runner Script

**Files:**
- Create: `scripts/run_experiment.py`

**Step 1: Write the experiment runner**

```python
#!/usr/bin/env python3
"""
Run A/B experiment: hypothesis-driven vs vanilla OpenEvolve.

Usage:
    python scripts/run_experiment.py \
        --task blis_router \
        --condition treatment \
        --runs 5 \
        --seed-start 100 \
        --output-dir experiments/hypothesis_ab_blis

Each run gets an isolated output directory and random seed.
After all runs complete, convergence data is collected into a CSV.
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TASK_CONFIGS = {
    "blis_router": {
        "initial_program": "examples/blis_router/initial_program.py",
        "evaluator": "examples/blis_router/evaluator.py",
        "treatment_config": "examples/blis_router/config_experiment_treatment.yaml",
        "control_config": "examples/blis_router/config_experiment_control.yaml",
    },
    "function_minimization": {
        "initial_program": "examples/function_minimization/initial_program.py",
        "evaluator": "examples/function_minimization/evaluator.py",
        "treatment_config": "examples/function_minimization/config_experiment_treatment.yaml",
        "control_config": "examples/function_minimization/config_experiment_control.yaml",
    },
}


def run_single(task: str, condition: str, seed: int, output_dir: Path) -> dict:
    """Run a single OpenEvolve experiment and return convergence data."""
    task_info = TASK_CONFIGS[task]
    config_path = task_info[f"{condition}_config"]

    run_dir = output_dir / f"{condition}_run_{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "openevolve-run.py",
        task_info["initial_program"],
        task_info["evaluator"],
        "--config", config_path,
        "--iterations", "10",
        "--output-dir", str(run_dir),
    ]

    print(f"Starting {condition} run seed={seed} -> {run_dir}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    if result.returncode != 0:
        print(f"  FAILED: {result.stderr[:500]}")
        return {"seed": seed, "condition": condition, "status": "failed", "error": result.stderr[:500]}

    # Collect convergence data from checkpoints
    convergence = collect_convergence(run_dir)
    return {"seed": seed, "condition": condition, "status": "ok", "convergence": convergence}


def collect_convergence(run_dir: Path) -> list:
    """Extract best_score at each checkpoint iteration."""
    checkpoints_dir = run_dir / "checkpoints"
    if not checkpoints_dir.exists():
        return []

    points = []
    for cp_dir in sorted(checkpoints_dir.iterdir()):
        if not cp_dir.is_dir():
            continue
        metrics_file = cp_dir / "best_metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                metrics = json.load(f)
            iteration = int(cp_dir.name.split("_")[-1]) if "_" in cp_dir.name else 0
            points.append({
                "iteration": iteration,
                "best_combined_score": metrics.get("combined_score", 0),
            })
    return points


def write_csv(results: list, output_path: Path):
    """Write convergence data to CSV for analysis."""
    rows = []
    for r in results:
        if r["status"] != "ok":
            continue
        for point in r.get("convergence", []):
            rows.append({
                "condition": r["condition"],
                "seed": r["seed"],
                "iteration": point["iteration"],
                "best_combined_score": point["best_combined_score"],
            })

    if not rows:
        print("No convergence data to write")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["condition", "seed", "iteration", "best_combined_score"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote convergence CSV to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run hypothesis A/B experiment")
    parser.add_argument("--task", required=True, choices=list(TASK_CONFIGS.keys()))
    parser.add_argument("--condition", required=True, choices=["treatment", "control", "both"])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=100)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    conditions = ["treatment", "control"] if args.condition == "both" else [args.condition]

    results = []
    for condition in conditions:
        for i in range(args.runs):
            seed = args.seed_start + i
            try:
                result = run_single(args.task, condition, seed, output_dir)
                results.append(result)
            except Exception as e:
                print(f"Run failed: {e}")
                results.append({"seed": seed, "condition": condition, "status": "error", "error": str(e)})

    # Write CSV
    csv_path = output_dir / "convergence.csv"
    write_csv(results, csv_path)

    # Write raw results
    with open(output_dir / "run_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nExperiment complete. Results in {output_dir}")


if __name__ == "__main__":
    main()
```

**Step 2: Verify script parses correctly**

Run: `python scripts/run_experiment.py --help`
Expected: Shows usage information

**Step 3: Commit**

```bash
git add scripts/run_experiment.py
git commit -m "feat: add experiment runner script for hypothesis A/B study"
```

---

### Task 8: Analysis Notebook

**Files:**
- Create: `scripts/analyze_experiment.py`

**Step 1: Write analysis script**

```python
#!/usr/bin/env python3
"""
Analyze hypothesis A/B experiment results and generate plots.

Usage:
    python scripts/analyze_experiment.py --data experiments/hypothesis_ab_blis/convergence.csv --output experiments/hypothesis_ab_blis/plots/
"""
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy.stats import mannwhitneyu


def load_data(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def plot_convergence_curves(df: pd.DataFrame, output_dir: Path, title_suffix: str = ""):
    """Plot median convergence curves with IQR bands."""
    fig, ax = plt.subplots(figsize=(8, 5))

    for condition, color in [("treatment", "#2196F3"), ("control", "#FF5722")]:
        cond_data = df[df["condition"] == condition]
        if cond_data.empty:
            continue

        grouped = cond_data.groupby("iteration")["best_combined_score"]
        median = grouped.median()
        q25 = grouped.quantile(0.25)
        q75 = grouped.quantile(0.75)

        label = "Hypothesis-Driven" if condition == "treatment" else "Vanilla OpenEvolve"
        ax.plot(median.index, median.values, color=color, linewidth=2, label=label)
        ax.fill_between(median.index, q25.values, q75.values, color=color, alpha=0.2)

    ax.set_xlabel("Iteration", fontsize=12)
    ax.set_ylabel("Best Combined Score", fontsize=12)
    ax.set_title(f"Convergence: Hypothesis-Driven vs Vanilla{title_suffix}", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    output_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_dir / "convergence_curves.png", dpi=150)
    plt.close(fig)
    print(f"Saved convergence_curves.png")


def plot_final_scores_boxplot(df: pd.DataFrame, output_dir: Path):
    """Box plot of final best scores at last iteration."""
    max_iter = df["iteration"].max()
    final = df[df["iteration"] == max_iter]

    fig, ax = plt.subplots(figsize=(6, 5))
    data = [
        final[final["condition"] == "treatment"]["best_combined_score"].values,
        final[final["condition"] == "control"]["best_combined_score"].values,
    ]
    labels = ["Hypothesis-Driven", "Vanilla"]

    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    bp["boxes"][0].set_facecolor("#2196F3")
    bp["boxes"][1].set_facecolor("#FF5722")

    ax.set_ylabel("Final Best Score (iteration {})".format(max_iter), fontsize=12)
    ax.set_title("Final Score Distribution", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(output_dir / "final_scores_boxplot.png", dpi=150)
    plt.close(fig)
    print(f"Saved final_scores_boxplot.png")


def compute_statistics(df: pd.DataFrame) -> dict:
    """Compute Mann-Whitney U test and summary statistics."""
    max_iter = df["iteration"].max()
    final = df[df["iteration"] == max_iter]

    treatment = final[final["condition"] == "treatment"]["best_combined_score"]
    control = final[final["condition"] == "control"]["best_combined_score"]

    stats = {
        "treatment_median": float(treatment.median()),
        "treatment_iqr": float(treatment.quantile(0.75) - treatment.quantile(0.25)),
        "control_median": float(control.median()),
        "control_iqr": float(control.quantile(0.75) - control.quantile(0.25)),
        "n_treatment": len(treatment),
        "n_control": len(control),
    }

    if len(treatment) >= 3 and len(control) >= 3:
        u_stat, p_value = mannwhitneyu(treatment, control, alternative="greater")
        stats["mann_whitney_u"] = float(u_stat)
        stats["p_value"] = float(p_value)
        # Rank-biserial correlation
        n1, n2 = len(treatment), len(control)
        stats["rank_biserial_r"] = 2 * u_stat / (n1 * n2) - 1

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to convergence.csv")
    parser.add_argument("--output", required=True, help="Output directory for plots")
    parser.add_argument("--title", default="", help="Title suffix for plots")
    args = parser.parse_args()

    df = load_data(args.data)
    output_dir = Path(args.output)

    print(f"Loaded {len(df)} data points")
    print(f"Conditions: {df['condition'].unique()}")
    print(f"Seeds: {df['seed'].unique()}")
    print(f"Iterations: {sorted(df['iteration'].unique())}")

    plot_convergence_curves(df, output_dir, args.title)
    plot_final_scores_boxplot(df, output_dir)

    stats = compute_statistics(df)
    print("\n=== Statistical Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    import json
    with open(output_dir / "statistics.json", "w") as f:
        json.dump(stats, f, indent=2)


if __name__ == "__main__":
    main()
```

**Step 2: Verify script parses correctly**

Run: `python scripts/analyze_experiment.py --help`
Expected: Shows usage information

**Step 3: Commit**

```bash
git add scripts/analyze_experiment.py
git commit -m "feat: add experiment analysis script with convergence plots and statistics"
```

---

### Task 9: End-to-End Pilot Validation

Verify the full pipeline works before running the real experiment.

**Step 1: Run 1 treatment pilot (function_minimization, fast)**

```bash
python openevolve-run.py \
  examples/function_minimization/initial_program.py \
  examples/function_minimization/evaluator.py \
  --config examples/function_minimization/config_experiment_treatment.yaml \
  --iterations 3
```

Expected: Completes without errors, hypothesis_ledger.json and hypothesis_knowledge_base artifacts created.

**Step 2: Run 1 control pilot**

```bash
python openevolve-run.py \
  examples/function_minimization/initial_program.py \
  examples/function_minimization/evaluator.py \
  --config examples/function_minimization/config_experiment_control.yaml \
  --iterations 3
```

Expected: Completes without errors, no hypothesis artifacts.

**Step 3: Verify experiment runner collects data**

```bash
python scripts/run_experiment.py \
  --task function_minimization \
  --condition both \
  --runs 1 \
  --seed-start 42 \
  --output-dir experiments/pilot_test
```

Expected: convergence.csv and run_results.json created.

**Step 4: Verify analysis produces plots**

```bash
python scripts/analyze_experiment.py \
  --data experiments/pilot_test/convergence.csv \
  --output experiments/pilot_test/plots/
```

Expected: convergence_curves.png and final_scores_boxplot.png created.

**Step 5: Clean up pilot data and commit**

```bash
rm -rf experiments/pilot_test
git add -A
git commit -m "chore: validate experiment pipeline end-to-end"
```

---

### Task 10: Run Full Experiment

**Step 1: Run BLIS router experiment**

```bash
python scripts/run_experiment.py \
  --task blis_router \
  --condition both \
  --runs 5 \
  --seed-start 100 \
  --output-dir experiments/hypothesis_ab_blis
```

**Step 2: Run function minimization experiment**

```bash
python scripts/run_experiment.py \
  --task function_minimization \
  --condition both \
  --runs 5 \
  --seed-start 100 \
  --output-dir experiments/hypothesis_ab_funcmin
```

**Step 3: Analyze both**

```bash
python scripts/analyze_experiment.py \
  --data experiments/hypothesis_ab_blis/convergence.csv \
  --output experiments/hypothesis_ab_blis/plots/ \
  --title " (BLIS Router)"

python scripts/analyze_experiment.py \
  --data experiments/hypothesis_ab_funcmin/convergence.csv \
  --output experiments/hypothesis_ab_funcmin/plots/ \
  --title " (Function Minimization)"
```

**Step 4: Review results and commit**

```bash
git add experiments/
git commit -m "results: hypothesis A/B experiment data and analysis"
```
