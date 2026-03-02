# Structured Threshold Tuning for OpenEvolve

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Separate algorithmic structure from threshold values in LLM-generated code. The LLM declares tunable parameters with ranges using a lightweight inline annotation (`@TUNE`). After the LLM generates code, a Bayesian optimizer (Optuna TPE) searches the declared threshold space before the program is scored. The optimized values are written back into the code with feedback annotations (`@TUNED`) so the LLM sees what the optimizer found and how much it helped.

**Relationship to hypotheses:** This complements hypothesis-driven evolution. Hypotheses guide the LLM's *strategic reasoning* ("batch by prefix length to reduce cache misses"). Threshold tuning handles the *numerical optimization* ("what's the right cutoff?"). Both produce inline annotations that travel with the code through the evolutionary lineage.

**Tech Stack:** Python 3.10+, Optuna (TPE sampler), unittest, openevolve framework

---

## Problem

LLM-generated algorithms in OpenEvolve frequently contain hard-coded thresholds (`if load < 0.4`, `if latency > 200`) that are essentially guesses. The evolutionary loop treats the algorithm + its thresholds as one atomic unit, so a brilliant algorithm with bad threshold values gets a bad score and may be discarded. The LLM has no principled way to search the threshold space — it just picks numbers.

---

## Annotation Format

### Declaring tunable thresholds

The LLM annotates variable assignments with `@TUNE`:

```python
# Continuous float (default)
load_cutoff = 0.4  # @TUNE [0.0, 1.0]

# Explicit float
decay_rate = 0.01  # @TUNE [0.001, 0.1] float

# Integer
batch_size = 32  # @TUNE [8, 128] int
```

Only numeric types (float and int) are supported. Categorical/strategy choices are algorithmic decisions that the LLM should make through evolution, not optimizer search.

### After tuning — optimizer feedback

The optimizer rewrites values and adds `@TUNED` annotations:

```python
load_cutoff = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.12, best_impact=throughput:+0.3)
batch_size = 64  # @TUNE [8, 128] int @TUNED(was=32, gain=+0.12, best_impact=avg_e2e_ms:-20)
```

Where:
- `gain` = total delta in `combined_score` from tuning ALL parameters jointly (same value on every `@TUNED` line, since parameters are optimized together)
- `best_impact` = the single most impacted individual metric and its delta (per-parameter, computed by comparing the best trial against a trial with this parameter reset to its original value)

### Rules

- **Max 3** `@TUNE` annotations per program. If the LLM declares more, only the first 3 are tuned; the rest are ignored.
- `@TUNE` must appear on a simple assignment line (`name = value`). Complex expressions are not supported.
- On subsequent iterations, existing `@TUNED(...)` annotations are stripped before tuning so the optimizer always starts fresh.
- All `@TUNE` parameters are re-tuned jointly every iteration (not just new ones), since adding/removing a parameter changes the optimal values for the others.

### Parsing regex (conceptual)

```
^(\s*(\w+)\s*=\s*(.+?)\s*)#\s*@TUNE\s+\[([^,\]]+),\s*([^\]]+)\](\s+(?:int|float))?
```

---

## Tuning Pipeline

### Integration point in iteration flow

The tuning step happens after LLM code generation but *before* evaluation:

```
BEFORE:
  LLM generates code → evaluate → inject RESULT comments → store in DB

AFTER:
  LLM generates code → parse @TUNE → optimize thresholds → rewrite code → evaluate → inject RESULT comments → store in DB
```

### How the optimizer works

1. **Parse**: Extract all `@TUNE` annotations from the child code (max 3).
2. **Skip if none**: If no `@TUNE` found, proceed directly to evaluation (zero overhead).
3. **Strip @TUNED**: Remove any existing `@TUNED(...)` annotations from the child code (inherited from parent through diffs).
4. **Build Optuna study**: Create a study with TPE sampler. Define one parameter per `@TUNE` using the declared range/type.
5. **Trial loop**: For each trial (up to `budget + num_params * budget_scale_per_param`):
   - Rewrite the threshold values in the code with Optuna's suggested values
   - Call the same evaluator used by the main loop
   - Return `combined_score` as the objective, record all individual metrics
6. **Apply best**: Take the best trial's values, rewrite into the code with `@TUNED(was=<original>, gain=<delta>, best_impact=<metric>:<delta>)`.
7. **Proceed**: The optimized code goes to the normal evaluation → RESULT injection → database storage path.

### Evaluation cost management

Each tuning trial calls the same evaluator as the main loop. Cost is controlled by the `budget` config — lower it if evaluations are expensive. The final optimized program gets the same evaluation as any other program (no special treatment).

### Async integration

The iteration worker (`run_iteration_with_shared_db`) is async, but Optuna's trial loop is synchronous. The tuning module runs the entire Optuna study inside `asyncio.get_event_loop().run_in_executor()`. Inside each trial's objective function, it uses `asyncio.run()` (in a new event loop) to call the async `evaluator.evaluate_program()`. This keeps the async worker unblocked while Optuna runs.

### Failure handling

If all tuning trials fail (timeouts, evaluator crashes, etc.), the tuning module falls back to the original child code with the LLM's guessed threshold values and proceeds to normal evaluation. A warning is logged but the iteration is not aborted.

### Optuna dependency guard

If `tuning.enabled: true` but `optuna` is not installed, the system raises `ImportError` at config load time with a clear message: `pip install openevolve[tuning]`. This fails fast rather than deep in a trial loop.

---

## Configuration

New `tuning` top-level key in YAML config:

```yaml
tuning:
  enabled: true                # Master switch, like hypothesis_driven
  budget: 20                   # Base Optuna trials per program
  max_params: 3                # Hard cap on @TUNE annotations honored
  budget_scale_per_param: 5    # Extra trials per param (total = budget + n * scale)
```

**Defaults:** `enabled: false`, `budget: 20`, `max_params: 3`, `budget_scale_per_param: 5`.

A program with 1 threshold gets 25 trials, 2 gets 30, 3 gets 35.

**Interaction with hypothesis_driven:** Independent flags. You can run neither, hypotheses only, tuning only, or both together. This enables clean A/B and factorial experiments.

---

## LLM Prompt Instructions

A `THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE` is appended to the system message when `tuning.enabled: true`, similar to `HYPOTHESIS_INSTRUCTIONS_TEMPLATE`.

The template instructs the LLM:

1. **What**: You may annotate up to 3 variable assignments with `@TUNE` to declare tunable thresholds.
2. **Syntax**: `var = value  # @TUNE [min, max]` for float (default), append `int` for integer. Only numeric types — no categorical.
3. **What happens**: An optimizer will search the declared ranges before scoring — so pick good ranges, not good values.
4. **Reading feedback**: `@TUNED(was=X, gain=Y, best_impact=metric:Z)` means the optimizer found a better value. `gain` is the total score improvement from tuning all parameters jointly. `best_impact` shows which metric this specific parameter affected most.
5. **Constraints**: Max 3 `@TUNE` per program. Choose the most impactful parameters. Hardcode the rest with your best guess.
6. **Guidance**: Focus `@TUNE` on numeric parameters where you're uncertain about the right value. Don't tune constants you know theoretically. Do tune decision boundaries, cutoffs, weights, and scaling factors. Don't use `@TUNE` for algorithmic choices (e.g., which strategy to use) — make those decisions yourself.
7. **Parent annotations**: Don't manually change `@TUNED` annotations from the parent — let the optimizer handle those. Focus on structural changes and declaring new thresholds if needed.

### Single-shot example in the template

```
Example:

```python
# EVOLVE-BLOCK-START
threshold_a = 0.5  # @TUNE [0.0, 1.0]
max_retries = 3  # @TUNE [1, 10] int

def solve(data):
    for item in data:
        if item.score < threshold_a:
            handle_low(item, retries=max_retries)
        else:
            handle_high(item)
# EVOLVE-BLOCK-END
```

After the optimizer runs, you will see in the next iteration:
```python
threshold_a = 0.72  # @TUNE [0.0, 1.0] @TUNED(was=0.5, gain=+0.11, best_impact=accuracy:+0.05)
max_retries = 7  # @TUNE [1, 10] int @TUNED(was=3, gain=+0.11, best_impact=success_rate:+0.1)
```
```

---

## Interaction with Existing Features

**With hypotheses:** Both coexist. Iteration order:

```
LLM generates code
  → rescue_hypotheses()          (if hypothesis_driven)
  → parse @TUNE + optimize       (if tuning.enabled)
  → evaluate (final, full)
  → inject_result_comments()     (if hypothesis_driven)
  → store in DB
```

A program can have both annotations:

```python
# HYPOTHESIS-1: routing by queue depth reduces tail latency
# MECHANISM-1: shorter queues correlate with faster completion
# EXPECT-1: p99_lat < 300
threshold_a = 0.5  # @TUNE [0.0, 1.0]
```

**With diff-based evolution:** `@TUNE` annotations live on normal assignment lines. Diffs add, remove, or change them naturally. `@TUNED(...)` gets stripped before tuning, so stale parent annotations aren't a problem.

**With MAP-Elites / islands:** No interaction. Tuning happens per-program before database insertion.

**A/B testing:** Same pattern as hypotheses. `tuning.enabled: true` in treatment, `false` in control. Existing `scripts/run_experiment.py` works unchanged.

---

## Files Overview

| File | Action | What |
|------|--------|------|
| `openevolve/tuning.py` | New | Core module: parse `@TUNE`, run Optuna, rewrite code with `@TUNED` |
| `openevolve/config.py` | Modify | Add `TuningConfig` dataclass |
| `openevolve/iteration.py` | Modify | Insert tuning step between LLM code generation and evaluation |
| `openevolve/prompt/templates.py` | Modify | Add `THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE` |
| `openevolve/prompt/sampler.py` | Modify | Append tuning instructions when `tuning.enabled` |
| `tests/test_tuning.py` | New | Unit tests for parsing, rewriting, Optuna integration |
| `examples/function_minimization/` | Modify | Update evaluator/config to demo threshold tuning |
| `setup.py` / `pyproject.toml` | Modify | Add `optuna` as optional dependency (`pip install openevolve[tuning]`) |
