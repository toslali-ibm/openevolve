# Hypothesis Pipeline V2: Score-Ranked, Island-Local Knowledge

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the broken aggregation-based hypothesis knowledge base with score-ranked individual hypothesis verdicts, computed fresh at prompt time from an island-local ledger.

**Architecture:** Each evaluator stores only the program's own hypothesis verdicts as an artifact (not the global knowledge base). The ledger entries are tagged with `program_id` and `island`. At prompt time, `iteration.py` / `process_parallel.py` compute a fresh island-local knowledge summary by pulling hypothesis verdicts from the top and worst scoring programs on the current island. The LLM sees two channels: "This parent's hypotheses" + "Strategies from top/worst island programs".

**Tech Stack:** Python, unittest, openevolve framework

---

## Problem Statement

The current `generate_knowledge_base_summary()` aggregates hypotheses by exact `(metric, claim)` string match. Since LLM-generated claims almost never repeat verbatim, every hypothesis has `total=1`, the REFUTED bucket is always empty, and multi-trial aggregation is a dead feature. Additionally, the knowledge base is frozen at parent eval time (stale) and is global (breaks island isolation).

## Design Decisions

1. **Drop aggregation-by-exact-string** — replace with score-ranked individual hypothesis+verdict display
2. **Per-program artifact** — evaluators store `hypothesis_results` (own verdicts only), NOT `hypothesis_knowledge_base`
3. **Island-tagged ledger** — add `program_id` and `island` fields to each ledger entry
4. **Fresh knowledge at prompt time** — move knowledge base generation from evaluator to iteration/worker, compute from ledger filtered by island
5. **Two-channel prompt** — "Parent's hypotheses" from artifact + "Island strategies" from fresh ledger query
6. **Backward compatible** — old ledger entries without island/program_id still load fine

---

### Task 1: Add `generate_island_knowledge_summary()` to hypothesis.py

**Files:**
- Modify: `openevolve/hypothesis.py:270-364`
- Test: `tests/test_hypothesis.py`

This new function replaces `generate_knowledge_base_summary()` (which we keep for backward compat but deprecate). It takes the ledger + a set of top program IDs + a set of worst program IDs and produces score-ranked output.

**Step 1: Write failing tests**

Add to `tests/test_hypothesis.py`:

```python
class TestIslandKnowledgeSummary(unittest.TestCase):
    """Test score-ranked island knowledge summary."""

    def _make_entry(self, program_id, island, score, hypotheses):
        return {
            "program_id": program_id,
            "island": island,
            "overall_combined_score": score,
            "hypotheses": hypotheses,
        }

    def test_empty_ledger(self):
        from openevolve.hypothesis import generate_island_knowledge_summary
        ledger = {"baseline": {}, "entries": []}
        result = generate_island_knowledge_summary(ledger, top_program_ids=set(), worst_program_ids=set())
        self.assertIn("No hypothesis data", result)

    def test_top_programs_shown(self):
        from openevolve.hypothesis import generate_island_knowledge_summary
        ledger = {
            "baseline": {"x": 10.0},
            "entries": [
                self._make_entry("p1", 0, -50.0, [
                    {"id": 1, "claim": "good idea", "mechanism": "works well",
                     "metric": "x", "operator": "<", "threshold": 8.0,
                     "actual": 7.0, "verdict": "CONFIRMED",
                     "delta_vs_baseline_pct": -30.0},
                ]),
                self._make_entry("p2", 0, -80.0, [
                    {"id": 1, "claim": "bad idea", "mechanism": "does not work",
                     "metric": "x", "operator": "<", "threshold": 8.0,
                     "actual": 12.0, "verdict": "REFUTED",
                     "delta_vs_baseline_pct": 20.0},
                ]),
            ],
        }
        result = generate_island_knowledge_summary(
            ledger, top_program_ids={"p1"}, worst_program_ids={"p2"}
        )
        self.assertIn("STRATEGIES FROM TOP-SCORING PROGRAMS", result)
        self.assertIn("good idea", result)
        self.assertIn("CONFIRMED", result)
        self.assertIn("STRATEGIES FROM WORST-SCORING PROGRAMS", result)
        self.assertIn("bad idea", result)
        self.assertIn("REFUTED", result)

    def test_baseline_shown(self):
        from openevolve.hypothesis import generate_island_knowledge_summary
        ledger = {"baseline": {"x": 42.0}, "entries": []}
        result = generate_island_knowledge_summary(ledger, top_program_ids=set(), worst_program_ids=set())
        self.assertIn("42.0", result)

    def test_filters_by_program_ids(self):
        from openevolve.hypothesis import generate_island_knowledge_summary
        ledger = {
            "baseline": {},
            "entries": [
                self._make_entry("p1", 0, -50.0, [
                    {"id": 1, "claim": "from p1", "mechanism": "m",
                     "metric": "x", "operator": "<", "threshold": 8.0,
                     "actual": 7.0, "verdict": "CONFIRMED",
                     "delta_vs_baseline_pct": -10.0},
                ]),
                self._make_entry("p3", 0, -70.0, [
                    {"id": 1, "claim": "from p3", "mechanism": "m",
                     "metric": "x", "operator": "<", "threshold": 8.0,
                     "actual": 9.0, "verdict": "REFUTED",
                     "delta_vs_baseline_pct": 5.0},
                ]),
            ],
        }
        # Only p1 is in top, p3 is not in either set
        result = generate_island_knowledge_summary(
            ledger, top_program_ids={"p1"}, worst_program_ids=set()
        )
        self.assertIn("from p1", result)
        self.assertNotIn("from p3", result)

    def test_respects_top_n_limit(self):
        from openevolve.hypothesis import generate_island_knowledge_summary
        entries = []
        for i in range(10):
            entries.append(self._make_entry(f"p{i}", 0, float(-i), [
                {"id": 1, "claim": f"claim_{i}", "mechanism": "m",
                 "metric": "x", "operator": "<", "threshold": 8.0,
                 "actual": 7.0, "verdict": "CONFIRMED",
                 "delta_vs_baseline_pct": -1.0},
            ]))
        ledger = {"baseline": {}, "entries": entries}
        top_ids = {f"p{i}" for i in range(10)}
        result = generate_island_knowledge_summary(
            ledger, top_program_ids=top_ids, worst_program_ids=set(), top_n=3
        )
        # Should show at most 3 entries from top programs
        count = result.count("[CONFIRMED]")
        self.assertLessEqual(count, 3)
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hypothesis.py::TestIslandKnowledgeSummary -v`
Expected: FAIL (ImportError — `generate_island_knowledge_summary` doesn't exist)

**Step 3: Implement `generate_island_knowledge_summary()`**

Add to `openevolve/hypothesis.py` after `generate_knowledge_base_summary()`:

```python
def generate_island_knowledge_summary(
    ledger: dict,
    top_program_ids: set[str],
    worst_program_ids: set[str],
    top_n: int = 5,
) -> str:
    """Generate score-ranked hypothesis summary from specific programs.

    Instead of aggregating by exact claim string (which never groups in practice),
    this shows individual hypothesis verdicts from the best and worst scoring
    programs on the current island, letting the LLM do pattern recognition.

    Args:
        ledger: Hypothesis ledger dict with 'entries' and 'baseline'.
        top_program_ids: Program IDs of top-scoring island programs.
        worst_program_ids: Program IDs of worst-scoring island programs.
        top_n: Max hypotheses to show per section.

    Returns:
        Formatted text summary for LLM prompt injection.
    """
    entries = ledger.get("entries", [])
    if not entries:
        lines = ["HYPOTHESIS KNOWLEDGE BASE:", "", "No hypothesis data yet."]
        baseline = ledger.get("baseline", {})
        if baseline:
            lines.append("")
            lines.append("=== BASELINE VALUES ===")
            for k, v in sorted(baseline.items()):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    def _format_hypotheses(entry_list, label, n):
        """Format hypothesis verdicts from a list of ledger entries."""
        section_lines = []
        count = 0
        for entry in entry_list:
            for h in entry.get("hypotheses", []):
                if count >= n:
                    break
                verdict = h.get("verdict", "UNKNOWN")
                delta = h.get("delta_vs_baseline_pct")
                delta_str = f", delta={delta:+.1f}% vs baseline" if delta is not None else ""
                op = h.get("operator", "<")
                actual_str = f"{h['actual']:.1f}" if h.get("actual") is not None else "N/A"
                section_lines.append(
                    f"  [{verdict}] {h.get('claim', '?')} "
                    f"(EXPECT {h.get('metric', '?')} {op} {h.get('threshold', '?')}, "
                    f"ACTUAL {actual_str}{delta_str})"
                )
                if h.get("mechanism"):
                    section_lines.append(f"    mechanism: {h['mechanism']}")
                count += 1
            if count >= n:
                break
        if section_lines:
            return [f"=== {label} ==="] + section_lines + [""]
        return []

    # Collect entries by program_id
    top_entries = [e for e in entries if e.get("program_id") in top_program_ids]
    worst_entries = [e for e in entries if e.get("program_id") in worst_program_ids]

    # Sort top entries by score descending (best first)
    top_entries.sort(key=lambda e: e.get("overall_combined_score", float("-inf")), reverse=True)
    # Sort worst entries by score ascending (worst first)
    worst_entries.sort(key=lambda e: e.get("overall_combined_score", float("inf")))

    lines = []
    lines += _format_hypotheses(top_entries, "STRATEGIES FROM TOP-SCORING PROGRAMS", top_n)
    lines += _format_hypotheses(worst_entries, "STRATEGIES FROM WORST-SCORING PROGRAMS", top_n)

    baseline = ledger.get("baseline", {})
    if baseline:
        lines.append("=== BASELINE VALUES ===")
        for k, v in sorted(baseline.items()):
            lines.append(f"  {k}: {v}")
        lines.append("")

    return "\n".join(lines).rstrip() if lines else "No hypothesis data yet."
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hypothesis.py::TestIslandKnowledgeSummary -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add openevolve/hypothesis.py tests/test_hypothesis.py
git commit -m "feat: add generate_island_knowledge_summary() for score-ranked hypothesis display"
```

---

### Task 2: Add `program_id` and `island` fields to ledger entries

**Files:**
- Modify: `openevolve/hypothesis.py:252-267` (update_ledger)
- Test: `tests/test_hypothesis.py`

**Step 1: Write failing tests**

Add to `tests/test_hypothesis.py`:

```python
class TestLedgerIslandFields(unittest.TestCase):
    """Test that ledger entries include program_id and island."""

    def test_update_ledger_with_program_id_and_island(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = load_ledger(path)
            h_results = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x",
                          "threshold": 10.0, "actual": 8.0, "baseline_value": 12.0,
                          "delta_vs_baseline_pct": -33.3, "verdict": "CONFIRMED"}]
            update_ledger(ledger, h_results, -100.0, path, program_id="abc123", island=2)
            reloaded = load_ledger(path)
            entry = reloaded["entries"][0]
            self.assertEqual(entry["program_id"], "abc123")
            self.assertEqual(entry["island"], 2)

    def test_update_ledger_backward_compat_no_program_id(self):
        """Old callers that don't pass program_id/island should still work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = load_ledger(path)
            h_results = [{"id": 1, "claim": "c", "mechanism": "m", "metric": "x",
                          "threshold": 10.0, "actual": 8.0, "baseline_value": 12.0,
                          "delta_vs_baseline_pct": -33.3, "verdict": "CONFIRMED"}]
            update_ledger(ledger, h_results, -100.0, path)
            reloaded = load_ledger(path)
            entry = reloaded["entries"][0]
            self.assertIsNone(entry.get("program_id"))
            self.assertIsNone(entry.get("island"))
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hypothesis.py::TestLedgerIslandFields -v`
Expected: FAIL (`update_ledger` doesn't accept `program_id`/`island` kwargs)

**Step 3: Update `update_ledger()` signature**

In `openevolve/hypothesis.py`, change `update_ledger`:

```python
def update_ledger(
    ledger: dict,
    hypothesis_results: list,
    overall_combined_score: float,
    ledger_path: Path,
    program_id: Optional[str] = None,
    island: Optional[int] = None,
) -> dict:
    """Append hypothesis results to ledger and persist to disk."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_combined_score": overall_combined_score,
        "hypotheses": hypothesis_results,
        "program_id": program_id,
        "island": island,
    }
    ledger["entries"].append(entry)

    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "w") as f:
        json.dump(ledger, f, indent=2)
    return ledger
```

**Step 4: Run tests**

Run: `python -m pytest tests/test_hypothesis.py::TestLedgerIslandFields -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add openevolve/hypothesis.py tests/test_hypothesis.py
git commit -m "feat: add program_id and island fields to hypothesis ledger entries"
```

---

### Task 3: Update evaluators to store own verdicts only (drop knowledge base artifact)

**Files:**
- Modify: `examples/blis_router/evaluator.py:599-644`
- Modify: `examples/function_minimization/evaluator.py:241-321`
- Modify: `examples/circle_packing/evaluator.py` (hypothesis section)
- Modify: `examples/alphaevolve_math_problems/kissing_number/evaluator.py` (hypothesis section)

The key change: evaluators stop calling `generate_knowledge_base_summary()` and stop setting `artifacts["hypothesis_knowledge_base"]`. They only set `artifacts["hypothesis_results"]` (the program's own verdicts). They also pass `program_id` to `update_ledger()`.

**Step 1: No new tests needed** — this is a wiring change. The existing evaluator tests (if any) and the integration tests in `tests/test_blis_hypothesis.py` cover the hypothesis parsing/testing. We'll verify manually.

**Step 2: Update `examples/blis_router/evaluator.py`**

Replace the hypothesis testing block (lines ~599-644). Key changes:
- Remove `generate_knowledge_base_summary` from imports
- Pass `program_id` to `update_ledger()` (use the child_id from the program path)
- Remove `artifacts["hypothesis_knowledge_base"] = knowledge_base_text` lines
- Keep `artifacts["hypothesis_results"] = hypothesis_results_text`
- Remove the "Still show knowledge base even without hypotheses" fallback block

**Step 3: Update `examples/function_minimization/evaluator.py`**

Same pattern as blis_router:
- Remove `generate_knowledge_base_summary` from imports
- Pass `program_id` to `update_ledger()`
- Remove `artifacts["hypothesis_knowledge_base"]` lines
- Keep `artifacts["hypothesis_results"]`

**Step 4: Update `examples/circle_packing/evaluator.py` and `examples/alphaevolve_math_problems/kissing_number/evaluator.py`**

Same pattern.

**Step 5: Run existing tests**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS (no test depends on `hypothesis_knowledge_base` artifact key)

**Step 6: Commit**

```bash
git add examples/blis_router/evaluator.py examples/function_minimization/evaluator.py \
       examples/circle_packing/evaluator.py examples/alphaevolve_math_problems/kissing_number/evaluator.py
git commit -m "refactor: evaluators store only own hypothesis verdicts, drop knowledge base artifact"
```

---

### Task 4: Compute fresh island-local knowledge at prompt time

**Files:**
- Modify: `openevolve/iteration.py:50-76`
- Modify: `openevolve/process_parallel.py:142-193` and `406-428`
- Test: `tests/test_hypothesis.py` (add integration test)

This is the core architectural change. Instead of reading stale `hypothesis_knowledge_base` from the parent's artifact, we:
1. Load the hypothesis ledger from disk
2. Get top N and worst N program IDs from the current island
3. Call `generate_island_knowledge_summary()` to produce fresh text
4. Inject it as a synthetic artifact alongside the parent's own artifacts

**Step 1: Write failing test**

```python
class TestFreshKnowledgeInjection(unittest.TestCase):
    """Test that fresh knowledge base is computed at prompt time."""

    def test_knowledge_injected_as_artifact(self):
        """Verify generate_island_knowledge_summary output can be injected as artifact."""
        from openevolve.hypothesis import generate_island_knowledge_summary
        ledger = {
            "baseline": {"x": 10.0},
            "entries": [
                {"program_id": "top1", "island": 0, "overall_combined_score": -30.0,
                 "hypotheses": [{"id": 1, "claim": "top strategy", "mechanism": "works",
                                 "metric": "x", "operator": "<", "threshold": 8.0,
                                 "actual": 7.0, "verdict": "CONFIRMED",
                                 "delta_vs_baseline_pct": -30.0}]},
            ],
        }
        summary = generate_island_knowledge_summary(
            ledger, top_program_ids={"top1"}, worst_program_ids=set()
        )
        # This should be injectable as an artifact value
        self.assertIsInstance(summary, str)
        self.assertIn("top strategy", summary)

        # Simulate what iteration.py will do: merge into parent_artifacts
        parent_artifacts = {"hypothesis_results": "H1 [CONFIRMED]: ..."}
        parent_artifacts["hypothesis_knowledge_base"] = summary
        self.assertIn("hypothesis_knowledge_base", parent_artifacts)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hypothesis.py::TestFreshKnowledgeInjection -v`
Expected: May pass if Task 1 is done. If so, this validates the integration path.

**Step 3: Update `openevolve/iteration.py`**

After getting `parent_artifacts` (line 55) and `parent_island` (line 58), add:

```python
# Compute fresh island-local hypothesis knowledge base
if config.hypothesis_driven:
    from openevolve.hypothesis import load_ledger, generate_island_knowledge_summary
    from pathlib import Path

    ledger_dir = os.environ.get("OPENEVOLVE_OUTPUT_DIR", "openevolve_output")
    ledger_path = Path(ledger_dir) / "hypothesis_ledger.json"
    if ledger_path.exists():
        ledger = load_ledger(ledger_path)
        # Get top and worst program IDs from current island
        top_progs = database.get_top_programs(5, island_idx=parent_island)
        worst_progs = database.get_top_programs(5, island_idx=parent_island, reverse=True)
        top_ids = {p.id for p in top_progs}
        worst_ids = {p.id for p in worst_progs}
        knowledge_text = generate_island_knowledge_summary(
            ledger, top_program_ids=top_ids, worst_program_ids=worst_ids
        )
        if parent_artifacts is None:
            parent_artifacts = {}
        parent_artifacts["hypothesis_knowledge_base"] = knowledge_text
```

**Step 4: Update `openevolve/process_parallel.py`**

In `_run_iteration_worker()` (around line 157), after getting `parent_artifacts`, add similar logic using the snapshot. Also update `_create_database_snapshot()` to include the ledger path or the ledger data itself.

For the worker, the ledger is on disk and accessible:

```python
# In _run_iteration_worker(), after parent_artifacts = ...
if _worker_config.hypothesis_driven:
    from openevolve.hypothesis import load_ledger, generate_island_knowledge_summary
    from pathlib import Path

    ledger_dir = os.environ.get("OPENEVOLVE_OUTPUT_DIR", "openevolve_output")
    ledger_path = Path(ledger_dir) / "hypothesis_ledger.json"
    if ledger_path.exists():
        ledger = load_ledger(ledger_path)
        # Get top and worst program IDs from island
        top_ids = set()
        worst_ids = set()
        island_progs = [
            programs[pid] for pid in db_snapshot["islands"][parent_island] if pid in programs
        ]
        island_progs.sort(
            key=lambda p: p.metrics.get("combined_score", safe_numeric_average(p.metrics)),
            reverse=True,
        )
        if island_progs:
            top_ids = {p.id for p in island_progs[:5]}
            worst_ids = {p.id for p in island_progs[-5:]}
        knowledge_text = generate_island_knowledge_summary(
            ledger, top_program_ids=top_ids, worst_program_ids=worst_ids
        )
        if parent_artifacts is None:
            parent_artifacts = {}
        parent_artifacts["hypothesis_knowledge_base"] = knowledge_text
```

**Step 5: Add `reverse` parameter to `database.get_top_programs()`**

Check if `get_top_programs` supports getting worst programs. If not, add a `reverse=False` parameter. Alternatively, the iteration.py path can compute worst IDs from the same sorted list.

Actually, simpler approach: in `iteration.py`, sort `island_top_programs` (already fetched at line 59) and take last 5 for worst. No new database method needed.

**Step 6: Run full test suite**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add openevolve/iteration.py openevolve/process_parallel.py tests/test_hypothesis.py
git commit -m "feat: compute fresh island-local hypothesis knowledge at prompt time"
```

---

### Task 5: Update HYPOTHESIS_INSTRUCTIONS_TEMPLATE for new knowledge format

**Files:**
- Modify: `openevolve/prompt/templates.py:20-43`

The template currently says "Build on CONFIRMED strategies" and "If a strategy was REFUTED". Update to match the new format that shows individual verdicts from top/worst programs rather than aggregated categories.

**Step 1: Update the template text**

In `openevolve/prompt/templates.py`, update `HYPOTHESIS_INSTRUCTIONS_TEMPLATE`:

```python
HYPOTHESIS_INSTRUCTIONS_TEMPLATE = """

## Hypothesis-Driven Evolution

You MUST include at least 1 hypothesis (max 3) as comments at the TOP of the EVOLVE-BLOCK, BEFORE any code.

Format (each hypothesis needs all 3 lines, using the appropriate comment syntax for the language):
  # HYPOTHESIS-N: <one-line claim about what will improve and why>
  # MECHANISM-N: <causal explanation - what signal/behavior drives the improvement>
  # EXPECT-N: <metric_name> < <threshold>   (for lower-is-better metrics like latency)
  # EXPECT-N: <metric_name> > <threshold>   (for higher-is-better metrics like scores)

Rules:
  - N starts at 1 and increments
  - metric_name must be one of the metrics shown in your performance feedback
  - Use < for metrics where lower is better (e.g. latency, error rate)
  - Use > for metrics where higher is better (e.g. accuracy, score)
  - threshold is a number; the hypothesis is CONFIRMED if actual satisfies the comparison
  - Set thresholds based on baseline values shown in the HYPOTHESIS KNOWLEDGE BASE artifact (if present)
  - Be specific: "improves performance" is too vague; "reduces avg_e2e_ms by routing large requests to less-loaded instances" is good
  - The knowledge base shows verdicts from TOP-SCORING and WORST-SCORING programs on your island
  - Learn from CONFIRMED hypotheses in top programs — build on strategies that worked
  - Avoid patterns from REFUTED hypotheses in worst programs — explain why your approach differs
  - If no knowledge base is shown yet (first iteration), set thresholds 5-10% beyond the current metrics
"""
```

**Step 2: Update existing test**

Run: `python -m pytest tests/test_hypothesis.py::TestPromptInjection -v`
Expected: PASS (test checks for "HYPOTHESIS-N" which is still present)

**Step 3: Commit**

```bash
git add openevolve/prompt/templates.py
git commit -m "refactor: update hypothesis template for score-ranked knowledge format"
```

---

### Task 6: Update `examples/blis_router/hypo_explained.md`

**Files:**
- Modify: `examples/blis_router/hypo_explained.md`

Rewrite the document to reflect the V2 architecture:
- Step 4 (evaluator): only stores own verdicts, passes program_id to ledger
- Step 5 (knowledge base): replaced with "fresh island-local knowledge at prompt time"
- Step 6 (prompt assembly): two-channel display
- Summary diagram updated

**Step 1: Rewrite the document**

Full rewrite reflecting the new architecture. Keep the same structure (Steps 1-6) but update content.

**Step 2: Commit**

```bash
git add examples/blis_router/hypo_explained.md
git commit -m "docs: update hypo_explained.md for V2 score-ranked island-local pipeline"
```

---

### Task 7: Pass `program_id` through evaluator call chain

**Files:**
- Modify: evaluators to extract program_id from file path or env var

The evaluators need the program's UUID to pass to `update_ledger()`. Currently, the evaluator receives `program_path` which contains the UUID (e.g., `/tmp/openevolve_abc123.py`). The UUID is also available as the filename stem.

**Step 1: In each evaluator's hypothesis block, extract program_id from path**

```python
# Extract program_id from file path (format: /tmp/openevolve_<uuid>.py or similar)
program_id = Path(program_path).stem
```

Then pass to `update_ledger(..., program_id=program_id)`.

For island, the evaluator doesn't know the island. We have two options:
- Pass island via environment variable (set in iteration.py before evaluation)
- Leave island=None in evaluators; fill it in from metadata when reading the ledger

Simpler: pass island via env var `OPENEVOLVE_ISLAND_ID` set in iteration.py/process_parallel.py.

**Step 2: Set `OPENEVOLVE_ISLAND_ID` in iteration.py and process_parallel.py**

In `iteration.py`, before calling `evaluator.evaluate_program()`:
```python
os.environ["OPENEVOLVE_ISLAND_ID"] = str(parent_island)
```

In `process_parallel.py`, similarly before evaluation.

**Step 3: Read in evaluators**

```python
island = int(os.environ.get("OPENEVOLVE_ISLAND_ID", "0"))
update_ledger(ledger, h_results, score, ledger_path, program_id=program_id, island=island)
```

**Step 4: Run full test suite**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add openevolve/iteration.py openevolve/process_parallel.py \
       examples/blis_router/evaluator.py examples/function_minimization/evaluator.py \
       examples/circle_packing/evaluator.py examples/alphaevolve_math_problems/kissing_number/evaluator.py
git commit -m "feat: pass program_id and island to hypothesis ledger via env vars"
```

---

### Task 8: Final integration test and cleanup

**Files:**
- Test: `tests/test_hypothesis.py`
- Modify: `openevolve/hypothesis.py` (add deprecation warning to old function)

**Step 1: Write end-to-end integration test**

```python
class TestV2PipelineIntegration(unittest.TestCase):
    """End-to-end test of the V2 hypothesis pipeline."""

    def test_full_pipeline(self):
        """Simulate: parse -> test -> ledger(with program_id) -> island summary."""
        code = """
# HYPOTHESIS-1: Better approach improves metric_a
# MECHANISM-1: Uses adaptive strategy
# EXPECT-1: metric_a < 5.0
def solve(): pass
"""
        # Parse
        hypotheses = parse_hypotheses(code, valid_metrics={"metric_a"})
        self.assertEqual(len(hypotheses), 1)

        # Test
        results = test_hypotheses(hypotheses, {"metric_a": 4.0}, {"metric_a": 8.0})
        self.assertEqual(results[0]["verdict"], "CONFIRMED")

        # Update ledger with program_id and island
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ledger.json"
            ledger = load_ledger(path)
            ledger["baseline"] = {"metric_a": 8.0}
            update_ledger(ledger, results, -4.0, path, program_id="prog_001", island=0)

            # Generate island knowledge summary
            from openevolve.hypothesis import generate_island_knowledge_summary
            summary = generate_island_knowledge_summary(
                ledger, top_program_ids={"prog_001"}, worst_program_ids=set()
            )
            self.assertIn("Better approach", summary)
            self.assertIn("CONFIRMED", summary)
            self.assertIn("BASELINE", summary)
```

**Step 2: Run full test suite**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS

**Step 3: Add deprecation log to `generate_knowledge_base_summary()`**

```python
def generate_knowledge_base_summary(ledger: dict, top_n: int = 5) -> str:
    """[DEPRECATED] Use generate_island_knowledge_summary() instead.

    This function aggregates by exact claim string which doesn't work in practice.
    Kept for backward compatibility with old evaluators.
    """
    logger.warning(
        "generate_knowledge_base_summary() is deprecated; "
        "use generate_island_knowledge_summary() instead"
    )
    # ... existing implementation unchanged ...
```

**Step 4: Run tests one final time**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add openevolve/hypothesis.py tests/test_hypothesis.py
git commit -m "test: add V2 pipeline integration test, deprecate old knowledge summary"
```

---

## Execution Order

Tasks 1 and 2 are independent and can be done in parallel.
Task 3 depends on Task 2 (evaluators pass program_id).
Task 4 depends on Task 1 (uses generate_island_knowledge_summary).
Task 5 is independent.
Task 6 is independent.
Task 7 depends on Tasks 2 and 3.
Task 8 depends on all previous tasks.

```
Task 1 ──┬── Task 4 ──┐
Task 2 ──┼── Task 3 ──┼── Task 7 ── Task 8
Task 5 ──┘            │
Task 6 ───────────────┘
```
