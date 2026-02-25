# Hypothesis-Driven Evolution: A/B Experiment Design

**Date:** 2026-02-25
**Goal:** Scientifically demonstrate that hypothesis-driven evolution outperforms vanilla OpenEvolve in both sample efficiency and solution quality, particularly under tight iteration budgets.

## Paper Claim

Hypothesis-driven evolution — where the LLM writes structured, testable predictions alongside code mutations and receives accumulated results as feedback — achieves better solutions faster than standard evolutionary code generation. With only 10 iterations, the feedback loop prevents wasted exploration and lets the LLM build on confirmed strategies.

## Experimental Conditions

### Condition 1: Control (Vanilla OpenEvolve)

- Standard OpenEvolve with `hypothesis_driven: false`
- LLM sees: current code, combined_score, per-workload metrics, evolution history, top/diverse programs
- No hypothesis prompting in system message
- Evaluator returns only scores and metrics — no knowledge base artifact

### Condition 2: Treatment (Hypothesis-Driven, Default)

- Full hypothesis pipeline with `hypothesis_driven: true` (the default)
- LLM writes HYPOTHESIS/MECHANISM/EXPECT comments in evolved code
- Evaluator parses hypotheses, tests against cached baseline, accumulates in persistent ledger
- Knowledge base summary (confirmed/refuted strategies) fed back as artifact each iteration
- System prompt includes hypothesis rules, workload hints, and instructions to reference knowledge base

### Shared Parameters

| Parameter | Value |
|-----------|-------|
| Iterations | 10 |
| Runs per condition | 3 (different random seeds) |
| API endpoint | `https://ete-litellm.ai-models.vpc-int.res.ibm.com` (all models) |

Each task uses **its own LLM ensemble** to test hypothesis-driven evolution in realistic settings.

## Tasks

### Task 1: BLIS Router (Primary)

Evolve Go routing policy for LLM inference load balancing across 3 workloads with conflicting optimal strategies.

| Parameter | Value |
|-----------|-------|
| LLM | `aws/claude-sonnet-4-5` (70%) + `aws/claude-opus-4-6` (30%) |
| Temperature | 1.0 |
| Scoring | `score = -0.5 * avg_e2e_ms - 0.5 * avg_p95_ms` |
| Database | 100 population, 3 islands, 15 archive |

### Task 2: Function Minimization

Evolve Python optimization algorithm to find global minimum of a complex multi-modal function.

| Parameter | Value |
|-----------|-------|
| LLM | `GCP/gemini-2.5-flash` (80%) + `gcp/gemini-3-flash-preview` (20%) |
| Temperature | 0.7 |
| Scoring | `combined_score = (0.5*value + 0.3*distance + 0.2*reliability) * quality_multiplier` |
| Database | 50 population, 3 islands, 20 archive |

### Task 3: Signal Processing

Evolve Python adaptive filtering algorithm for non-stationary time series. Multi-objective optimization (slope changes, lag error, tracking accuracy, false reversals).

| Parameter | Value |
|-----------|-------|
| LLM | `GCP/gemini-2.5-flash` (80%) + `gcp/gemini-3-flash-preview` (20%) |
| Temperature | 0.6 |
| Scoring | `composite_score = 0.3*S + 0.2*L_recent + 0.2*L_avg + 0.3*R` (multi-objective) |
| Database | 80 population, 4 islands, 30 archive |

## Metrics

### Primary Metrics (per run)

| Metric | Description | Computation |
|--------|-------------|-------------|
| Best score at iteration N | Convergence curve | Track `best_combined_score` after each of 10 iterations |
| Final best score | Solution quality at budget exhaustion | Best score at iteration 10 |
| AUCC | Area Under Convergence Curve — captures both speed and quality | Sum of best-so-far scores across all 10 iterations |
| Build success rate | Fraction of iterations producing compilable code | `successful_builds / total_iterations` |

### Per-Task Metric Breakdown

For the best program at iteration 10:
- **BLIS Router:** `cache_warmup_e2e_ms`, `load_spikes_e2e_ms`, `multiturn_e2e_ms`, `avg_e2e_ms`, `avg_p95_ms`
- **Function Minimization:** `value_score`, `distance_score`, `reliability_score`
- **Signal Processing:** `slope_changes`, `lag_error`, `correlation`, `noise_reduction`, `composite_score`

### Statistical Analysis

- **N=3 per condition** — report median ± IQR (interquartile range)
- **Mann-Whitney U test** for comparing conditions (non-parametric, appropriate for small N)
- **Effect size**: report rank-biserial correlation coefficient

### Qualitative Analysis (Treatment Only)

- Sample 2-3 hypothesis ledgers from treatment runs
- Show knowledge base evolution over 10 iterations
- Highlight cases where LLM explicitly built on confirmed hypotheses or avoided refuted ones
- Demonstrates interpretability as a secondary benefit

## Plots

1. **Convergence curves** — median best-so-far ± IQR shaded bands, control vs. treatment, one subplot per task
2. **Box plots** — final best scores at iteration 10, per condition, per task
3. **Per-workload latency** — grouped bar chart of best program's per-workload latencies

## Infrastructure

### Core Integration

Move hypothesis support into OpenEvolve core as a configurable default:

- `hypothesis_driven: true/false` config flag (default: `true`)
- Generic hypothesis prompt template injected into system message when enabled
- Core handles: ledger persistence, knowledge base generation from evaluator-reported hypothesis results
- Evaluators opt-in by returning `hypothesis_results` in their metrics dict

### Configs Needed

Per task, two configs that are identical except for the hypothesis flag:
1. **Treatment config** — existing LLM ensemble + `hypothesis_driven: true`, hypothesis instructions in system prompt
2. **Control config** — existing LLM ensemble + `hypothesis_driven: false`, system prompt stripped of hypothesis instructions

### Experiment Runner

`scripts/run_experiment.py`:
- Takes: condition name, number of runs, seed range, config path
- Launches independent OpenEvolve runs with isolated output directories
- Collects convergence data (best score per iteration) into CSV
- Handles failures gracefully (log and continue)

### Analysis

`scripts/analyze_experiment.ipynb`:
- Reads experiment CSVs
- Computes summary statistics (median, IQR, Mann-Whitney U)
- Generates publication-quality plots

### Directory Structure

```
experiments/
  hypothesis_ab_blis/
    treatment_run_1/ ... treatment_run_5/
    control_run_1/   ... control_run_5/
  hypothesis_ab_funcmin/
    treatment_run_1/ ... treatment_run_5/
    control_run_1/   ... control_run_5/
  hypothesis_ab_signal/
    treatment_run_1/ ... treatment_run_5/
    control_run_1/   ... control_run_5/
```

## Execution Order

1. Integrate hypothesis-driven mode into OpenEvolve core (config flag, prompt template, ledger/knowledge base)
2. Create Gemini Flash configs (treatment + control)
3. Adapt simpler task for hypothesis-driven mode
4. Build experiment runner script
5. Run 1 pilot run per condition to validate setup
6. Run full experiment: 3 runs × 2 conditions × 3 tasks = 18 runs
7. Analyze results and generate plots
8. Write paper sections

## Future Extensions

After initial results, consider:
- **Single-model runs**: Re-run all tasks with a single shared model (e.g., Gemini Flash) to control for model effects
- **Ablation: hypotheses without feedback**: LLM writes hypotheses but never sees knowledge base — isolates whether structured reasoning alone helps vs. the feedback loop
- **Ablation: free-form reasoning**: Prompt says "explain your reasoning" without structured HYPOTHESIS/MECHANISM/EXPECT format
- **Scale**: Increase to 50-100 iterations to measure asymptotic effects
- **More tasks**: Additional use cases for stronger generality claim
