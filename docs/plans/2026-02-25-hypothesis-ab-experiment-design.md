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
| LLM | Gemini Flash (single model, no ensemble) |
| Iterations | 10 |
| Temperature | 1.0 |
| Seed program | `initial_program.py` (static weighted routing) |
| Workloads | cache_warmup, load_spikes, multiturn |
| Scoring | `score = -0.5 * avg_e2e_ms - 0.5 * avg_p95_ms` |
| Database | 100 population, 3 islands, 15 archive |
| Runs per condition | 5 (different random seeds) |

## Tasks

### Task 1: BLIS Router (Primary)

Evolve Go routing policy for LLM inference load balancing across 3 workloads with conflicting optimal strategies. This is the existing `examples/blis_router/` setup.

### Task 2: Simpler Task (Generality)

Adapt one existing OpenEvolve example (e.g., function minimization) to support hypothesis-driven mode. Demonstrates the approach generalizes beyond BLIS router.

## Metrics

### Primary Metrics (per run)

| Metric | Description | Computation |
|--------|-------------|-------------|
| Best score at iteration N | Convergence curve | Track `best_combined_score` after each of 10 iterations |
| Final best score | Solution quality at budget exhaustion | Best score at iteration 10 |
| AUCC | Area Under Convergence Curve — captures both speed and quality | Sum of best-so-far scores across all 10 iterations |
| Build success rate | Fraction of iterations producing compilable code | `successful_builds / total_iterations` |

### Per-Workload Breakdown

For the best program at iteration 10:
- `cache_warmup_e2e_ms`
- `load_spikes_e2e_ms`
- `multiturn_e2e_ms`
- `avg_e2e_ms`, `avg_p95_ms`

### Statistical Analysis

- **N=5 per condition** — report median ± IQR (interquartile range)
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

1. **Gemini Flash config** — single model (`gemini/gemini-2.0-flash`), no ensemble
2. **Treatment config** — Gemini Flash + `hypothesis_driven: true` (the default)
3. **Control config** — Gemini Flash + `hypothesis_driven: false`, system prompt stripped of hypothesis instructions

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
    treatment_run_1/
    treatment_run_2/
    ...
    control_run_1/
    control_run_2/
    ...
  hypothesis_ab_simple/
    treatment_run_1/
    ...
```

## Execution Order

1. Integrate hypothesis-driven mode into OpenEvolve core (config flag, prompt template, ledger/knowledge base)
2. Create Gemini Flash configs (treatment + control)
3. Adapt simpler task for hypothesis-driven mode
4. Build experiment runner script
5. Run 1 pilot run per condition to validate setup
6. Run full experiment: 5 runs × 2 conditions × 2 tasks = 20 runs
7. Analyze results and generate plots
8. Write paper sections

## Future Extensions

After initial results, consider:
- **Additional models**: Run with Claude Sonnet, Qwen, etc. to show model-agnostic benefit
- **Ablation: hypotheses without feedback**: LLM writes hypotheses but never sees knowledge base — isolates whether structured reasoning alone helps vs. the feedback loop
- **Ablation: free-form reasoning**: Prompt says "explain your reasoning" without structured HYPOTHESIS/MECHANISM/EXPECT format
- **Scale**: Increase to 50-100 iterations to measure asymptotic effects
- **More tasks**: Additional use cases for stronger generality claim
