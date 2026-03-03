# A/B Experiment Guide

How to run A/B experiments for OpenEvolve features. Three independent features can be A/B tested:

| Feature | Config Flag | What It Does |
|---------|------------|--------------|
| **Hypothesis** | `hypothesis_driven: true/false` | LLM writes structured HYPOTHESIS/EXPECT comments; RESULT verdicts auto-injected |
| **Tuning** | `tuning.enabled: true/false` | LLM annotates params with `@TUNE`; Optuna optimizes within declared ranges |
| **Combined** | Both flags | Hypothesis + Tuning together |

---

## CRITICAL: Execution Rules

### 1. ALWAYS run experiments sequentially — NEVER in parallel

```bash
# CORRECT: single process, --condition both runs treatment then control sequentially
python scripts/run_experiment.py --task <task> --condition both --runs 2 ...

# WRONG: two parallel processes — causes data corruption
python scripts/run_experiment.py --task <task> --condition treatment ... &
python scripts/run_experiment.py --task <task> --condition control ... &
```

**Why**: Some evaluators (especially BLIS router) write to shared files (e.g., `routing.go`).
Parallel runs will clobber each other, producing corrupt results. Even for evaluators that
don't share files (funcmin, circpack), parallel `run_experiment.py` processes write to the
same output directory and can race on `convergence.csv` / `run_results.json`.

### 2. ALWAYS start from a clean state

Before running experiments, remove any previous run data in the output directory:

```bash
rm -rf experiments/tuning_ab_funcmin   # remove old data
# then run fresh
python scripts/run_experiment.py --task function_minimization_tuning ...
```

**Why**: Leftover checkpoint directories, tracker files, or stale `convergence.csv` from
previous runs can contaminate results or cause the experiment runner to skip/overwrite runs.

### 3. One variable at a time

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

### B. Tuning A/B

Tests whether `@TUNE` threshold tuning improves outcomes.

**Config setup** — only `tuning.enabled` differs:

| Setting | Treatment | Control |
|---------|-----------|---------|
| `hypothesis_driven` | `false` | `false` |
| `tuning.enabled` | `true` | `false` |
| `tuning.budget` | `10` | — |
| `tuning.max_params` | `3` | — |
| `tuning.budget_scale_per_param` | `3` | — |

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
  budget: 10           # base Optuna trials
  max_params: 3        # max @TUNE annotations honored
  budget_scale_per_param: 3  # extra trials per param (total = budget + params * scale)
```

**Control config template**:
```yaml
hypothesis_driven: false

tuning:
  enabled: false
```

**Validation checklist** (treatment runs only):
- `tuning_tracker.json` exists with `total_iterations_with_tuning > 0`
- Programs contain `@TUNE` annotations (grep for `@TUNE` in checkpoint programs)
- Best programs contain `@TUNED(...)` feedback annotations
- Grep logs for `[TUNING]` and `[TUNE-TRACK]` to see per-iteration stats
- Check `avg_gain_when_tuned` in tracker — positive means tuning is helping

**Language notes**: `@TUNE` annotations work in any language:
- Python: `threshold = 0.5  # @TUNE [0.0, 1.0]`
- Go: `threshold := 0.5 // @TUNE [0.0, 1.0]`
- Rust/C++: `let threshold = 0.5; // @TUNE [0.0, 1.0]`

**Performance note**: Tuning adds ~19 evaluations per iteration (budget + params * scale).
For expensive evaluators (BLIS, circle_packing), this significantly increases iteration time.
For cheap evaluators (funcmin), overhead is minimal (~1s per iteration).

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
  budget: 10
  max_params: 3
  budget_scale_per_param: 3
```

```yaml
# Control: both features OFF
hypothesis_driven: false
tuning:
  enabled: false
```

**Note**: This tests the combined effect. To attribute effects to individual features,
run separate hypothesis-only and tuning-only A/B experiments.

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
python scripts/analyze_experiment.py \
    --data experiments/<experiment_dir>/convergence.csv \
    --output experiments/<experiment_dir>
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

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Build failed` in BLIS logs | Check `examples/blis_router/inference-sim` builds manually |
| LLM timeout errors | Increase `llm.timeout` in both configs |
| `[TUNING]` never appears in logs | Check `tuning.enabled: true` in config; verify `process_parallel.py` passes `tuning_enabled` to `build_prompt` |
| `@TUNE` count = 0 in tracker | LLM isn't generating annotations; check prompt template is injected (look for `[TUNING] Appended` in stderr) |
| `persist_rate` = 0 (hypothesis) | Diff application stripping hypotheses; check rescue logic |
| Scores identical treatment/control | Pipeline may not be active; check tracker files exist |
| Parallel run corruption | **Kill all processes**, clean output dir, restart with `--condition both` |
