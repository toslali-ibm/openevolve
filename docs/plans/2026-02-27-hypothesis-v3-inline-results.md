# Hypothesis V3: Inline RESULT Comments — Zero Infrastructure

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** After evaluation, inject `RESULT-N` comment lines into the child's code so hypothesis verdicts travel with the code through OpenEvolve's existing parent/top-program/inspiration display — no ledger, no knowledge base, no artifacts needed.

**Architecture:** The framework (`iteration.py` / `process_parallel.py`) parses HYPOTHESIS/EXPECT comments from child code, tests them against actual metrics, and injects `// RESULT-N: CONFIRMED (actual=3850.0)` lines. The modified code is stored in the database. When shown to the LLM as parent, top program, or inspiration, the hypotheses+results are visible in context with the code. Evaluators become hypothesis-unaware — they just return metrics.

**Tech Stack:** Python 3.10+, unittest, openevolve framework

---

## What Changes

```
BEFORE (V1):
  Evaluator: parse hypos → test → update ledger → generate knowledge base → store as artifact
  Prompt:    parent's stale artifact["hypothesis_knowledge_base"] → LLM

AFTER (V3):
  Framework: parse hypos → test against metrics → inject RESULT-N into code → store code
  Prompt:    parent code (has RESULT lines) + top programs (have RESULT lines) → LLM
  Evaluator: just returns metrics (no hypothesis code at all)
```

## Files Overview

| File | Action | What |
|------|--------|------|
| `openevolve/hypothesis.py` | Add function | `inject_result_comments(code, metrics)` |
| `openevolve/hypothesis.py` | Keep as-is | `parse_hypotheses()`, `test_hypotheses()`, `rescue_hypotheses()` |
| `openevolve/hypothesis.py` | Deprecate | `load_ledger()`, `update_ledger()`, `generate_knowledge_base_summary()`, `format_hypothesis_results()` |
| `openevolve/iteration.py` | Add 5 lines | Call `inject_result_comments()` after evaluation |
| `openevolve/process_parallel.py` | Add 5 lines | Same in worker process |
| `openevolve/prompt/templates.py` | Update text | Tell LLM to read RESULT-N lines |
| `examples/*/evaluator.py` (×4) | Remove code | Delete all hypothesis imports and pipeline code |
| `tests/test_hypothesis.py` | Add tests | For `inject_result_comments()` |
| `examples/blis_router/hypo_explained.md` | Rewrite | Document V3 |

---

### Task 1: Add `inject_result_comments()` to hypothesis.py

**Files:**
- Modify: `openevolve/hypothesis.py`
- Test: `tests/test_hypothesis.py`

This is the core new function. It takes code + actual metrics, parses hypotheses,
tests them, and injects RESULT-N lines right after the corresponding EXPECT-N lines.

**Step 1: Write failing tests**

Add to `tests/test_hypothesis.py`:

```python
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
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_hypothesis.py::TestInjectResultComments -v`
Expected: FAIL (ImportError — `inject_result_comments` doesn't exist)

**Step 3: Implement `inject_result_comments()`**

Add to `openevolve/hypothesis.py` after `rescue_hypotheses()` (after line 111):

```python
def inject_result_comments(code: str, actual_metrics: dict) -> str:
    """Inject RESULT-N comment lines after each EXPECT-N in the code.

    After evaluation, the framework calls this to stamp hypothesis verdicts
    directly into the child's code.  When this code is later shown to the LLM
    (as parent, top program, or inspiration), the verdicts are visible in
    context with the code that produced them.

    No-op when:
      - code has no EXPECT-N lines
      - RESULT-N lines already exist (idempotent)

    Args:
        code: Source code with HYPOTHESIS/MECHANISM/EXPECT comments.
        actual_metrics: Dict of metric_name → value from evaluation.

    Returns:
        Code with RESULT-N lines injected after each EXPECT-N.
    """
    # Already has results? Don't double-stamp.
    if re.search(r"(?://|#|--)\s*RESULT-\d+:", code):
        return code

    expect_pattern = re.compile(
        rf"^(\s*)((?://|#|--)\s*)EXPECT-(\d+):\s*(\S+)\s*([<>])\s*([0-9]+(?:\.[0-9]+)?)\s*$"
    )

    lines = code.splitlines()
    new_lines = []
    for line in lines:
        new_lines.append(line)
        m = expect_pattern.match(line)
        if m:
            indent = m.group(1)       # leading whitespace
            prefix = m.group(2)       # comment prefix (e.g. "// " or "# ")
            hid = m.group(3)          # hypothesis number
            metric = m.group(4)       # metric name
            operator = m.group(5)     # < or >
            threshold = float(m.group(6))
            actual = actual_metrics.get(metric)

            if actual is None:
                verdict = "INCONCLUSIVE"
                result_text = f"{indent}{prefix}RESULT-{hid}: {verdict} (metric not available)"
            else:
                if operator == ">":
                    verdict = "CONFIRMED" if actual > threshold else "REFUTED"
                else:
                    verdict = "CONFIRMED" if actual < threshold else "REFUTED"
                result_text = f"{indent}{prefix}RESULT-{hid}: {verdict} (actual={actual})"

            new_lines.append(result_text)

    return "\n".join(new_lines)
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hypothesis.py::TestInjectResultComments -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add openevolve/hypothesis.py tests/test_hypothesis.py
git commit -m "feat: add inject_result_comments() to stamp verdicts into code"
```

---

### Task 2: Call `inject_result_comments()` in iteration.py

**Files:**
- Modify: `openevolve/iteration.py:13,126-127`

After evaluation returns metrics, inject RESULT lines into child_code before
storing it in the Program object.

**Step 1: No new test** — tested via Task 1 unit tests + Task 6 integration test.

**Step 2: Update imports (line 13)**

Add `inject_result_comments` to the existing import:

```python
from openevolve.hypothesis import rescue_hypotheses, inject_result_comments
```

**Step 3: Add injection after evaluation (after line 126)**

After `result.child_metrics = await evaluator.evaluate_program(child_code, child_id)`,
add:

```python
        # Stamp hypothesis verdicts into child code
        if config.hypothesis_driven and result.child_metrics:
            child_code = inject_result_comments(child_code, result.child_metrics)
```

This goes between lines 126 and 128 (before `artifacts = evaluator.get_pending_artifacts`).

**Step 4: Run existing tests**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add openevolve/iteration.py
git commit -m "feat: inject hypothesis RESULT comments after evaluation in iteration.py"
```

---

### Task 3: Call `inject_result_comments()` in process_parallel.py

**Files:**
- Modify: `openevolve/process_parallel.py:259-262`

Same change as Task 2 but in the worker process path.

**Step 1: Add injection after evaluation**

After line 259 (`child_metrics = asyncio.run(_worker_evaluator.evaluate_program(...))`),
add:

```python
        # Stamp hypothesis verdicts into child code
        if _worker_config.hypothesis_driven and child_metrics:
            from openevolve.hypothesis import inject_result_comments
            child_code = inject_result_comments(child_code, child_metrics)
```

This goes between lines 259 and 261 (before `artifacts = _worker_evaluator.get_pending_artifacts`).

**Step 2: Run existing tests**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add openevolve/process_parallel.py
git commit -m "feat: inject hypothesis RESULT comments after evaluation in process_parallel.py"
```

---

### Task 4: Update system prompt template

**Files:**
- Modify: `openevolve/prompt/templates.py:20-43`

Update `HYPOTHESIS_INSTRUCTIONS_TEMPLATE` to tell the LLM about RESULT lines
and how to learn from them.

**Step 1: Replace the template**

```python
HYPOTHESIS_INSTRUCTIONS_TEMPLATE = """

## Hypothesis-Driven Evolution

You MUST include at least 1 hypothesis (max 3) as comments at the TOP of the EVOLVE-BLOCK, BEFORE any code.

Format (each hypothesis needs all 3 lines, using the appropriate comment syntax for the language):
  # HYPOTHESIS-N: <one-line claim about what will improve and why>
  # MECHANISM-N: <causal explanation - what signal/behavior drives the improvement>
  # EXPECT-N: <metric_name> < <threshold>   (for lower-is-better metrics like latency)
  # EXPECT-N: <metric_name> > <threshold>   (for higher-is-better metrics like scores)

After evaluation, a RESULT-N line is automatically added showing the verdict:
  # RESULT-N: CONFIRMED (actual=3850.0)
  # RESULT-N: REFUTED (actual=5200.0)

Rules:
  - N starts at 1 and increments
  - metric_name must be one of the metrics shown in your performance feedback
  - Use < for metrics where lower is better (e.g. latency, error rate)
  - Use > for metrics where higher is better (e.g. accuracy, score)
  - threshold is a number; the hypothesis is CONFIRMED if actual satisfies the comparison
  - Be specific: "improves performance" is too vague; "reduces avg_e2e_ms by routing large requests to less-loaded instances" is good
  - Look at RESULT lines in the parent program and top programs to see what worked (CONFIRMED) and what failed (REFUTED)
  - Build on CONFIRMED strategies from top-performing programs
  - Avoid or differentiate from REFUTED strategies
  - If no RESULT lines exist yet (first iteration), set thresholds 5-10% beyond the current metrics
  - Do NOT write RESULT lines yourself — they are added automatically after evaluation
"""
```

**Step 2: Run existing prompt injection tests**

Run: `python -m pytest tests/test_hypothesis.py::TestPromptInjection -v`
Expected: PASS (tests check for "HYPOTHESIS-N" / "MECHANISM-N" / "EXPECT-N" which are still present)

**Step 3: Commit**

```bash
git add openevolve/prompt/templates.py
git commit -m "feat: update hypothesis template to document RESULT-N lines"
```

---

### Task 5: Remove hypothesis pipeline from all evaluators

**Files:**
- Modify: `examples/blis_router/evaluator.py`
- Modify: `examples/function_minimization/evaluator.py`
- Modify: `examples/circle_packing/evaluator.py`
- Modify: `examples/alphaevolve_math_problems/kissing_number/evaluator.py`

Remove all hypothesis imports and the hypothesis pipeline blocks. Evaluators
just return metrics — the framework handles hypotheses.

**Step 1: In each evaluator, remove these imports**

```python
# DELETE these lines:
from openevolve.hypothesis import (
    parse_hypotheses,
    test_hypotheses,
    load_ledger,
    update_ledger,
    generate_knowledge_base_summary,
    format_hypothesis_results,
)
```

Also remove the `VALID_METRICS` constant (no longer needed in evaluators).

**Step 2: In each evaluator, remove the hypothesis pipeline block**

In `blis_router/evaluator.py`, delete lines 346-644 (the entire `hypothesis_enabled` block):
```python
# DELETE the entire block starting with:
hypothesis_enabled = os.environ.get("HYPOTHESIS_DRIVEN", "false") == "true"
if hypothesis_enabled:
    ...
```

Same pattern for all 4 evaluators. The evaluator just returns `EvaluationResult(metrics=..., artifacts=...)` with its normal artifacts (workload results, convergence info, etc.) — no hypothesis artifacts.

**Step 3: Run existing tests**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add examples/blis_router/evaluator.py \
       examples/function_minimization/evaluator.py \
       examples/circle_packing/evaluator.py \
       examples/alphaevolve_math_problems/kissing_number/evaluator.py
git commit -m "refactor: remove hypothesis pipeline from evaluators (framework handles it)"
```

---

### Task 6: End-to-end integration test

**Files:**
- Test: `tests/test_hypothesis.py`

Test the full V3 flow: LLM writes code with hypotheses → rescue → evaluate →
inject results → results visible in code → parse still works on result-annotated code.

**Step 1: Write the test**

```python
class TestV3InlineResultsPipeline(unittest.TestCase):
    """End-to-end test of V3: hypotheses + results live in code."""

    def test_full_pipeline_python(self):
        """Simulate: rescue → eval → inject → result visible in code."""
        # LLM response with hypotheses outside diff blocks (Gemini style)
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
        from openevolve.hypothesis import inject_result_comments
        final_code = inject_result_comments(rescued, actual_metrics)

        # Verify RESULT is in the code
        self.assertIn("RESULT-1: CONFIRMED", final_code)
        self.assertIn("actual=0.92", final_code)

        # Step 4: When this code is shown to next LLM, hypotheses are still parseable
        parsed = parse_hypotheses(final_code, valid_metrics={"combined_score", "distance_score"})
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["claim"], "Multi-start search improves combined_score")

    def test_full_pipeline_go(self):
        """Same flow with Go comment syntax."""
        code = (
            "// EVOLVE-BLOCK-START\n"
            "// HYPOTHESIS-1: Cache affinity reduces latency\n"
            "// MECHANISM-1: Prefix reuse avoids recomputation\n"
            "// EXPECT-1: avg_e2e_ms < 5000\n"
            "func route(req Request) int { return 0 }\n"
            "// EVOLVE-BLOCK-END\n"
        )
        metrics = {"avg_e2e_ms": 4200.0, "avg_p95_ms": 5100.0}

        from openevolve.hypothesis import inject_result_comments
        result = inject_result_comments(code, metrics)

        self.assertIn("// RESULT-1: CONFIRMED", result)
        self.assertIn("actual=4200.0", result)

        # Still parseable
        parsed = parse_hypotheses(result, valid_metrics={"avg_e2e_ms"})
        self.assertEqual(len(parsed), 1)

    def test_idempotent_injection(self):
        """Injecting twice should not double-stamp."""
        code = (
            "# HYPOTHESIS-1: Claim\n"
            "# MECHANISM-1: Mechanism\n"
            "# EXPECT-1: score > 0.5\n"
            "x = 1\n"
        )
        metrics = {"score": 0.8}
        from openevolve.hypothesis import inject_result_comments
        once = inject_result_comments(code, metrics)
        twice = inject_result_comments(once, metrics)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count("RESULT-1"), 1)
```

**Step 2: Run the test**

Run: `python -m pytest tests/test_hypothesis.py::TestV3InlineResultsPipeline -v`
Expected: ALL PASS

**Step 3: Run full test suite**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/test_hypothesis.py
git commit -m "test: add V3 inline-results end-to-end integration tests"
```

---

### Task 7: Update hypo_explained.md for V3

**Files:**
- Modify: `examples/blis_router/hypo_explained.md`

Rewrite to document V3 architecture. Key message: hypotheses and results live
in the code. No ledger, no knowledge base, no artifacts. OpenEvolve's existing
parent/top-program/inspiration mechanisms carry the hypothesis intelligence.

**Step 1: Rewrite the document**

Full rewrite covering:
- Step 1: System prompt (same as before)
- Step 2: LLM writes HYPOTHESIS/MECHANISM/EXPECT (same as before)
- Step 3: rescue_hypotheses() (same as before)
- Step 4: Evaluator returns metrics (NO hypothesis code)
- Step 5: Framework injects RESULT-N lines into code
- Step 6: Code stored in database with results baked in
- Step 7: When shown to LLM, hypotheses+results are visible in context
- Summary diagram
- V1 issues (for reference)

**Step 2: Commit**

```bash
git add examples/blis_router/hypo_explained.md
git commit -m "docs: rewrite hypo_explained.md for V3 inline results architecture"
```

---

### Task 8: Deprecate old hypothesis infrastructure

**Files:**
- Modify: `openevolve/hypothesis.py`

Add deprecation warnings to `load_ledger()`, `update_ledger()`,
`generate_knowledge_base_summary()`, and `format_hypothesis_results()`.
Don't delete them yet — old evaluators or scripts may still reference them.

**Step 1: Add deprecation warnings**

At the top of each function, add:

```python
import warnings
warnings.warn(
    "load_ledger() is deprecated. V3 hypothesis pipeline uses inline RESULT comments.",
    DeprecationWarning,
    stacklevel=2,
)
```

**Step 2: Run full test suite**

Run: `python -m unittest discover tests -v`
Expected: ALL PASS (deprecation warnings are non-fatal)

**Step 3: Commit**

```bash
git add openevolve/hypothesis.py
git commit -m "refactor: deprecate ledger/knowledge-base functions (replaced by inline RESULT)"
```

---

## Execution Order

```
Task 1 (inject_result_comments) ── Task 2 (iteration.py) ── Task 3 (process_parallel.py) ──┐
                                                                                             ├── Task 6 (integration test)
Task 4 (template update) ──────────────────────────────────────────────────────────────────┤
                                                                                             ├── Task 7 (docs)
Task 5 (remove evaluator code) ────────────────────────────────────────────────────────────┤
                                                                                             └── Task 8 (deprecate)
```

Tasks 1, 4, 5 are independent — can run in parallel.
Tasks 2, 3 depend on Task 1.
Tasks 6, 7, 8 depend on all previous tasks.

## What We Delete (net negative lines)

- ~50 lines of hypothesis boilerplate per evaluator × 4 evaluators = **~200 lines deleted**
- Ledger, knowledge base functions eventually removed = **~120 lines deprecated**
- Added: `inject_result_comments()` = **~40 lines**
- Added: 5 lines in iteration.py + 5 lines in process_parallel.py
- **Net: ~270 fewer lines of code**
