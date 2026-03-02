# A/B Experiment: Hypothesis-Driven Evolution

How to run A/B experiments comparing hypothesis-driven evolution (treatment) vs vanilla OpenEvolve (control) for the BLIS router use case.

## What the Experiment Tests

**Hypothesis pipeline**: When `hypothesis_driven: true`, the LLM is prompted to write
structured `HYPOTHESIS-N / MECHANISM-N / EXPECT-N` comments in evolved code. After evaluation,
`RESULT-N: CONFIRMED/REFUTED` comments are automatically injected. In subsequent iterations,
the LLM sees these verdicts in parent and top programs, enabling structured learning.

**Control**: `hypothesis_driven: false` — vanilla evolution with no hypothesis instructions.

**Both conditions** share identical domain prompts, LLM models, temperature, population settings,
and evaluation. The **only difference** is the `hypothesis_driven` flag.

## Prerequisites

```bash
# 1. Install OpenEvolve
pip install -e ".[dev]"

# 2. Verify BLIS simulator builds
cd examples/blis_router/inference-sim
go build -o simulation_worker main.go
cd ../../..

# 3. Verify LLM API access
# The configs use: api_base: https://ete-litellm.ai-models.vpc-int.res.ibm.com
# Models: aws/claude-sonnet-4-5 (primary), aws/claude-opus-4-6 (secondary)
# Test with a quick curl or litellm call to confirm connectivity.
```

## Config Files

| File | Purpose |
|------|---------|
| `examples/blis_router/config_experiment_treatment.yaml` | Treatment: `hypothesis_driven: true` |
| `examples/blis_router/config_experiment_control.yaml` | Control: `hypothesis_driven: false` |

These configs are **identical** except for the `hypothesis_driven` flag (line 20).
Domain knowledge, LLM settings, population size, evaluation — all the same.

## Running a Pilot (Quick Validation)

Run 1 treatment + 1 control with few iterations to verify the pipeline works:

```bash
python scripts/run_experiment.py \
    --task blis_router \
    --condition both \
    --runs 1 \
    --seed-start 42 \
    --iterations 5 \
    --output-dir experiments/pilot_$(date +%Y%m%d_%H%M)
```

### What to Check After a Pilot

1. **Both runs completed** — check `run_results.json` for `"status": "ok"`

2. **Hypothesis pipeline is working** (treatment only):
   ```bash
   # Check the hypothesis tracker
   cat experiments/pilot_*/treatment_run_42/db/hypothesis_tracker.json | python -m json.tool
   ```
   Verify these rates are healthy:
   - `avg_hypotheses_per_iteration` > 0 (LLM is generating hypotheses)
   - `persist_rate` > 0.5 (hypotheses survive into code after diff application)
   - `inject_rate` > 0.5 (RESULT comments are being injected)
   - `inherit_rate` > 0 after iteration ~3+ (parent programs have hypotheses)

3. **Scores are being recorded** — check convergence data:
   ```bash
   cat experiments/pilot_*/convergence.csv
   ```

4. **Logs for hypothesis tracking** — grep for `[HYPO-TRACK]`:
   ```bash
   grep "HYPO-TRACK" experiments/pilot_*/treatment_run_42/logs/*.log
   ```
   Each iteration logs: `generated=N persisted=N results_injected=N parent_hypos=N top_w_hypos=N/M`

5. **Best program has hypotheses** (treatment):
   ```bash
   grep -c "HYPOTHESIS-" experiments/pilot_*/treatment_run_42/best/best_program.py
   grep -c "RESULT-" experiments/pilot_*/treatment_run_42/best/best_program.py
   ```

## Running a Full A/B Experiment

Standard A/B: 3+ runs per condition with different seeds:

```bash
python scripts/run_experiment.py \
    --task blis_router \
    --condition both \
    --runs 5 \
    --seed-start 100 \
    --iterations 50 \
    --output-dir experiments/ab_$(date +%Y%m%d_%H%M)
```

For parallel execution (if you have enough resources):
```bash
python scripts/run_experiment.py \
    --task blis_router \
    --condition both \
    --runs 5 \
    --seed-start 100 \
    --iterations 50 \
    --output-dir experiments/ab_$(date +%Y%m%d_%H%M) \
    --parallel
```

**Time estimate**: Each run = ~1-2 hours for 50 iterations. Sequential = 10-20 hours for 5+5 runs.

## Analyzing Results

```bash
python scripts/analyze_experiment.py \
    --data experiments/ab_*/convergence.csv \
    --output experiments/ab_*/plots
```

This produces:
- **Convergence plot**: Median + IQR bands for treatment vs control over iterations
- **Final score boxplot**: Distribution comparison at final iteration
- **statistics.json**: Mann-Whitney U test (p-value, rank-biserial effect size)

### Interpreting Statistics

- **p < 0.05**: Statistically significant difference
- **rank_biserial > 0**: Treatment outperforms control (positive = better)
- **rank_biserial magnitude**: 0.1 = small, 0.3 = medium, 0.5 = large effect

## Hypothesis Pipeline Validation Checklist

For **treatment runs**, verify these pipeline stages:

| Stage | What to Check | Where |
|-------|--------------|-------|
| **Generation** | LLM writes HYPOTHESIS/EXPECT comments | `hypothesis_tracker.json` → `total_hypotheses_generated` |
| **Persistence** | Hypotheses survive diff application + rescue | `hypothesis_tracker.json` → `persist_rate` |
| **Injection** | RESULT-N comments added after evaluation | `hypothesis_tracker.json` → `inject_rate` |
| **Inheritance** | Parent programs carry hypotheses into next iter | `hypothesis_tracker.json` → `inherit_rate` |
| **Learning** | Best programs have hypothesis+result comments | Check best_program.py for HYPOTHESIS/RESULT lines |

**Red flags** (indicates pipeline is broken):
- `avg_hypotheses_per_iteration` = 0 → LLM is ignoring hypothesis instructions
- `persist_rate` = 0 → Diff application is stripping hypotheses and rescue is failing
- `inject_rate` = 0 → RESULT injection is failing (metrics mismatch?)
- `inherit_rate` stays 0 after 5+ iterations → Hypotheses not propagating through population

## Customizing the Experiment

### Changing Models

Edit both config files identically:
```yaml
llm:
  primary_model: aws/claude-sonnet-4-6    # or any model from the available list
  secondary_model: aws/claude-opus-4-6
  api_base: https://ete-litellm.ai-models.vpc-int.res.ibm.com
```

### Changing Iteration Count

Either edit `max_iterations` in both configs, or use `--iterations` flag (overrides config).

### Running Only One Condition

```bash
# Treatment only
python scripts/run_experiment.py --task blis_router --condition treatment --runs 3 ...

# Control only
python scripts/run_experiment.py --task blis_router --condition control --runs 3 ...
```

## File Structure After a Run

```
experiments/ab_20260227_1430/
├── convergence.csv                    # Combined convergence data
├── run_results.json                   # Full results with hypothesis stats
├── treatment_run_100/
│   ├── checkpoints/checkpoint_*/      # Per-checkpoint snapshots
│   ├── best/best_program.py           # Best evolved program
│   ├── db/hypothesis_tracker.json     # Hypothesis pipeline stats
│   ├── logs/                          # Full logs (grep for HYPO-TRACK)
│   ├── experiment_stdout.txt          # Captured stdout
│   └── experiment_stderr.txt          # Captured stderr
├── treatment_run_101/
│   └── ...
├── control_run_100/
│   └── ...                            # Same structure, no hypothesis_tracker
└── plots/                             # After running analyze_experiment.py
    ├── convergence.png
    ├── final_scores.png
    └── statistics.json
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Build failed` in logs | Check `examples/blis_router/inference-sim` builds manually |
| LLM timeout errors | Increase `llm.timeout` in both configs |
| All workloads fail | Check BLIS sim binary exists and workload YAMLs are present |
| `persist_rate` = 0 | LLM may be writing hypotheses outside SEARCH/REPLACE blocks; rescue should handle this but check logs for "Rescued" messages |
| `inherit_rate` stays 0 | Population may be too small or hypotheses are only in low-scoring programs that never get sampled as parents |
