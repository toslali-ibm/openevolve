# Hypothesis-Driven Evolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add hypothesis-driven feedback to the BLIS router evaluator so the LLM writes testable predictions alongside code, and receives structured confirmed/refuted signals via artifacts.

**Architecture:** New `hypothesis.py` module in `examples/blis_router/` contains all hypothesis logic (parsing, testing, ledger, summary generation). `evaluator.py` imports and calls these functions. `config.yaml` system_message gets hypothesis instructions. Zero OpenEvolve core changes.

**Tech Stack:** Python 3.10+, regex parsing, JSON file I/O, existing OpenEvolve artifact pipeline.

**Design doc:** `docs/plans/2026-02-23-hypothesis-driven-evolution-design.md`

---

### Task 1: Hypothesis Parsing

**Files:**
- Create: `examples/blis_router/hypothesis.py`
- Test: `tests/test_blis_hypothesis.py`

**Step 1: Write failing tests for parse_hypotheses**

```python
# tests/test_blis_hypothesis.py
import sys
import os
import unittest

# Add examples/blis_router to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'examples', 'blis_router'))

from hypothesis import parse_hypotheses


class TestParseHypotheses(unittest.TestCase):

    def test_single_hypothesis(self):
        go_code = """
// EVOLVE-BLOCK-START
// HYPOTHESIS-1: Cache affinity boost helps large requests
// MECHANISM-1: Large prefix means more KV blocks to reuse
// EXPECT-1: prefix_caching_e2e_ms < 235

scores := make(map[string]float64, len(snapshots))
// EVOLVE-BLOCK-END
"""
        result = parse_hypotheses(go_code)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['id'], 1)
        self.assertEqual(result[0]['claim'], 'Cache affinity boost helps large requests')
        self.assertEqual(result[0]['mechanism'], 'Large prefix means more KV blocks to reuse')
        self.assertEqual(result[0]['metric'], 'prefix_caching_e2e_ms')
        self.assertAlmostEqual(result[0]['threshold'], 235.0)

    def test_multiple_hypotheses(self):
        go_code = """
// HYPOTHESIS-1: Cache boost for large requests
// MECHANISM-1: More KV blocks to reuse
// EXPECT-1: prefix_caching_e2e_ms < 235

// HYPOTHESIS-2: Queue penalty for realtime
// MECHANISM-2: Realtime SLO needs low queue depth
// EXPECT-2: signal_freshness_e2e_ms < 175
"""
        result = parse_hypotheses(go_code)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['metric'], 'prefix_caching_e2e_ms')
        self.assertEqual(result[1]['metric'], 'signal_freshness_e2e_ms')

    def test_no_hypotheses(self):
        go_code = """
scores := make(map[string]float64, len(snapshots))
for i, scorer := range ws.scorers {
    dimScores := scorer(req, snapshots)
}
"""
        result = parse_hypotheses(go_code)
        self.assertEqual(len(result), 0)

    def test_incomplete_hypothesis_missing_expect(self):
        go_code = """
// HYPOTHESIS-1: Some claim
// MECHANISM-1: Some mechanism
// No EXPECT line
"""
        result = parse_hypotheses(go_code)
        self.assertEqual(len(result), 0)

    def test_multiline_mechanism(self):
        go_code = """
// HYPOTHESIS-1: Cache affinity boost
// MECHANISM-1: Requests with >400 tokens have more KV cache blocks
//   to reuse, so routing to high-CacheHitRate instances helps
// EXPECT-1: prefix_caching_e2e_ms < 235
"""
        result = parse_hypotheses(go_code)
        self.assertEqual(len(result), 1)
        self.assertIn('400 tokens', result[0]['mechanism'])

    def test_threshold_with_decimal(self):
        go_code = """
// HYPOTHESIS-1: Some claim
// MECHANISM-1: Some mechanism
// EXPECT-1: avg_e2e_ms < 192.5
"""
        result = parse_hypotheses(go_code)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]['threshold'], 192.5)


if __name__ == '__main__':
    unittest.main()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_blis_hypothesis.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'hypothesis'`

**Step 3: Implement parse_hypotheses**

```python
# examples/blis_router/hypothesis.py
"""
Hypothesis-driven evolution support for BLIS router evaluator.

Parses structured hypothesis comments from Go code, tests predictions
against evaluation results, and maintains a persistent knowledge base
of confirmed/refuted strategies across iterations.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Valid metrics that can appear in EXPECT lines
VALID_METRICS = {
    'prefix_caching_e2e_ms',
    'signal_freshness_e2e_ms',
    'multiturn_affinity_e2e_ms',
    'sjf_bimodal_e2e_ms',
    'combined_stress_e2e_ms',
    'avg_e2e_ms',
    'avg_p95_ms',
}


def parse_hypotheses(go_code: str) -> list:
    """Parse HYPOTHESIS/MECHANISM/EXPECT comment blocks from Go code.

    Returns list of dicts with keys: id, claim, mechanism, metric, threshold.
    Only returns hypotheses that have all required fields (claim + metric + threshold).
    """
    hypotheses = {}  # keyed by N

    for line in go_code.split('\n'):
        stripped = line.strip()

        # HYPOTHESIS-N: <claim>
        m = re.match(r'//\s*HYPOTHESIS-(\d+):\s*(.+)', stripped)
        if m:
            n = int(m.group(1))
            if n not in hypotheses:
                hypotheses[n] = {'id': n}
            hypotheses[n]['claim'] = m.group(2).strip()
            continue

        # MECHANISM-N: <text> (first line only; continuation lines are appended)
        m = re.match(r'//\s*MECHANISM-(\d+):\s*(.+)', stripped)
        if m:
            n = int(m.group(1))
            if n not in hypotheses:
                hypotheses[n] = {'id': n}
            hypotheses[n]['mechanism'] = m.group(2).strip()
            hypotheses[n]['_reading_mechanism'] = True
            continue

        # EXPECT-N: <metric> < <threshold>
        m = re.match(r'//\s*EXPECT-(\d+):\s*(\w+)\s*<\s*([\d.]+)', stripped)
        if m:
            n = int(m.group(1))
            if n not in hypotheses:
                hypotheses[n] = {'id': n}
            hypotheses[n]['metric'] = m.group(2).strip()
            hypotheses[n]['threshold'] = float(m.group(3))
            # Stop reading mechanism continuation
            for h in hypotheses.values():
                h.pop('_reading_mechanism', None)
            continue

        # Mechanism continuation line: //   <more text>
        m = re.match(r'//\s{2,}(.+)', stripped)
        if m:
            for h in hypotheses.values():
                if h.get('_reading_mechanism'):
                    h['mechanism'] = h.get('mechanism', '') + ' ' + m.group(1).strip()
            continue

    # Clean up and return only complete hypotheses
    result = []
    for n in sorted(hypotheses.keys()):
        h = hypotheses[n]
        h.pop('_reading_mechanism', None)
        if 'claim' in h and 'metric' in h and 'threshold' in h:
            if 'mechanism' not in h:
                h['mechanism'] = ''
            result.append(h)

    return result
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_blis_hypothesis.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add examples/blis_router/hypothesis.py tests/test_blis_hypothesis.py
git commit -m "feat(blis): add hypothesis parsing from Go comments"
```

---

### Task 2: Hypothesis Testing

**Files:**
- Modify: `examples/blis_router/hypothesis.py`
- Modify: `tests/test_blis_hypothesis.py`

**Step 1: Write failing tests for test_hypotheses**

Append to `tests/test_blis_hypothesis.py`:

```python
from hypothesis import test_hypotheses


class TestTestHypotheses(unittest.TestCase):

    def test_confirmed(self):
        hypotheses = [{'id': 1, 'claim': 'Cache helps', 'mechanism': 'Reuse',
                       'metric': 'prefix_caching_e2e_ms', 'threshold': 235}]
        actuals = {'prefix_caching_e2e_ms': 228.4}
        baseline = {'prefix_caching_e2e_ms': 248.5}

        results = test_hypotheses(hypotheses, actuals, baseline)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['verdict'], 'CONFIRMED')
        self.assertAlmostEqual(results[0]['actual'], 228.4)
        self.assertLess(results[0]['delta_vs_baseline_pct'], 0)  # Improved

    def test_refuted(self):
        hypotheses = [{'id': 1, 'claim': 'Queue penalty', 'mechanism': 'Less wait',
                       'metric': 'signal_freshness_e2e_ms', 'threshold': 175}]
        actuals = {'signal_freshness_e2e_ms': 193.7}
        baseline = {'signal_freshness_e2e_ms': 188.2}

        results = test_hypotheses(hypotheses, actuals, baseline)
        self.assertEqual(results[0]['verdict'], 'REFUTED')
        self.assertGreater(results[0]['delta_vs_baseline_pct'], 0)  # Regressed

    def test_inconclusive_missing_metric(self):
        hypotheses = [{'id': 1, 'claim': 'Some claim', 'mechanism': 'Some mech',
                       'metric': 'sjf_bimodal_e2e_ms', 'threshold': 200}]
        actuals = {}  # Workload failed, no metric
        baseline = {'sjf_bimodal_e2e_ms': 210.0}

        results = test_hypotheses(hypotheses, actuals, baseline)
        self.assertEqual(results[0]['verdict'], 'INCONCLUSIVE')

    def test_multiple_hypotheses_mixed(self):
        hypotheses = [
            {'id': 1, 'claim': 'H1', 'mechanism': 'M1',
             'metric': 'prefix_caching_e2e_ms', 'threshold': 235},
            {'id': 2, 'claim': 'H2', 'mechanism': 'M2',
             'metric': 'signal_freshness_e2e_ms', 'threshold': 175},
        ]
        actuals = {'prefix_caching_e2e_ms': 220, 'signal_freshness_e2e_ms': 190}
        baseline = {'prefix_caching_e2e_ms': 248, 'signal_freshness_e2e_ms': 188}

        results = test_hypotheses(hypotheses, actuals, baseline)
        self.assertEqual(results[0]['verdict'], 'CONFIRMED')
        self.assertEqual(results[1]['verdict'], 'REFUTED')
```

**Step 2: Run tests to verify new tests fail**

Run: `python -m pytest tests/test_blis_hypothesis.py::TestTestHypotheses -v`
Expected: FAIL with `ImportError`

**Step 3: Implement test_hypotheses**

Append to `examples/blis_router/hypothesis.py`:

```python
def test_hypotheses(hypotheses: list, actual_metrics: dict, baseline_metrics: dict) -> list:
    """Test each hypothesis against actual evaluation results and baseline.

    Returns list of dicts with keys: id, claim, mechanism, metric, threshold,
    actual, baseline_value, delta_vs_baseline_pct, verdict.
    """
    results = []
    for h in hypotheses:
        metric = h['metric']
        threshold = h['threshold']

        actual = actual_metrics.get(metric)
        baseline_val = baseline_metrics.get(metric)

        if actual is None:
            verdict = 'INCONCLUSIVE'
            delta_pct = None
        else:
            verdict = 'CONFIRMED' if actual < threshold else 'REFUTED'
            if baseline_val and baseline_val != 0:
                delta_pct = round((actual - baseline_val) / baseline_val * 100, 1)
            else:
                delta_pct = None

        results.append({
            'id': h['id'],
            'claim': h['claim'],
            'mechanism': h.get('mechanism', ''),
            'metric': metric,
            'threshold': threshold,
            'actual': actual,
            'baseline_value': baseline_val,
            'delta_vs_baseline_pct': delta_pct,
            'verdict': verdict,
        })

    return results
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_blis_hypothesis.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add examples/blis_router/hypothesis.py tests/test_blis_hypothesis.py
git commit -m "feat(blis): add hypothesis testing against baseline"
```

---

### Task 3: Ledger Operations

**Files:**
- Modify: `examples/blis_router/hypothesis.py`
- Modify: `tests/test_blis_hypothesis.py`

**Step 1: Write failing tests for ledger load/update**

Append to `tests/test_blis_hypothesis.py`:

```python
import tempfile
from hypothesis import load_ledger, update_ledger


class TestLedger(unittest.TestCase):

    def test_load_empty_ledger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = load_ledger(path)
            self.assertEqual(ledger['baseline'], {})
            self.assertEqual(ledger['entries'], [])

    def test_load_existing_ledger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            data = {"baseline": {"avg_e2e_ms": 200}, "entries": [{"verdict": "CONFIRMED"}]}
            path.write_text(json.dumps(data))
            ledger = load_ledger(path)
            self.assertEqual(ledger['baseline']['avg_e2e_ms'], 200)
            self.assertEqual(len(ledger['entries']), 1)

    def test_update_ledger_appends(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = {"baseline": {}, "entries": []}
            hypothesis_results = [
                {'id': 1, 'claim': 'H1', 'mechanism': 'M1', 'metric': 'avg_e2e_ms',
                 'threshold': 200, 'actual': 195, 'baseline_value': 210,
                 'delta_vs_baseline_pct': -7.1, 'verdict': 'CONFIRMED'}
            ]
            updated = update_ledger(ledger, hypothesis_results, -205.3, path)
            self.assertEqual(len(updated['entries']), 1)
            self.assertEqual(updated['entries'][0]['verdict'], 'CONFIRMED')
            self.assertEqual(updated['entries'][0]['overall_combined_score'], -205.3)
            # Verify persisted to disk
            reloaded = json.loads(path.read_text())
            self.assertEqual(len(reloaded['entries']), 1)

    def test_update_ledger_accumulates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = {"baseline": {}, "entries": [{"verdict": "REFUTED", "metric": "x"}]}
            hypothesis_results = [
                {'id': 1, 'claim': 'H1', 'mechanism': 'M1', 'metric': 'avg_e2e_ms',
                 'threshold': 200, 'actual': 195, 'baseline_value': 210,
                 'delta_vs_baseline_pct': -7.1, 'verdict': 'CONFIRMED'}
            ]
            updated = update_ledger(ledger, hypothesis_results, -205.3, path)
            self.assertEqual(len(updated['entries']), 2)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_blis_hypothesis.py::TestLedger -v`
Expected: FAIL with `ImportError`

**Step 3: Implement load_ledger and update_ledger**

Append to `examples/blis_router/hypothesis.py`:

```python
def load_ledger(ledger_path: Path) -> dict:
    """Load hypothesis ledger from disk, or return empty ledger."""
    if ledger_path.exists():
        return json.loads(ledger_path.read_text())
    return {"baseline": {}, "entries": []}


def update_ledger(ledger: dict, hypothesis_results: list,
                  overall_combined_score: float, ledger_path: Path) -> dict:
    """Append hypothesis results to ledger and persist to disk."""
    timestamp = datetime.now().isoformat()
    for r in hypothesis_results:
        ledger["entries"].append({
            "timestamp": timestamp,
            "hypothesis": r['claim'],
            "mechanism": r['mechanism'],
            "metric": r['metric'],
            "threshold": r['threshold'],
            "actual": r['actual'],
            "baseline_value": r['baseline_value'],
            "delta_vs_baseline_pct": r['delta_vs_baseline_pct'],
            "verdict": r['verdict'],
            "overall_combined_score": overall_combined_score,
        })
    ledger_path.write_text(json.dumps(ledger, indent=2))
    return ledger
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_blis_hypothesis.py -v`
Expected: All 14 tests PASS

**Step 5: Commit**

```bash
git add examples/blis_router/hypothesis.py tests/test_blis_hypothesis.py
git commit -m "feat(blis): add hypothesis ledger persistence"
```

---

### Task 4: Knowledge Base Summary Generation

**Files:**
- Modify: `examples/blis_router/hypothesis.py`
- Modify: `tests/test_blis_hypothesis.py`

**Step 1: Write failing tests for generate_knowledge_base_summary**

Append to `tests/test_blis_hypothesis.py`:

```python
from hypothesis import generate_knowledge_base_summary


class TestKnowledgeBaseSummary(unittest.TestCase):

    def test_empty_ledger(self):
        ledger = {"baseline": {"avg_e2e_ms": 200}, "entries": []}
        summary = generate_knowledge_base_summary(ledger)
        self.assertIn("HYPOTHESIS KNOWLEDGE BASE", summary)
        self.assertIn("No hypothesis data yet", summary)

    def test_confirmed_strategies_shown(self):
        ledger = {
            "baseline": {"prefix_caching_e2e_ms": 248.5},
            "entries": [
                {"metric": "prefix_caching_e2e_ms", "verdict": "CONFIRMED",
                 "delta_vs_baseline_pct": -8.1, "actual": 228.4,
                 "baseline_value": 248.5, "hypothesis": "cache boost",
                 "mechanism": "reuse blocks"},
                {"metric": "prefix_caching_e2e_ms", "verdict": "CONFIRMED",
                 "delta_vs_baseline_pct": -6.2, "actual": 233.1,
                 "baseline_value": 248.5, "hypothesis": "cache boost v2",
                 "mechanism": "reuse blocks"},
            ]
        }
        summary = generate_knowledge_base_summary(ledger)
        self.assertIn("CONFIRMED STRATEGIES", summary)
        self.assertIn("prefix_caching_e2e_ms", summary)
        self.assertIn("2/2 confirmed", summary)

    def test_refuted_strategies_shown(self):
        ledger = {
            "baseline": {"signal_freshness_e2e_ms": 188.2},
            "entries": [
                {"metric": "signal_freshness_e2e_ms", "verdict": "REFUTED",
                 "delta_vs_baseline_pct": 2.9, "actual": 193.7,
                 "baseline_value": 188.2, "hypothesis": "queue penalty",
                 "mechanism": "less wait"},
                {"metric": "signal_freshness_e2e_ms", "verdict": "REFUTED",
                 "delta_vs_baseline_pct": 3.8, "actual": 195.3,
                 "baseline_value": 188.2, "hypothesis": "queue penalty v2",
                 "mechanism": "less wait"},
            ]
        }
        summary = generate_knowledge_base_summary(ledger)
        self.assertIn("REFUTED STRATEGIES", summary)
        self.assertIn("0/2 confirmed", summary)

    def test_top_n_limits_output(self):
        ledger = {
            "baseline": {},
            "entries": [
                {"metric": f"metric_{i}", "verdict": "CONFIRMED",
                 "delta_vs_baseline_pct": -i, "actual": 100 - i,
                 "baseline_value": 100, "hypothesis": f"h{i}",
                 "mechanism": f"m{i}"}
                for i in range(10)
            ]
        }
        summary = generate_knowledge_base_summary(ledger, top_n=3)
        # Should only show top 3 confirmed metrics
        confirmed_section = summary.split("CONFIRMED STRATEGIES")[1] if "CONFIRMED" in summary else ""
        metric_count = sum(1 for line in confirmed_section.split('\n') if 'metric_' in line and 'confirmed' in line)
        self.assertLessEqual(metric_count, 3)

    def test_baseline_values_shown(self):
        ledger = {
            "baseline": {"avg_e2e_ms": 200.5, "avg_p95_ms": 350.2},
            "entries": []
        }
        summary = generate_knowledge_base_summary(ledger)
        self.assertIn("BASELINE", summary)
        self.assertIn("200.5", summary)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_blis_hypothesis.py::TestKnowledgeBaseSummary -v`
Expected: FAIL with `ImportError`

**Step 3: Implement generate_knowledge_base_summary**

Append to `examples/blis_router/hypothesis.py`:

```python
def generate_knowledge_base_summary(ledger: dict, top_n: int = 5) -> str:
    """Generate a text summary of the hypothesis knowledge base.

    Groups entries by target metric, classifies as confirmed/refuted/inconclusive,
    and returns a formatted summary with top N of each category.
    """
    entries = ledger.get("entries", [])
    baseline = ledger.get("baseline", {})

    lines = ["HYPOTHESIS KNOWLEDGE BASE:", ""]

    if not entries:
        lines.append("No hypothesis data yet. Write hypotheses to start building the knowledge base.")
        lines.append("")
        if baseline:
            lines.append("BASELINE VALUES (initial program, static weights):")
            for metric, val in sorted(baseline.items()):
                lines.append(f"  {metric}: {val}")
        return "\n".join(lines)

    # Group entries by metric
    by_metric = {}
    for entry in entries:
        metric = entry["metric"]
        if metric not in by_metric:
            by_metric[metric] = []
        by_metric[metric].append(entry)

    confirmed_metrics = []
    refuted_metrics = []
    inconclusive_metrics = []

    for metric, metric_entries in by_metric.items():
        total = len(metric_entries)
        confirmed = sum(1 for e in metric_entries if e["verdict"] == "CONFIRMED")

        deltas = [e["delta_vs_baseline_pct"] for e in metric_entries
                  if e.get("delta_vs_baseline_pct") is not None]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0

        actuals = [e["actual"] for e in metric_entries if e.get("actual") is not None]
        best_actual = min(actuals) if actuals else None
        baseline_val = metric_entries[0].get("baseline_value")

        info = {
            "metric": metric,
            "confirmed": confirmed,
            "total": total,
            "avg_delta_pct": round(avg_delta, 1),
            "best_actual": best_actual,
            "baseline_value": baseline_val,
        }

        confirm_rate = confirmed / total if total > 0 else 0
        if confirm_rate >= 0.5:
            confirmed_metrics.append(info)
        elif total >= 2:
            refuted_metrics.append(info)
        else:
            inconclusive_metrics.append(info)

    # Sort: confirmed by best avg_delta (most negative first), refuted by worst
    confirmed_metrics.sort(key=lambda x: x["avg_delta_pct"])
    refuted_metrics.sort(key=lambda x: x["avg_delta_pct"], reverse=True)

    if confirmed_metrics:
        lines.append("CONFIRMED STRATEGIES (build on these):")
        for info in confirmed_metrics[:top_n]:
            lines.append(f"  {info['metric']}:")
            lines.append(f"    - {info['confirmed']}/{info['total']} confirmed, avg improvement {info['avg_delta_pct']}%")
            if info['best_actual'] is not None and info['baseline_value'] is not None:
                lines.append(f"    - Best achieved: {info['best_actual']:.1f}ms (baseline: {info['baseline_value']:.1f}ms)")
        lines.append("")

    if refuted_metrics:
        lines.append("REFUTED STRATEGIES (avoid these):")
        for info in refuted_metrics[:top_n]:
            lines.append(f"  {info['metric']}:")
            lines.append(f"    - {info['confirmed']}/{info['total']} confirmed, avg delta {info['avg_delta_pct']}%")
        lines.append("")

    if inconclusive_metrics:
        lines.append("INCONCLUSIVE (not enough data):")
        for info in inconclusive_metrics[:top_n]:
            lines.append(f"  {info['metric']}:")
            lines.append(f"    - {info['confirmed']}/{info['total']} confirmed, needs more trials")
        lines.append("")

    if baseline:
        lines.append("BASELINE VALUES (initial program, static weights):")
        for metric, val in sorted(baseline.items()):
            lines.append(f"  {metric}: {val}")

    return "\n".join(lines)
```

**Step 4: Write format_hypothesis_results helper**

Also append to `examples/blis_router/hypothesis.py`:

```python
def format_hypothesis_results(hypothesis_results: list, overall_score: float,
                              baseline_score: float) -> str:
    """Format this iteration's hypothesis verdicts as human-readable text."""
    lines = []
    for r in hypothesis_results:
        lines.append(f"HYPOTHESIS-{r['id']}: \"{r['claim']}\"")
        lines.append(f"  EXPECT: {r['metric']} < {r['threshold']}")
        if r['actual'] is not None:
            delta_str = ""
            if r['delta_vs_baseline_pct'] is not None:
                sign = "+" if r['delta_vs_baseline_pct'] >= 0 else ""
                delta_str = f" ({sign}{r['delta_vs_baseline_pct']}% vs baseline of {r['baseline_value']:.1f})"
            lines.append(f"  ACTUAL: {r['metric']} = {r['actual']:.1f}")
            lines.append(f"  VERDICT: {r['verdict']}{delta_str}")
        else:
            lines.append(f"  ACTUAL: metric unavailable (workload failed)")
            lines.append(f"  VERDICT: INCONCLUSIVE")
        lines.append("")

    if baseline_score != 0:
        delta_pct = round((overall_score - baseline_score) / abs(baseline_score) * 100, 1)
        sign = "+" if delta_pct >= 0 else ""
        lines.append(f"OVERALL: combined_score = {overall_score:.1f} (baseline = {baseline_score:.1f}, delta = {sign}{delta_pct}%)")
    else:
        lines.append(f"OVERALL: combined_score = {overall_score:.1f}")

    return "\n".join(lines)
```

**Step 5: Run all tests**

Run: `python -m pytest tests/test_blis_hypothesis.py -v`
Expected: All 19 tests PASS

**Step 6: Commit**

```bash
git add examples/blis_router/hypothesis.py tests/test_blis_hypothesis.py
git commit -m "feat(blis): add knowledge base summary and result formatting"
```

---

### Task 5: Baseline Caching in Evaluator

**Files:**
- Modify: `examples/blis_router/evaluator.py:74-100` (add baseline logic near top of evaluate)

**Step 1: Add get_or_compute_baseline function to evaluator.py**

Add after the `extract_go_code` function (after line 71):

```python
def get_or_compute_baseline(script_dir: Path, inference_sim_dir: Path,
                            policy_config_path: Path) -> dict:
    """Get baseline metrics from cache, or compute by evaluating initial program.

    Runs the initial program (static weights) through all workloads once,
    caches results to baseline_metrics.json for future evaluations.
    """
    cache_path = script_dir / "baseline_metrics.json"
    if cache_path.exists():
        logger.info("Loading cached baseline metrics")
        return json.loads(cache_path.read_text())

    logger.info("Computing baseline metrics from initial program (first run only)...")

    # Write initial program's Go code to routing.go
    initial_program_path = script_dir / "initial_program.py"
    with open(initial_program_path, 'r') as f:
        initial_text = f.read()
    initial_go_code = extract_go_code(initial_text)

    with open(inference_sim_dir / "sim" / "routing.go", 'w') as f:
        f.write(initial_go_code)

    # Build
    result = subprocess.run(
        ["go", "build", "-o", "simulation_worker", "main.go"],
        cwd=inference_sim_dir, capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        logger.error(f"Baseline build failed: {result.stderr}")
        return {}

    # Run all workloads (reuse same workload list and parsing as evaluate())
    baseline = {}
    workloads = [
        ("signal_freshness", "workload_signal_freshness.yaml"),
        ("prefix_caching", "workload_prefix_caching.yaml"),
        ("multiturn_affinity", "workload_multiturn_affinity.yaml"),
        ("sjf_bimodal", "workload_sjf_bimodal.yaml"),
        ("combined_stress", "workload_combined_stress.yaml"),
    ]
    latencies = []
    tail_latencies = []

    for workload_name, workload_file in workloads:
        workload_path = script_dir / workload_file
        cmd = [
            "./simulation_worker", "run",
            "--model", "Qwen/Qwen2.5-7B-Instruct",
            "--hardware", "H100", "--tp", "1", "--num-instances", "4",
            "--policy-config", str(policy_config_path),
            "--workload-spec", str(workload_path),
            "--log", "info",
            "--alpha-coeffs", "4680.303204056608,0.0,0.0",
            "--beta-coeffs", "7051.796874715078,19.538416565504026,25.431830886933543",
            "--total-kv-blocks", "65833",
            "--max-num-running-reqs", "256",
            "--max-num-scheduled-tokens", "4096",
        ]
        try:
            sim_result = subprocess.run(
                cmd, cwd=inference_sim_dir, capture_output=True,
                text=True, timeout=120
            )
            if sim_result.returncode == 0:
                cluster_metrics = _parse_cluster_metrics(sim_result.stdout + (sim_result.stderr or ""))
                if cluster_metrics:
                    e2e_ms = float(cluster_metrics["e2e_mean_ms"])
                    e2e_p95 = float(cluster_metrics.get("e2e_p95_ms", e2e_ms))
                    baseline[f"{workload_name}_e2e_ms"] = e2e_ms
                    latencies.append(e2e_ms)
                    tail_latencies.append(e2e_p95)
                    logger.info(f"Baseline {workload_name}: {e2e_ms:.1f}ms")
        except Exception as e:
            logger.error(f"Baseline {workload_name} failed: {e}")

    if latencies:
        baseline["avg_e2e_ms"] = sum(latencies) / len(latencies)
        baseline["avg_p95_ms"] = sum(tail_latencies) / len(tail_latencies)
        baseline["combined_score"] = -0.5 * baseline["avg_e2e_ms"] - 0.5 * baseline["avg_p95_ms"]

    cache_path.write_text(json.dumps(baseline, indent=2))
    logger.info(f"Baseline cached to {cache_path}: {baseline}")
    return baseline
```

**Step 2: Extract _parse_cluster_metrics helper**

Extract the JSON parsing logic (currently lines 284-320 in evaluate()) into a reusable function. Add before `get_or_compute_baseline`:

```python
def _parse_cluster_metrics(output_text: str) -> dict:
    """Parse cluster-wide metrics from simulation output JSON blocks."""
    json_blocks = []
    in_json = False
    json_buffer = ""
    brace_count = 0

    for line in output_text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('{'):
            in_json = True
            brace_count = 0
        if in_json:
            json_buffer += line + '\n'
            brace_count += stripped.count('{') - stripped.count('}')
            if brace_count == 0 and json_buffer.strip():
                try:
                    json_blocks.append(json.loads(json_buffer))
                except json.JSONDecodeError:
                    pass
                json_buffer = ""
                in_json = False

    for block in json_blocks:
        if block.get("instance_id") == "cluster":
            return block
    return None
```

**Step 3: Run existing tests to verify no regression**

Run: `python -m unittest discover tests -v 2>&1 | tail -5`
Expected: No regressions

**Step 4: Commit**

```bash
git add examples/blis_router/evaluator.py
git commit -m "feat(blis): add baseline caching and extract JSON parsing helper"
```

---

### Task 6: Integrate Hypothesis Pipeline into evaluate()

**Files:**
- Modify: `examples/blis_router/evaluator.py:74-455` (the evaluate function)

**Step 1: Add imports at top of evaluator.py**

After existing imports (line 24), add:

```python
from hypothesis import (
    parse_hypotheses, test_hypotheses, load_ledger, update_ledger,
    generate_knowledge_base_summary, format_hypothesis_results,
)
```

**Step 2: Add baseline + hypothesis parsing early in evaluate()**

After the "Step 1: Extract Go code" block (after line 130), add:

```python
    # Step 1b: Get baseline metrics and parse hypotheses
    baseline_metrics = get_or_compute_baseline(script_dir, inference_sim_dir, policy_config_path)
    hypotheses = parse_hypotheses(go_code)
    if hypotheses:
        logger.info(f"Parsed {len(hypotheses)} hypotheses from evolved code")
        for h in hypotheses:
            logger.info(f"  H{h['id']}: {h['claim']} (EXPECT: {h['metric']} < {h['threshold']})")
    else:
        logger.info("No hypotheses found in evolved code")
```

**Step 3: Add hypothesis testing after workload loop**

After the score computation (after line 409 `score = -0.5 * avg_latency - 0.5 * avg_tail_latency`), add:

```python
    # Step 5b: Test hypotheses and update ledger
    hypothesis_results_text = ""
    knowledge_base_text = ""
    if hypotheses:
        # Build actual metrics dict matching EXPECT metric names
        actual_for_hypothesis = {
            "prefix_caching_e2e_ms": workload_results.get("prefix_caching", {}).get("e2e_ms"),
            "signal_freshness_e2e_ms": workload_results.get("signal_freshness", {}).get("e2e_ms"),
            "multiturn_affinity_e2e_ms": workload_results.get("multiturn_affinity", {}).get("e2e_ms"),
            "sjf_bimodal_e2e_ms": workload_results.get("sjf_bimodal", {}).get("e2e_ms"),
            "combined_stress_e2e_ms": workload_results.get("combined_stress", {}).get("e2e_ms"),
            "avg_e2e_ms": avg_latency if latencies else None,
            "avg_p95_ms": avg_tail_latency if tail_latencies else None,
        }
        # Remove None values
        actual_for_hypothesis = {k: v for k, v in actual_for_hypothesis.items() if v is not None}

        h_results = test_hypotheses(hypotheses, actual_for_hypothesis, baseline_metrics)

        # Format results for this iteration
        baseline_score = baseline_metrics.get("combined_score", 0)
        hypothesis_results_text = format_hypothesis_results(h_results, score, baseline_score)
        logger.info(f"Hypothesis results:\n{hypothesis_results_text}")

        # Update ledger
        ledger_path = script_dir / "hypothesis_ledger.json"
        ledger = load_ledger(ledger_path)
        if not ledger["baseline"] and baseline_metrics:
            ledger["baseline"] = baseline_metrics
        update_ledger(ledger, h_results, score, ledger_path)

        # Generate knowledge base summary
        knowledge_base_text = generate_knowledge_base_summary(ledger)
    else:
        # Still show knowledge base even if this iteration has no hypotheses
        ledger_path = script_dir / "hypothesis_ledger.json"
        if ledger_path.exists():
            ledger = load_ledger(ledger_path)
            knowledge_base_text = generate_knowledge_base_summary(ledger)
```

**Step 4: Add hypothesis artifacts to the return value**

In the artifacts dict (around line 425), add the new keys:

```python
    if hypothesis_results_text:
        artifacts["hypothesis_results"] = hypothesis_results_text
    if knowledge_base_text:
        artifacts["hypothesis_knowledge_base"] = knowledge_base_text
```

**Step 5: Replace inline JSON parsing with _parse_cluster_metrics call**

In the workload loop (around line 284), replace the inline JSON parsing block with:

```python
                cluster_metrics = _parse_cluster_metrics(result.stdout + (result.stderr or ""))
                if cluster_metrics and "e2e_mean_ms" in cluster_metrics:
                    e2e_ms = float(cluster_metrics["e2e_mean_ms"])
                    # ... rest of existing metric extraction stays the same
```

**Step 6: Run all tests**

Run: `python -m pytest tests/test_blis_hypothesis.py -v && python -m unittest discover tests -v 2>&1 | tail -5`
Expected: All tests PASS, no regressions

**Step 7: Commit**

```bash
git add examples/blis_router/evaluator.py
git commit -m "feat(blis): integrate hypothesis pipeline into evaluate()"
```

---

### Task 7: Update System Prompt in config.yaml

**Files:**
- Modify: `examples/blis_router/config.yaml:80-188` (system_message section)

**Step 1: Add hypothesis instructions to system_message**

Append to the end of the `system_message` block in `config.yaml` (before `num_top_programs`):

```yaml
    HYPOTHESIS REQUIREMENTS:
    You MUST include at least 1 hypothesis (max 3) as Go comments at the TOP of the EVOLVE-BLOCK,
    BEFORE any code.

    Format (each hypothesis needs all 3 lines):
      // HYPOTHESIS-N: <one-line claim about what will improve and why>
      // MECHANISM-N: <causal explanation - what signal/behavior drives the improvement>
      // EXPECT-N: <metric_name> < <threshold>

    Available metrics for EXPECT (lower = better, use < operator):
      - prefix_caching_e2e_ms: prefix cache reuse workload (rate=500, shared system prompts)
      - signal_freshness_e2e_ms: high-rate load signal freshness (rate=5000)
      - multiturn_affinity_e2e_ms: multi-turn session affinity (rate=5000)
      - sjf_bimodal_e2e_ms: bimodal request size distribution (rate=3000)
      - combined_stress_e2e_ms: all patterns combined (rate=3000)
      - avg_e2e_ms: average across all workloads
      - avg_p95_ms: average p95 tail latency across all workloads

    Hypothesis rules:
      - Set thresholds based on baseline values shown in the HYPOTHESIS KNOWLEDGE BASE artifact
      - Be specific: "helps latency" is too vague;
        "reduces prefix_caching_e2e_ms by routing large-prefix requests to cache-warm instances" is good
      - If a strategy was REFUTED in the knowledge base, explain why your new approach differs
      - Build on CONFIRMED strategies; combine proven techniques
      - If no knowledge base is shown yet (first iteration), set thresholds 5-10% below
        the current metrics shown above

    Example:
    ```go
    // HYPOTHESIS-1: Cache affinity boost helps large-prefix workloads
    // MECHANISM-1: Requests with >400 tokens have more KV cache blocks to reuse
    // EXPECT-1: prefix_caching_e2e_ms < 235
    if len(req.InputTokens) > 400 {
        for _, snap := range snapshots {
            scores[snap.ID] *= (1.0 + snap.CacheHitRate * 0.5)
        }
    }
    ```
```

**Step 2: Verify YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('examples/blis_router/config.yaml'))"`
Expected: No errors

**Step 3: Commit**

```bash
git add examples/blis_router/config.yaml
git commit -m "feat(blis): add hypothesis requirements to system prompt"
```

---

### Task 8: End-to-End Manual Verification

**Step 1: Run evaluator standalone with initial program**

This verifies baseline caching works:

Run: `cd examples/blis_router && python evaluator.py`
Expected:
- "Computing baseline metrics from initial program" on first run
- `baseline_metrics.json` created with per-workload metrics
- "No hypotheses found in evolved code" (initial program has no hypotheses)
- Normal evaluation completes with score

**Step 2: Verify baseline cache is reused on second run**

Run: `cd examples/blis_router && python evaluator.py`
Expected:
- "Loading cached baseline metrics" (uses cache, no re-computation)
- Same results as step 1

**Step 3: Create a test program with hypotheses and verify parsing**

Create a temp test file and run manually to verify hypothesis parsing + testing + ledger update works end-to-end. Verify:
- `hypothesis_ledger.json` created with entries
- Artifacts contain `hypothesis_results` and `hypothesis_knowledge_base`

**Step 4: Run full test suite**

Run: `python -m pytest tests/test_blis_hypothesis.py -v && python -m unittest discover tests`
Expected: All tests PASS

**Step 5: Final commit**

```bash
git add -A examples/blis_router/baseline_metrics.json
git commit -m "feat(blis): add baseline metrics cache (auto-generated)"
```

Add `hypothesis_ledger.json` to `.gitignore` since it's runtime state:

```bash
echo "examples/blis_router/hypothesis_ledger.json" >> .gitignore
git add .gitignore
git commit -m "chore: ignore hypothesis ledger (runtime state)"
```
