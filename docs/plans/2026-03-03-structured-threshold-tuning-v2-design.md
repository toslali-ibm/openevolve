# Structured Threshold Tuning v2 — Design

**Status:** Proposed redesign based on v1 A/B experiment findings

**Goal:** Separate algorithmic innovation (LLM's strength) from parameter optimization (optimizer's strength). The LLM focuses on inventing better algorithms. Optuna handles numeric parameter tuning. Together they outperform either alone.

**Predecessor:** `docs/plans/2026-03-02-structured-threshold-tuning-design.md` (v1)

**Tech Stack:** Python 3.10+, Optuna (TPE sampler), unittest, openevolve framework

---

## Why v2: A/B Experiment Findings

v1 was tested on three tasks (2 runs each, 25 iterations, `hypothesis_driven: false`):

| Task | Treatment Median | Control Median | Winner |
|------|-----------------|----------------|--------|
| Function Minimization | 1.4994 | 1.4994 | Tie |
| Circle Packing | 0.935 | 0.961 | Control |
| BLIS Router | -3867.2 | -3859.3 | Control |

Tuning provided no statistically significant benefit on any task.

### Root causes identified

1. **Prompt conditioning problem:** The v1 prompt told the LLM to "choose the most impactful parameters" and "focus on parameters where you're uncertain." This reframed the LLM's objective from "invent better algorithms" to "write code with tunable knobs." Control LLMs, without these instructions, freely invented structural innovations (adaptive weight blending in BLIS, parametric grid search in circpack) that treatment LLMs never found.

2. **Tuning every program every iteration:** v1 tuned every evolved program regardless of quality. Data showed 68% of tuning effort was spent on already-good programs (score > population median) with average gain of +0.01. Meanwhile, tuning poor-but-novel programs yielded gains of +0.70 on average — the "good algorithm, bad thresholds" rescue case.

3. **Massive time overhead:** Tuning added 19 evaluations per iteration. For BLIS (Go build + simulation per eval), this meant 324 seconds/iteration — a 6-8x slowdown. In the same wall-clock time, control could have run ~200 pure evolution iterations.

4. **Redundant evaluation bug:** After `tune_program()` ran 20 evaluations (1 baseline + 19 trials), the caller evaluated the tuned code AGAIN (21st eval) because `tune_program()` didn't return the best trial's metrics.

5. **No cross-iteration learning:** Optuna started fresh every iteration. Even when the same algorithm was tuned twice, previous trial history was discarded. Each iteration re-discovered the same optimal values from scratch.

6. **LLM creativity constraint:** The @TUNE parser only supports `var = constant # @TUNE [min, max]`. In circpack, the LLM attempted formula-based parameters (`1.0 / (ny + 1)`, `radii * 0.3 + max_r * 0.7`) that were rejected by the regex, wasting those iterations.

---

## v2 Design Principles

1. **LLM innovates algorithms. Optuna tunes parameters.** The prompt must frame the LLM's role as algorithmic invention, not parameter selection.

2. **Tune selectively, not universally.** Only tune programs where tuning has high expected value: novel-but-low-scoring programs (rescue) and elite programs at checkpoints (polish).

3. **Minimize evolution tax.** Tuning overhead must not crowd out evolutionary exploration. Use a tiered trial budget: tiny for rescue, moderate for checkpoint polish, thorough only at the final iteration.

4. **No redundant computation.** `tune_program()` returns metrics. The caller skips re-evaluation.

5. **Warm hints, not warm-starts.** Seed Optuna with parent's tuned values via `enqueue_trial()`, but never persist studies across iterations (the objective function changes when the algorithm changes).

6. **Optuna is invisible to the LLM.** The LLM never sees @TUNED feedback. It sees only the optimized values written into the code and any @TUNE annotations it placed. This prevents the LLM from anchoring on parameter tuning results and keeps its full attention on algorithmic innovation. @TUNED is used internally only — for warm hints between parent and child Optuna runs.

7. **Minimal prompt footprint.** The tuning instructions in the LLM prompt must be as short as possible (3-5 lines). Every token spent on tuning instructions is a token not spent on algorithmic reasoning.

---

## Annotation Format (unchanged from v1)

### Declaring tunable parameters

```python
# Python
load_cutoff = 0.4  # @TUNE [0.0, 1.0]
batch_size = 32  # @TUNE [8, 128] int

# Go
loadPenalty := 2.0 // @TUNE [0.5, 5.0]
maxRetries := 3 // @TUNE [1, 10] int
```

Only numeric types (float, int). Categorical/strategy choices are algorithmic decisions.

### After tuning — internal optimizer feedback (NOT shown to LLM)

@TUNED annotations are written internally after Optuna optimization:

```python
load_cutoff = 0.67  # @TUNE [0.0, 1.0] @TUNED(was=0.4, gain=+0.12, best_impact=throughput:+0.3)
```

- `gain` = total `combined_score` delta from tuning all parameters jointly
- `best_impact` = single most-impacted metric and its delta

**Critical: @TUNED is stripped before code enters the database or is shown to the LLM.** The LLM only sees the optimized value and the @TUNE range:

```python
load_cutoff = 0.67  # @TUNE [0.0, 1.0]
```

Additionally, when `|gain| < 0.01` (parameter is insensitive), @TUNE is also stripped — the line becomes a plain assignment:

```python
load_cutoff = 0.67
```

This prevents @TUNE annotations from accumulating on parameters that don't matter.

@TUNED is used internally only for:
1. Warm hints — extracting parent's tuned values for `enqueue_trial()` in child Optuna runs
2. Logging/tracking — recording tuning effectiveness in `IterationTuningStats`

### Parsing regex

```
^(\s*(\w+)\s*:?=\s*(.+?)\s*)(?:#|//)\s*@TUNE\s+\[([^,\]]+),\s*([^\]]+)\](\s+(?:int|float))?
```

Supports Python `#` and Go/Rust/C++ `//` comments, and Go `:=` assignment.

### Rules (unchanged)

- Max `max_params` (default 3) @TUNE per program. Excess annotations ignored.
- @TUNE must appear on a simple assignment line.
- @TUNED annotations stripped before each tuning run.

---

## v2 Tuning Pipeline

### Tiered tuning strategy

v2 replaces v1's "tune everything every iteration" with a three-tier approach that graduates trial budget by context:

#### Tier 1: Rescue Tuning (per-iteration, selective) — 5 trials

**Purpose:** Save novel algorithms that have bad parameter values. This is a screening operation: "is this algorithm salvageable with better numbers?"

**Selection criteria:** A program is a rescue candidate if:

```
IF  score < population_median  AND  diversity > diversity_median:
    → TUNE (novel algorithm, likely bad thresholds)
ELIF  score < population_p25:
    → TUNE (very poor score, cheap insurance)
ELSE:
    → SKIP (already good, or unoriginal)
```

**Trial budget:** Minimal — **5 trials** flat. With a warm hint as trial 0, this gives 4 real exploration trials. Enough to detect signal without significant overhead.

**Rationale:** The A/B data showed that 68% of v1 tuning effort was spent on programs scoring above the population median, with average gain +0.01. Rescue mode targets the remaining 32% where average gain was +0.47 — a 47x better return on investment. The budget is deliberately tiny: rescue is a binary question ("can this be saved?"), not a thorough optimization.

#### Tier 2: Checkpoint Polish (at checkpoints) — 10 trials

**Purpose:** Moderate optimization of elite programs at intermediate checkpoints. The population is still evolving, so thorough optimization isn't worth the cost — but a quick polish can improve the parent programs that future LLM iterations build on.

**When:** At every `checkpoint_interval` (but NOT the final iteration — that uses Tier 3).

**What:** Tune the top-K programs (default K=3) from each island.

**Trial budget:** Moderate — **10 trials** flat. With warm hint, this is 1 seeded + 9 exploration trials.

**Database update:** If the polished version scores higher than the original, replace it in the database. Otherwise keep the original.

**Rationale:** Intermediate polish improves the starting points that the LLM evolves from. A 25-iteration run with `checkpoint_interval=5` does checkpoint polish at iterations 5, 10, 15, 20 — 4 rounds of moderate optimization.

#### Tier 3: Final Polish (at final iteration only) — 20 trials

**Purpose:** Thorough optimization of the best programs found. Evolution is done — this is the last chance to squeeze out parameter gains.

**When:** At the final iteration only.

**What:** Tune the top-K programs (default K=3) from each island with the largest trial budget.

**Trial budget:** Thorough — **20 trials** flat. This is where we invest the most per-program, since these are the final results.

**Rationale:** The final iteration's elites represent the best algorithms discovered. They deserve thorough parameter optimization because no further algorithmic evolution will occur. The cost is amortized: one round of 20 trials × 3 elites = 60 evaluations, paid once.

### Integration point in iteration flow

```
BEFORE (v1):
  LLM generates code → tune ALL programs (19 trials) → evaluate AGAIN → store in DB

AFTER (v2):
  LLM generates code → [rescue tune IF selected, 5 trials] → evaluate → store in DB
  At checkpoints:     → [polish top-K elites, 10 trials] → update DB if improved
  At final iteration: → [polish top-K elites, 20 trials] → update DB if improved
```

### Warm hint via enqueue_trial

When a program has @TUNE annotations, seed Optuna with the current values in the code:

```python
parent_values = extract_current_tune_values(child_code)  # from @TUNE lines
study = optuna.create_study(direction="maximize", sampler=TPESampler())

if parent_values:
    # Seed the current values as trial 0
    study.enqueue_trial(parent_values)

study.optimize(objective, n_trials=trial_budget)
```

**Why not warm-start the full study?** Because the objective function changes when the algorithm changes. A parameter named `temp` in a simulated annealing program has completely different semantics than `temp` in a basin-hopping program. Reusing the full TPE history would poison the sampler with irrelevant data.

**Why enqueue_trial works:** It gives TPE a single known-good starting point without constraining future exploration. If the algorithm changed and the old values are bad, TPE moves away after 1-2 trials. If similar, TPE saves budget. Cost: zero (it's just trial 0 of the budget we'd spend anyway).

### Extracting current values for warm hint

Since @TUNED is stripped before code enters the database, the warm hint extracts the *current assigned value* from @TUNE lines — this is the Optuna-optimized value from the parent's tuning run (already written into the code):

```python
def extract_current_tune_values(code: str) -> dict:
    """Extract current values from lines that have @TUNE annotations.

    Since @TUNED is stripped before DB storage, the current value on a
    @TUNE line IS the best value from any prior tuning run (or the LLM's
    original guess if never tuned). Either way, it's a good seed.
    """
    values = {}
    for line in code.split("\n"):
        tune_match = _TUNE_RANGE_RE.match(line)
        if tune_match:
            name = tune_match.group(2)
            value = float(tune_match.group(3).strip())
            values[name] = value
    return values
```

Note: this is simpler than the v2-draft's `extract_tuned_values()` which required @TUNED to be present. Since @TUNED is now stripped before DB storage, we extract from the @TUNE line itself.

---

## v2 LLM Prompt Template

This is the most critical change. The v1 prompt framed the LLM as a parameter selector. The v2 prompt is intentionally minimal — it gives the LLM just enough to use @TUNE without reframing its objective.

### What changed and why

| Aspect | v1 | v2 |
|--------|----|----|
| Prompt length | ~30 lines, 12 mentions of @TUNE | **5 lines**, 2 mentions of @TUNE |
| Opening frame | "You may annotate parameters with @TUNE" | "An optimizer tunes numeric parameters" |
| LLM's role | Parameter selector | Algorithm inventor (implicit) |
| @TUNE guidance | "Choose the most impactful parameters" | "Mark values you're uncertain about" |
| @TUNED feedback | Shown to LLM with interpretation guide | **Never shown to LLM** |
| Anti-patterns | (missing in v1, added but verbose in v2-draft) | Omitted — less is more |
| Closing principle | (missing) | Omitted — no reframing needed |

### Design rationale: minimal prompt footprint

Three independent reviewers flagged that the v2-draft's 29-line prompt still primed the LLM on parameter thinking. Every line about @TUNE — even anti-patterns ("do NOT add @TUNE to avoid decisions") — draws attention to tuning at the expense of algorithms. The "don't think about elephants" problem.

The solution: **make the prompt so short it barely registers.** The LLM's primary task (algorithmic innovation) is never mentioned in the tuning instructions — it comes from the evolution prompt itself. The tuning instructions just explain the @TUNE syntax, nothing more.

### New template

```python
THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE = """

## Automatic Parameter Optimization

An optimizer automatically tunes numeric parameters in your code after generation.
If your code has a numeric value you're uncertain about, mark it:
  `var = value  # @TUNE [min, max]` (or `// @TUNE` for Go/Rust/C++)
Focus your effort on better algorithms, not better numbers. Max 3 annotations.
"""
```

**4 lines.** The LLM knows: (1) an optimizer exists, (2) how to mark parameters, (3) there's a cap of 3, (4) focus on algorithms. Nothing more.

### What the LLM does NOT see

- No @TUNED annotations (stripped before DB storage — see Annotation Format section)
- No gain/impact metrics from previous tuning runs
- No guidance on interpreting tuning results
- No anti-patterns or warnings about parameter obsession
- No examples of good vs bad @TUNE candidates

All of these were in the v2-draft and removed. The less the LLM thinks about tuning, the more it thinks about algorithms.

### Evidence for this approach

From the v1 A/B experiments:

- **BLIS control** discovered adaptive weight blending (structural innovation) while treatment optimized static threshold penalties. Control scored -3856 vs treatment -3881.
- **Circpack control** discovered parametric grid search and normalized direction vectors while treatment tuned `step_size` and `spacing_x`. Control scored 0.961 vs treatment 0.935.
- **Circpack treatment logs** showed 6+ parsing failures where the LLM tried formula-based parameters (creative ideas) that the @TUNE regex rejected.

The v1 prompt steered the LLM toward parameters. The v2 prompt is deliberately terse — @TUNE is a footnote, not the main event.

---

## Configuration

### New config structure

```yaml
tuning:
  enabled: true                    # Master switch
  max_params: 3                    # Hard cap on @TUNE annotations honored

  # Tiered trial budgets (flat counts, no per-param scaling)
  rescue_trials: 5                 # Rescue: screening question, tiny budget
  checkpoint_trials: 10            # Checkpoint polish: moderate optimization
  final_trials: 20                 # Final polish: thorough optimization
  polish_top_k: 3                  # Tune top-K programs per island at polish time
```

### Defaults

```python
@dataclass
class TuningConfig:
    enabled: bool = False
    max_params: int = 3

    # Tiered trial budgets (flat counts)
    rescue_trials: int = 5         # Per-iteration rescue (selective)
    checkpoint_trials: int = 10    # Polish at checkpoint intervals
    final_trials: int = 20         # Polish at final iteration
    polish_top_k: int = 3          # Top-K programs per island to polish
```

The per-param scaling from the v2-draft (`budget + scale * num_params`) is removed. Flat trial counts are simpler to reason about and configure. With 3 params max, the scaling added at most 3-9 trials — not worth the complexity.

### Backward compatibility

v1 configs with `budget` are mapped to `rescue_trials`:

```python
if "budget" in tuning_dict and "rescue_trials" not in tuning_dict:
    # v1 had a single budget; map to rescue (closest equivalent)
    tuning_dict["rescue_trials"] = tuning_dict.pop("budget")
    tuning_dict.pop("budget_scale_per_param", None)  # drop per-param scaling
```

v2-draft configs with `rescue_budget`/`polish_budget` are also mapped:

```python
if "rescue_budget" in tuning_dict and "rescue_trials" not in tuning_dict:
    tuning_dict["rescue_trials"] = tuning_dict.pop("rescue_budget")
    tuning_dict.pop("rescue_scale_per_param", None)
if "polish_budget" in tuning_dict and "checkpoint_trials" not in tuning_dict:
    tuning_dict["checkpoint_trials"] = tuning_dict.pop("polish_budget")
    tuning_dict.pop("polish_scale_per_param", None)
```

### Interaction with hypothesis_driven

Independent flags. You can run neither, hypotheses only, tuning only, or both. This enables clean A/B and factorial experiments.

---

## tune_program() API Change

### v1 signature

```python
async def tune_program(
    code: str,
    evaluate_fn: Callable,
    config: TuningConfig,
) -> Tuple[str, IterationTuningStats]:
```

### v2 signature

```python
async def tune_program(
    code: str,
    evaluate_fn: Callable,
    config: TuningConfig,
    mode: str = "rescue",               # "rescue", "checkpoint", or "final"
    baseline_metrics: dict = None,       # pre-computed baseline (avoids redundant eval)
) -> Tuple[str, IterationTuningStats, Optional[dict]]:
    #                                      ↑ returns best trial metrics (or None)
```

Changes:
- `mode` selects trial budget (`rescue` → 5, `checkpoint` → 10, `final` → 20)
- `baseline_metrics` accepts pre-computed evaluation (from rescue pre-eval or DB) to avoid redundant baseline evaluation inside tune_program
- Returns `Optional[dict]` of best trial metrics to eliminate redundant post-tune eval
- Warm hint is extracted from the code's current @TUNE values (no @TUNED needed)

### Internal flow

```python
async def tune_program(code, evaluate_fn, config, mode="rescue", baseline_metrics=None):
    stats = IterationTuningStats()

    code = strip_tuned_annotations(code)  # strip any residual @TUNED
    params = parse_tune_annotations(code, max_params=config.max_params)
    if not params:
        return code, stats, None  # no @TUNE, no metrics to return

    # Select budget based on mode (flat counts)
    if mode == "final":
        n_trials = config.final_trials
    elif mode == "checkpoint":
        n_trials = config.checkpoint_trials
    else:
        n_trials = config.rescue_trials

    # Baseline evaluation (reuse pre-computed if available)
    if baseline_metrics:
        original_metrics = baseline_metrics
    else:
        original_metrics = await evaluate_fn(code, "tune_baseline")
    original_score = original_metrics.get("combined_score", 0.0)

    # Extract warm hint from current @TUNE values in code
    current_values = extract_current_tune_values(code)

    # Create study with warm hint
    study = optuna.create_study(direction="maximize", sampler=TPESampler())
    if current_values:
        seed = {p.name: current_values[p.name]
                for p in params if p.name in current_values}
        if seed:
            study.enqueue_trial(seed)

    # Run Optuna
    study.optimize(objective, n_trials=n_trials)

    # Apply best if improved
    best_trial = study.best_trial
    if best_trial.value > original_score:
        best_metrics = best_trial.user_attrs.get("metrics", original_metrics)
        # rewrite_tune_values writes @TUNED internally for logging,
        # then strip_tuned_for_db() removes it before DB storage
        result_code = rewrite_tune_values(code, params, best_trial.params,
                                          original_score, best_trial.value,
                                          original_metrics, best_metrics)
        result_code = strip_tuned_for_db(result_code, gain_threshold=0.01)
        return result_code, stats, best_metrics  # ← metrics returned
    else:
        return code, stats, original_metrics  # ← original metrics returned
```

### strip_tuned_for_db() — the @TUNED firewall

This function ensures @TUNED never reaches the database or LLM:

```python
def strip_tuned_for_db(code: str, gain_threshold: float = 0.01) -> str:
    """Strip @TUNED annotations before code enters the database.

    - All @TUNED(...) annotations are removed
    - If |gain| < gain_threshold, also strip @TUNE (parameter is insensitive)
    - The optimized VALUE remains in the code (the LLM sees the number)
    """
    lines = []
    for line in code.split("\n"):
        if "@TUNED" in line:
            gain = _extract_gain(line)  # parse gain from @TUNED(...)
            if gain is not None and abs(gain) < gain_threshold:
                # Insensitive param: strip both @TUNE and @TUNED
                line = _strip_tune_annotation(line)
            else:
                # Sensitive param: keep @TUNE, strip @TUNED
                line = _strip_tuned_only(line)
        lines.append(line)
    return "\n".join(lines)
```

---

## Rescue Selection Logic

### Where it runs

In `process_parallel.py`, after LLM code generation and before evaluation:

```python
# After child_code is generated by LLM...

should_rescue = False
tuning_metrics = None

if _worker_config.tuning.enabled and has_tune_annotations(child_code):
    # Get population stats from database snapshot
    pop_scores = [p["metrics"].get("combined_score", 0)
                  for p in db_snapshot["programs"].values()
                  if p.get("metrics")]
    pop_diversities = [p.get("diversity", 0)
                       for p in db_snapshot["programs"].values()]

    if pop_scores and pop_diversities:
        score_median = median(pop_scores)
        score_p25 = percentile(pop_scores, 25)
        diversity_median = median(pop_diversities)

        # Use database's existing fast_code_diversity against reference set
        # (same mechanism used for MAP-Elites feature mapping)
        child_diversity = db_diversity_score(child_code, db_snapshot)

        # Evaluate child first to get its un-tuned score
        pre_tune_metrics = await evaluate_fn(child_code, "pre_tune")
        pre_tune_score = pre_tune_metrics.get("combined_score", 0)

        if pre_tune_score < score_median and child_diversity > diversity_median:
            should_rescue = True  # Novel algorithm, bad thresholds
        elif pre_tune_score < score_p25:
            should_rescue = True  # Very poor, cheap insurance

if should_rescue:
    child_code, tuning_stats, tuning_metrics = await tune_program(
        child_code, evaluate_fn, config.tuning,
        mode="rescue",
        baseline_metrics=pre_tune_metrics)  # reuse pre-eval as baseline

# Final evaluation (skip if tuning already evaluated)
if tuning_metrics:
    child_metrics = tuning_metrics
else:
    child_metrics = pre_tune_metrics  # already evaluated, no waste
```

Note: `extract_tuned_values()` is no longer needed here — `tune_program()` extracts the warm hint internally from @TUNE lines.

### Diversity estimation — reusing existing infrastructure

OpenEvolve's `ProgramDatabase` already computes diversity for MAP-Elites feature mapping:

- **`_fast_code_diversity(code1, code2)`** — lightweight score using length diff, line diff, and character set diff
- **`_get_cached_diversity(program)`** — cached computation against a greedy max-diversity reference set of 20 programs
- **`Program.diversity`** field — stored on every program in the database

For rescue selection, we reuse this same mechanism rather than implementing a separate estimator:

```python
def db_diversity_score(child_code: str, db_snapshot: dict) -> float:
    """Compute diversity of child code against population using the database's
    existing _fast_code_diversity function and diversity reference set.

    This is the same metric used for MAP-Elites binning, ensuring consistency
    between rescue selection and feature mapping.
    """
    reference_codes = db_snapshot.get("diversity_reference_set", [])
    if not reference_codes:
        # Fallback: use codes from first 20 programs
        reference_codes = [p["code"] for p in list(db_snapshot["programs"].values())[:20]
                          if p.get("code")]

    scores = []
    for ref_code in reference_codes:
        if ref_code != child_code:
            scores.append(_fast_code_diversity(child_code, ref_code))

    return sum(scores) / max(1, len(scores)) if scores else 0.0
```

The `diversity_median` for rescue selection is computed from the existing `Program.diversity` values already stored in the database — no extra computation needed:

```python
pop_diversities = [p["diversity"] for p in db_snapshot["programs"].values()]
```

### Note on pre-tune evaluation cost

The rescue selection path evaluates the child once (`pre_tune_metrics`) to determine its score before deciding whether to tune. This is a per-iteration tax (~20s for BLIS), but it is NOT wasted:

- **If rescue fires:** `pre_tune_metrics` is passed as `baseline_metrics` to `tune_program()`, which skips its own baseline evaluation. Zero redundant evals.
- **If rescue is skipped:** `pre_tune_metrics` becomes the final child evaluation. Zero redundant evals.

The pre-eval is the child's only evaluation in all code paths — it just happens earlier in the pipeline (before the rescue decision) rather than later (after).

---

## Polish Tuning Logic

### Where it runs

In `ProcessParallelController.run_evolution()`, at checkpoint and final callbacks:

```python
async def _polish_elites(self, iteration: int, is_final: bool = False):
    """Tune top-K elite programs. Uses checkpoint budget normally, final budget at end."""
    if not self.config.tuning.enabled:
        return

    mode = "final" if is_final else "checkpoint"

    for island_id in range(self.num_islands):
        island_programs = self.database.get_island_programs(island_id)
        if not island_programs:
            continue

        # Sort by combined_score, take top-K
        sorted_progs = sorted(
            island_programs,
            key=lambda p: p.metrics.get("combined_score", 0),
            reverse=True
        )
        top_k = sorted_progs[:self.config.tuning.polish_top_k]

        for prog in top_k:
            if not has_tune_annotations(prog.code):
                continue  # nothing to tune

            polished_code, stats, polished_metrics = await tune_program(
                prog.code,
                self.evaluator.evaluate_program,
                self.config.tuning,
                mode=mode,  # "checkpoint" (10 trials) or "final" (20 trials)
                baseline_metrics=prog.metrics,  # reuse existing metrics
            )

            if polished_metrics:
                polished_score = polished_metrics.get("combined_score", 0)
                original_score = prog.metrics.get("combined_score", 0)

                if polished_score > original_score:
                    prog.code = polished_code
                    prog.metrics = polished_metrics
                    self.database.update(prog)
                    logger.info(
                        f"[TUNE-{mode.upper()}] Improved {prog.id} on island {island_id}: "
                        f"{original_score:.4f} → {polished_score:.4f} "
                        f"(+{polished_score - original_score:.4f})"
                    )

            if self.tuning_tracker:
                self.tuning_tracker.record(stats)
```

### When it runs

```python
# At intermediate checkpoints — moderate budget (10 trials)
if completed_iteration % self.config.checkpoint_interval == 0:
    checkpoint_callback(completed_iteration)
    if completed_iteration < max_iterations:
        await self._polish_elites(completed_iteration, is_final=False)

# At final iteration — thorough budget (20 trials)
if completed_iterations >= max_iterations:
    await self._polish_elites(completed_iterations, is_final=True)
```

---

## Interaction with Existing Features

### With hypotheses

Both coexist. Iteration order:

```
LLM generates code
  → rescue_hypotheses()              (if hypothesis_driven)
  → [rescue tune IF selected]        (if tuning.enabled + criteria met)
  → evaluate
  → inject_result_comments()         (if hypothesis_driven)
  → store in DB

At checkpoints:
  → polish top-K elites              (if tuning.enabled)
  → save checkpoint
```

### With diff-based evolution

@TUNE annotations live on normal assignment lines. Diffs add, remove, or change them naturally. @TUNED is never present in the database, so diffs never see it.

### With MAP-Elites / islands

Rescue tuning uses population statistics (median score, median diversity) for selection. Polish tuning operates per-island on the top-K programs.

### With process-parallel workers

Rescue tuning runs inside the worker process (same as v1). Polish tuning runs in the main controller process at checkpoint time — it has direct database access and doesn't need serialization.

### A/B testing

Same pattern as v1. `tuning.enabled: true` in treatment, `false` in control. The `scripts/run_experiment.py` works unchanged.

---

## Tracking and Observability

### IterationTuningStats (extended)

```python
@dataclass
class IterationTuningStats:
    iteration: int = 0
    mode: str = ""                           # "rescue", "checkpoint", "final", or "skipped"
    tune_annotations_found: int = 0
    tune_annotations_honored: int = 0
    tuning_ran: bool = False
    tuning_duration_s: Optional[float] = None
    original_score: Optional[float] = None
    tuned_score: Optional[float] = None
    gain: Optional[float] = None
    trials_completed: int = 0
    trials_failed: int = 0
    param_changes: dict = field(default_factory=dict)
    warm_hint_used: bool = False             # whether enqueue_trial was used
    selection_reason: str = ""               # "novel_low_score", "very_poor", "checkpoint_elite", "final_elite"
    annotations_stripped: int = 0            # @TUNE removed due to gain ≈ 0
```

### TuningTracker summary (extended)

```python
def summary(self) -> dict:
    return {
        "total_iterations_tracked": ...,
        "rescue_count": ...,           # iterations where rescue tuning ran
        "checkpoint_polish_count": ...,# programs polished at intermediate checkpoints
        "final_polish_count": ...,     # programs polished at final iteration
        "skip_count": ...,             # iterations where tuning was skipped
        "rescue_avg_gain": ...,
        "checkpoint_polish_avg_gain": ...,
        "final_polish_avg_gain": ...,
        "total_trials": ...,
        "total_tuning_wall_clock_s": ..., # total wall-clock spent on tuning
        "avg_tuning_duration_s": ...,
        "warm_hint_hit_rate": ...,     # % of warm hints that were close to best
        "annotations_stripped_total": ..., # @TUNE removed due to gain ≈ 0
        "tune_annotation_rate": ...,   # % of iterations with @TUNE annotations (manipulation check)
        "per_iteration": [...],
    }
```

### Log messages

```
[TUNE-RESCUE]     iter=8  | score=0.50<median(1.20) div=245>median(180) → tuning | 5 trials | 0.50→1.49 gain=+0.99
[TUNE-SKIP]       iter=9  | score=1.48>median(1.20) → skipping rescue
[TUNE-CHECKPOINT] iter=10 | island=0 | prog=abc123 | 10 trials | 1.48→1.50 gain=+0.02
[TUNE-CHECKPOINT] iter=10 | island=0 | prog=def456 | 10 trials | 1.47→1.47 gain=+0.00 (no improvement)
[TUNE-FINAL]      iter=25 | island=0 | prog=abc123 | 20 trials | 1.50→1.52 gain=+0.02
[TUNE-STRIP]      iter=8  | stripped @TUNE from 'decay_rate' (gain=+0.003, below threshold 0.01)
```

---

## Expected Performance Impact

### Evaluation budget comparison (25 iterations, BLIS router, ~20s/eval)

| Metric | v1 | v2 |
|--------|----|----|
| Rescue-tuned iterations | 25/25 (100%) | ~8/25 (32%) |
| Trials per rescue | 19 | **5** |
| Checkpoint polish rounds | 0 | 4 (at iter 5, 10, 15, 20) |
| Trials per checkpoint polish (×3 elites) | — | **10 × 3 = 30** |
| Final polish rounds | 0 | 1 (at iter 25) |
| Trials per final polish (×3 elites) | — | **20 × 3 = 60** |
| Redundant post-tune evals | 25 | 0 |
| **Total tuning evaluations** | **500** (19×25 + 25) | **~220** (5×8 + 30×4 + 60×1) |
| **Total tuning wall-clock** | **~2.8 hours** | **~1.2 hours** |

v2 uses **56% fewer evaluations** than v1, with the budget graduated by value:
- Rescue (40 evals, ~13 min): cheap screening of novel programs
- Checkpoint polish (120 evals, ~40 min): moderate optimization of evolving elites
- Final polish (60 evals, ~20 min): thorough optimization of the best algorithms found

### Where the savings come from

1. **Skip 68% of iterations** (programs above median score): saves ~323 evaluations
2. **Tiny rescue budget** (5 vs 19 trials): saves ~112 evaluations on rescue iterations
3. **Zero redundant evals**: saves 25 evaluations
4. **Tiered polish** adds ~180 evaluations (vs v2-draft's ~360) — half the polish cost

### LLM creativity comparison

| Metric | v1 | v2 (expected) |
|--------|----|----|
| LLM prompt about tuning | ~30 lines, 12× @TUNE mentions | **4 lines**, 2× @TUNE mentions |
| @TUNED feedback shown | Yes (biases toward parameters) | **No** (hidden from LLM) |
| LLM's effective task | "Invent + select parameters" | "Invent algorithms" (same as control) |
| Structural innovations | Rare (LLM stuck on parameters) | Expected: same rate as control |
| @TUNE as constraint | Yes (LLM designs for tunability) | No (footnote, not main event) |

---

## Files Overview

| File | Action | What |
|------|--------|------|
| `openevolve/tuning.py` | Modify | Add `mode` param (rescue/checkpoint/final), return metrics, warm hint, `strip_tuned_for_db()`, `extract_current_tune_values()` |
| `openevolve/config.py` | Modify | Tiered `TuningConfig` with `rescue_trials`/`checkpoint_trials`/`final_trials`, `polish_top_k` |
| `openevolve/process_parallel.py` | Modify | Rescue selection logic, pass `baseline_metrics`, tiered polish at checkpoints + final |
| `openevolve/prompt/templates.py` | Modify | Replace `THRESHOLD_TUNING_INSTRUCTIONS_TEMPLATE` with 4-line v2 version |
| `openevolve/prompt/sampler.py` | No change | Already appends template when `tuning.enabled` |
| `tests/test_tuning.py` | Modify | Add tests for: rescue selection, tiered polish, warm hint from @TUNE values, metrics return, `strip_tuned_for_db()`, gain-threshold @TUNE stripping |
| `scripts/run_experiment.py` | Modify | Increase timeout to 14400s (already done) |

---

## Migration from v1

v1 configs work unchanged. The `budget` field is auto-mapped to `rescue_trials`. Per-param scaling is dropped. Polish uses defaults. The prompt template change and @TUNED hiding are automatic (no config needed).

To opt into v2 with custom tiered budgets:

```yaml
tuning:
  enabled: true
  rescue_trials: 5          # screening question: is this algorithm salvageable?
  checkpoint_trials: 10     # moderate polish at intermediate checkpoints
  final_trials: 20          # thorough polish at the end
  polish_top_k: 3           # top-K programs per island to polish
```

---

## Resolved Design Decisions

These were open questions in earlier drafts, now resolved based on three independent design reviews:

1. **@TUNED visibility → Hidden from LLM.** All three reviewers unanimously agreed: @TUNED must not be shown to the LLM. The optimized value is already in the code; @TUNED meta-information (gain, was, impact) anchors the LLM on parameter thinking. @TUNED is used internally only for warm hints and logging. Additionally, @TUNE is auto-stripped when `|gain| < 0.01` to prevent insensitive annotations from accumulating.

2. **Prompt length → Minimal (4 lines).** All three reviewers recommended dramatic reduction. The v2-draft's 29-line prompt still mentioned @TUNE 12 times. The final 4-line prompt gives the LLM syntax knowledge without reframing its task. Less prompt = more algorithmic creativity.

3. **Trial budgets → Tiered (5/10/20).** Graduated by context: rescue is a binary screening question (5 trials), checkpoint polish is moderate maintenance (10 trials), final polish is thorough end-of-run optimization (20 trials). Flat counts, no per-param scaling.

4. **Polish timing → Checkpoints + final, not just final.** Intermediate polish at checkpoints improves the parent programs that future LLM iterations evolve from. With 10 trials per checkpoint (not 24), the wall-clock cost is manageable (~10 min per checkpoint for BLIS, vs ~24 min with the v2-draft's budget).

5. **Rescue pre-evaluation → Keep it.** The per-iteration eval tax (~20s for BLIS) is acceptable because: (a) the eval is reused as the child's final evaluation when rescue is skipped, (b) it's reused as the baseline when rescue fires, (c) 8 min total over 25 iterations is small relative to the run's total time.

## Remaining Open Questions

1. **@TUNE annotation rate:** What if the LLM stops generating @TUNE annotations because the minimal prompt de-emphasizes them? The 4-line prompt says "mark values you're uncertain about" which is permissive, but some LLMs might interpret the brevity as "this is unimportant." Mitigation: monitor `tune_annotation_rate` in the tracker. If it drops to zero, the prompt may need a small nudge.

2. **Diversity estimation accuracy:** We reuse the database's existing `_fast_code_diversity()` and reference set for consistency with MAP-Elites. This is a fast approximation (length diff + line diff + character set diff) — not perfect (variable renames inflate scores), but it's the same metric the rest of the system uses for diversity binning, so rescue selection and MAP-Elites agree on what "diverse" means.

3. **Experiment design:** Three reviewers recommended a 3-arm experiment (control / prompt-only / full treatment) to isolate whether the prompt change or Optuna tuning drives the result. This adds experimental cost but provides cleaner causal evidence. Also recommended: increase from 2 to 4+ seeds per condition for statistical power.

---

## A/B Experiment Candidates

Examples ranked by expected tuning benefit. Best candidates have: known algorithm families with numeric calibration, clean continuous eval signal, and fast evaluators.

### HIGH — Primary A/B targets

| Example | Eval Speed | Key @TUNE Targets | Why Tuning Helps |
|---|---|---|---|
| `function_minimization` | ~0.1s | step size, temperature, cooling rate, restart count | Any evolved optimizer (SA, CMA-ES, gradient) lives/dies by hyperparameters |
| `r_robust_regression` | ~1s | Huber delta, RANSAC threshold, breakdown point, regularization λ | Textbook threshold-sensitive domain; bias-variance trade-off under outliers |
| `circle_packing` | ~0.5s | SA temp/cooling, perturbation magnitude, ring radii (already hardcoded 0.3, 0.7) | Local search parameters directly determine packing quality |
| `blis_router` | ~20s | scorer weights (prefix vs load vs kv), hysteresis thresholds, decay constants | WeightedScoring is explicitly weight-based; optimal mix depends on workload |
| `sldbench` | ~2s | num_restarts, lr, regularization, convergence tolerance, init_scale | Parametric function fitting; optimizer hyperparameters control fit quality |

### MEDIUM — Conditional benefit

| Example | Notes |
|---|---|
| `rust_adaptive_sort` | `is_nearly_sorted` threshold and insertion-sort cutoff matter, but structural choice dominates |
| `alphaevolve_math_problems/matmul` | Explicit `Hyperparameters` dataclass (lr, restarts, l1_strength), but algorithmic trick (STE) is the real win |
| `alphaevolve_math_problems` (geometry) | Only helps if LLM evolves a local-search optimizer; constructive solutions have nothing to tune |

### LOW — Skip

`k_module_problem` (categorical only), `toygosys` (discrete integers, slow eval), `online_judge_programming` (correctness, no thresholds), `lm_eval` / `llm_prompt_optimization` (text, not code), `attention_optimization` (discrete flags, noisy eval), `symbolic_regression` (evaluator already optimizes params internally).

### Recommended A/B order

1. **function_minimization** — fastest eval, cleanest signal, run first
2. **r_robust_regression** — fast eval, strong threshold sensitivity
3. **circle_packing** — already tested in v1 (baseline data exists)
4. **blis_router** — highest real-world stakes but 20s/eval makes tuning overhead costly
