# A/B Experiment Guide

How to run A/B experiments for OpenEvolve features. Three independent features can be A/B tested:

| Feature | Config Flag | What It Does |
|---------|------------|--------------|
| **Hypothesis** | `hypothesis_driven: true/false` | LLM writes structured HYPOTHESIS/EXPECT comments; RESULT verdicts auto-injected |
| **Tuning (v2)** | `tuning.enabled: true/false` | LLM annotates params with `@TUNE`; Optuna optimizes via tiered rescue/polish |
| **Combined** | Both flags | Hypothesis + Tuning together |

---

## CRITICAL: Execution Rules

### 1. ALWAYS run experiments sequentially — NEVER in parallel

**Run order**: `--condition both` interleaves treatment and control **by seed** — each
treatment run is immediately followed by its matching control run before moving to the next seed.

```bash
# CORRECT: single process, interleaved by seed (default)
python scripts/run_experiment.py --task <task> --condition both --runs 3 ...
# Execution order: treatment_500, control_500, treatment_501, control_501, treatment_502, control_502

# WRONG: two parallel processes — causes data corruption
python scripts/run_experiment.py --task <task> --condition treatment ... &
python scripts/run_experiment.py --task <task> --condition control ... &
```

**Why interleaved**: Interleaving controls for time-of-day LLM variation and lets you
validate the pipeline on both conditions early (after seed 0 completes, you have one
treatment and one control to compare). Use `--no-interleave` to group by condition
(all treatment first, then all control) if you have a specific reason.

**Why sequential**: Some evaluators (especially BLIS router) write to shared files (e.g.,
`routing.go`). Parallel runs will clobber each other, producing corrupt results. Even for
evaluators that don't share files (funcmin, circpack), parallel `run_experiment.py` processes
write to the same output directory and can race on `convergence.csv` / `run_results.json`.

### 2. ALWAYS start from a clean state

Before re-running an experiment, **move** the old data to `experiments/old/` with a version suffix:

```bash
mv experiments/tuning_ab_funcmin experiments/old/tuning_ab_funcmin_v1   # archive old data
# then run fresh
python scripts/run_experiment.py --task function_minimization_tuning ...
```

**NEVER** use `rm -rf` on experiment data. NEVER delete the entire `experiments/` directory
or other experiments' data. Always archive to `experiments/old/`.

**Why**: Leftover checkpoint directories, tracker files, or stale `convergence.csv` from
previous runs can contaminate results or cause the experiment runner to skip/overwrite runs.
Archiving preserves data for later comparison.

### 3. ALWAYS use parallel_evaluations: 1 in tuning experiment configs

All tuning experiment configs (`config_tuning_treatment.yaml` / `config_tuning_control.yaml`)
**must** set `parallel_evaluations: 1`. Do NOT increase this value.

```yaml
evaluator:
  parallel_evaluations: 1   # REQUIRED for tuning experiments
```

**Why**: With `parallel_evaluations > 1`, multiple worker iterations run concurrently. The
checkpoint polish drain code processes completed iterations without triggering checkpoint
callbacks, causing **missing checkpoints** (e.g., checkpoint_10 skipped entirely). Additionally,
out-of-order iteration completion makes checkpoint triggering unreliable. The tuning pipeline
(rescue selection, checkpoint polish, final polish) was designed assuming sequential iteration
completion.

**Verify before running**: `grep parallel_evaluations examples/<task>/config_tuning_*.yaml`
— both treatment and control must show `1`.

### 4. One variable at a time

Each A/B experiment must isolate exactly **one** independent variable. Control and treatment
configs must be **identical** except for the flag being tested. If testing tuning, both
configs must have `hypothesis_driven: false`. If testing hypothesis, both must have
`tuning.enabled: false` (or omit it entirely).

---

## Experiment Types

### A. Hypothesis A/B

Tests whether hypothesis-driven evolution improves outcomes.

**Config setup** — only `hypothesis_driven` differs:

| Setting | Treatment | Control |
|---------|-----------|---------|
| `hypothesis_driven` | `true` | `false` |
| `tuning.enabled` | `false` (or omit) | `false` (or omit) |

**Task names**: `blis_router`, `function_minimization`, `circle_packing`, etc.

**Config files**: `config_experiment_treatment.yaml` / `config_experiment_control.yaml`

```bash
python scripts/run_experiment.py \
    --task blis_router \
    --condition both \
    --runs 2 \
    --seed-start 300 \
    --iterations 25 \
    --output-dir experiments/hypothesis_ab_blis
```

**Validation checklist** (treatment runs only):
- `hypothesis_tracker.json` exists with `avg_hypotheses_per_iteration > 0`
- `persist_rate > 0.5`, `inject_rate > 0.5`
- `inherit_rate > 0` after ~3 iterations
- Best program contains `HYPOTHESIS-` and `RESULT-` comments
- Grep logs for `[HYPO-TRACK]` to see per-iteration stats

### B. Tuning A/B (v2 — tiered rescue/polish)

Tests whether `@TUNE` threshold tuning improves outcomes.

**How tuning v2 works**: The LLM sees a minimal 4-line prompt about `@TUNE`. It focuses on
algorithms, not parameters. Behind the scenes, Optuna runs in three tiers:
- **Rescue** (5 trials): Novel-but-low-scoring programs get a quick tuning pass
- **Checkpoint polish** (10 trials): Top-K elites polished at each checkpoint
- **Final polish** (20 trials): Thorough tuning of the best programs at the end

The LLM **never** sees `@TUNED` feedback — optimizer results are hidden to prevent
anchoring on parameter thinking. Insensitive `@TUNE` annotations (gain < 0.01) are
automatically stripped.

**Config setup** — only `tuning.enabled` differs:

| Setting | Treatment | Control |
|---------|-----------|---------|
| `hypothesis_driven` | `false` | `false` |
| `tuning.enabled` | `true` | `false` |
| `tuning.rescue_trials` | `5` | — |
| `tuning.checkpoint_trials` | `10` | — |
| `tuning.final_trials` | `20` | — |
| `tuning.polish_top_k` | `3` | — |
| `tuning.max_params` | `3` | — |

**Task names**: `function_minimization_tuning`, `circle_packing_tuning`, `blis_router_tuning`

**Config files**: `config_tuning_treatment.yaml` / `config_tuning_control.yaml`

```bash
python scripts/run_experiment.py \
    --task function_minimization_tuning \
    --condition both \
    --runs 2 \
    --seed-start 300 \
    --iterations 25 \
    --output-dir experiments/tuning_ab_funcmin
```

**Treatment config template** (tuning section):
```yaml
hypothesis_driven: false

tuning:
  enabled: true
  max_params: 3
  rescue_trials: 5         # per-iteration rescue (selective, novel+low-scoring only)
  checkpoint_trials: 10    # polish top-K elites at each checkpoint
  final_trials: 20         # thorough polish at the final iteration
  polish_top_k: 3          # top-K programs per island to polish
```

**Control config template**:
```yaml
hypothesis_driven: false

tuning:
  enabled: false
```

**Validation checklist** (treatment runs only):
- `tuning_tracker.json` exists with `total_iterations_with_tuning > 0`
- Check `rescue_count > 0` — rescue is selecting novel programs to tune
- Check `tune_annotation_rate > 0` — LLM is generating `@TUNE` annotations
- Best programs should **NOT** contain `@TUNED` (stripped before DB storage)
- Best programs may contain `@TUNE` annotations (sensitive ones kept)
- Grep logs for `[TUNE-RESCUE]`, `[TUNE-SKIP]`, `[TUNE-CHECKPOINT]`, `[TUNE-FINAL]`
- Check `rescue_avg_gain` in tracker — positive means rescue is helping
- If `tune_annotation_rate` drops to 0, the LLM stopped generating `@TUNE`

**Language notes**: `@TUNE` annotations work in any language:
- Python: `threshold = 0.5  # @TUNE [0.0, 1.0]`
- Go: `threshold := 0.5 // @TUNE [0.0, 1.0]`
- Rust/C++: `let threshold = 0.5; // @TUNE [0.0, 1.0]`

**Performance note (v2 vs v1)**: v2 uses ~56% fewer evaluations than v1. Rescue tuning
fires on ~32% of iterations (novel+low-scoring only), not all. Polish adds ~180 evaluations
total over a 25-iteration run (vs v1's ~500). For BLIS (~20s/eval), total tuning wall-clock
is ~1.2 hours vs v1's ~2.8 hours.

### C. Combined (Hypothesis + Tuning) A/B

Tests whether hypothesis AND tuning together improve outcomes vs vanilla.

**Config setup** — both flags differ:

| Setting | Treatment | Control |
|---------|-----------|---------|
| `hypothesis_driven` | `true` | `false` |
| `tuning.enabled` | `true` | `false` |

```yaml
# Treatment: both features ON
hypothesis_driven: true
tuning:
  enabled: true
  max_params: 3
  rescue_trials: 5
  checkpoint_trials: 10
  final_trials: 20
  polish_top_k: 3
```

```yaml
# Control: both features OFF
hypothesis_driven: false
tuning:
  enabled: false
```

**Note**: This tests the combined effect. To attribute effects to individual features,
run separate hypothesis-only and tuning-only A/B experiments (or use the factorial runner).

---

## Live Monitoring During Runs (IMPORTANT)

Don't just launch experiments and wait. **Continuously monitor** every run throughout its
entire duration. A broken pipeline or silent regression mid-run wastes hours of compute.
Check logs after every few iterations, not just the first ones.

### How to monitor

While an experiment is running, tail the stderr log in a separate terminal (or use Bash tool):

```bash
# Find the active run directory
ls -lt experiments/<dir>/  # most recent run dir at top

# Tail the live log
tail -f experiments/<dir>/treatment_run_300/experiment_stderr.txt
```

### What to look for — Tuning treatment

Check these **continuously throughout the run** (not just the first few iterations):

| Expected Log Line | What It Means | If Missing |
|-------------------|---------------|------------|
| `[TUNE-RESCUE] iter=N ...` | Rescue tuning fired on a novel program | May be OK if all programs score above median |
| `[TUNE-SKIP] iter=N ...` | Program skipped rescue (good score or low diversity) | Should appear — means selection logic is active |
| `[TUNE-CHECKPOINT] iter=5 ...` | Checkpoint polish ran at first checkpoint | Must appear at checkpoint_interval iterations |
| `tune_annotations=N→M` | LLM generated N @TUNE annotations, M honored | If N=0 for several iterations, LLM isn't using @TUNE |

**Red flags — stop and investigate:**
- Zero `[TUNE-RESCUE]` AND zero `[TUNE-SKIP]` lines → tuning pipeline not running at all
- `tune_annotations=0` for 5+ consecutive iterations → LLM stopped generating @TUNE
- `[TUNING] Baseline evaluation failed` repeatedly → evaluator broken
- Any `ImportError` mentioning optuna → `pip install optuna` needed

### What to look for — Hypothesis treatment

| Expected Log Line | What It Means | If Missing |
|-------------------|---------------|------------|
| `[HYPO-TRACK] iter=N ... hypotheses_in_child_code=M` | M > 0 means hypotheses persisted | If M=0, diff application is stripping them |
| `[HYPO-TRACK] ... results_injected=K` | K > 0 means RESULT verdicts injected | If K=0 after iter 1, inject pipeline broken |
| `[HYPO-TRACK] ... persist_rate=X` | X > 0.5 means hypotheses surviving diffs | X=0 means all hypotheses lost |

### What to look for — Control runs

Control runs should have **none** of the above log lines. If you see `[TUNE-RESCUE]` or
`[HYPO-TRACK]` in a control run, the config is wrong — the feature isn't disabled.

### Validation after each run completes

```bash
# Quick sanity check for tuning treatment
cat experiments/<dir>/treatment_run_*/tuning_tracker.json | python -m json.tool | head -20
# Expect: rescue_count > 0, tune_annotation_rate > 0

# Quick sanity check for hypothesis treatment
cat experiments/<dir>/treatment_run_*/hypothesis_tracker.json | python -m json.tool | head -20
# Expect: avg_hypotheses_per_iteration > 0, persist_rate > 0.5

# Verify control has no tracker files (or tracker shows zeros)
ls experiments/<dir>/control_run_*/tuning_tracker.json  # should not exist
ls experiments/<dir>/control_run_*/hypothesis_tracker.json  # should not exist
```

### When to abort and restart

- **Config mismatch**: Treatment and control configs differ in more than the tested flag
- **Pipeline not active**: 5+ consecutive iterations with zero annotations/hypotheses in treatment
- **Evaluator broken**: Repeated evaluation failures in stderr
- **Stale data**: Output directory had leftover files from a previous run

---

## Prerequisites

```bash
# 1. Install OpenEvolve
pip install -e ".[dev]"

# 2. For BLIS router: verify simulator builds
cd examples/blis_router/inference-sim
go build -o simulation_worker main.go
cd ../../..

# 3. Verify LLM API access
# Configs use: api_base: https://ete-litellm.ai-models.vpc-int.res.ibm.com
# Test connectivity before launching long experiments.
```

## Analyzing Results

```bash
# For hypothesis experiments (default labels: "Hypothesis-Driven" vs "Vanilla OpenEvolve")
python scripts/analyze_experiment.py \
    --data experiments/<experiment_dir>/convergence.csv \
    --output experiments/<experiment_dir>

# For tuning experiments (labels: "Tuning" vs "Control")
python scripts/analyze_experiment.py \
    --data experiments/<experiment_dir>/convergence.csv \
    --output experiments/<experiment_dir> \
    --labels tuning
```

Produces:
- **convergence_curves.png**: Median + IQR bands over iterations
- **final_scores_boxplot.png**: Distribution comparison at final iteration
- **statistics.json**: Mann-Whitney U test (p-value, effect size)

### Interpreting Statistics

- **p < 0.05**: Statistically significant difference
- **rank_biserial > 0**: Treatment outperforms control
- **rank_biserial magnitude**: 0.1 = small, 0.3 = medium, 0.5 = large effect

## File Structure After a Run

```
experiments/tuning_ab_funcmin/
├── convergence.csv                    # Combined convergence data
├── run_results.json                   # Full results with pipeline stats
├── treatment_run_300/
│   ├── checkpoints/checkpoint_*/      # Per-checkpoint snapshots
│   ├── best/best_program.py           # Best evolved program
│   ├── tuning_tracker.json            # Tuning pipeline stats (if tuning enabled)
│   ├── hypothesis_tracker.json        # Hypothesis pipeline stats (if hypo enabled)
│   ├── logs/                          # Full logs
│   ├── experiment_stdout.txt
│   └── experiment_stderr.txt
├── control_run_300/
│   └── ...                            # Same structure, no tracker files
└── convergence_curves.png             # After analyze_experiment.py
```

## Available Tasks

| Task Name | Feature Tested | Evaluator | Language |
|-----------|---------------|-----------|----------|
| `blis_router` | Hypothesis | BLIS Go simulator | Go |
| `function_minimization` | Hypothesis | Python function min | Python |
| `circle_packing` | Hypothesis | Python circle packing | Python |
| `blis_router_tuning` | Tuning | BLIS Go simulator | Go |
| `function_minimization_tuning` | Tuning | Python function min | Python |
| `circle_packing_tuning` | Tuning | Python circle packing | Python |
| `web_scraper_tuning` | Tuning | Python web scraping | Python |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Build failed` in BLIS logs | Check `examples/blis_router/inference-sim` builds manually |
| LLM timeout errors | Increase `llm.timeout` in both configs |
| `[TUNE-RESCUE]` never appears | Check `tuning.enabled: true`; check LLM is generating `@TUNE` annotations |
| `tune_annotation_rate` = 0 | LLM isn't generating `@TUNE`; prompt may need a nudge (rare) |
| `rescue_count` = 0 | All programs score above median — rescue selection is working correctly, just no candidates |
| `@TUNED` in best program | Bug — `strip_tuned_for_db()` should remove it. Check `tuning.py` |
| `persist_rate` = 0 (hypothesis) | Diff application stripping hypotheses; check rescue logic |
| Scores identical treatment/control | Pipeline may not be active; check tracker files exist |
| Parallel run corruption | **Kill all processes**, clean output dir, restart with `--condition both` |
| Missing checkpoints (e.g., checkpoint_10 skipped) | Set `parallel_evaluations: 1` in both configs. With >1, drain skips checkpoint callbacks |

## Document History

- **Canonical doc**: This file (`docs/AB_EXPERIMENT_HOWTO.md`)
- **Superseded**: `docs/plans/hypothesis-ab-experiment-howto.md` (deleted — was hypothesis-only, referenced removed signal_processing task)
- **Related design docs** (historical, not howto):
  - `docs/plans/2026-02-25-hypothesis-ab-experiment-design.md` — Original hypothesis experiment design
  - `docs/plans/2026-02-25-hypothesis-ab-experiment-plan.md` — Original implementation plan
  - `docs/plans/hypothesis-ab-experiment-findings.md` — v1 hypothesis experiment results
  - `docs/plans/2026-03-02-structured-threshold-tuning-design.md` — Tuning v1 design
  - `docs/plans/2026-03-03-structured-threshold-tuning-v2-design.md` — Tuning v2 design (current)
