# Hypothesis A/B Experiment: How to Run

## Overview

This experiment compares **hypothesis-driven evolution** (treatment) against **vanilla OpenEvolve** (control) across 3 tasks. The treatment condition injects structured hypothesis instructions into the LLM prompt and feeds back a knowledge base of confirmed/refuted strategies.

## Prerequisites

```bash
pip install -e ".[dev]"
pip install pandas matplotlib scipy
```

For BLIS router experiments, you also need the Go simulation binary built:
```bash
cd examples/blis_router/inference-sim && go build -o simulation_worker main.go && cd -
```

## Quick Start (Single Task)

### Run both conditions for function_minimization:
```bash
python scripts/run_experiment.py \
  --task function_minimization \
  --condition both \
  --runs 3 \
  --seed-start 100 \
  --output-dir experiments/hypothesis_ab_funcmin
```

### Analyze results:
```bash
python scripts/analyze_experiment.py \
  --data experiments/hypothesis_ab_funcmin/convergence.csv \
  --output experiments/hypothesis_ab_funcmin/plots/ \
  --title " (Function Minimization)"
```

## Full Experiment (All 3 Tasks)

### 1. BLIS Router (Sonnet + Opus ensemble via ete-litellm)
```bash
python scripts/run_experiment.py \
  --task blis_router \
  --condition both \
  --runs 3 \
  --seed-start 100 \
  --output-dir experiments/hypothesis_ab_blis
```

### 2. Function Minimization (Gemini Flash via ete-litellm)
```bash
python scripts/run_experiment.py \
  --task function_minimization \
  --condition both \
  --runs 3 \
  --seed-start 100 \
  --output-dir experiments/hypothesis_ab_funcmin
```

### 3. Signal Processing (Gemini Flash via ete-litellm)
```bash
python scripts/run_experiment.py \
  --task signal_processing \
  --condition both \
  --runs 3 \
  --seed-start 100 \
  --output-dir experiments/hypothesis_ab_signal
```

### 4. Analyze All Three
```bash
python scripts/analyze_experiment.py \
  --data experiments/hypothesis_ab_blis/convergence.csv \
  --output experiments/hypothesis_ab_blis/plots/ \
  --title " (BLIS Router)"

python scripts/analyze_experiment.py \
  --data experiments/hypothesis_ab_funcmin/convergence.csv \
  --output experiments/hypothesis_ab_funcmin/plots/ \
  --title " (Function Minimization)"

python scripts/analyze_experiment.py \
  --data experiments/hypothesis_ab_signal/convergence.csv \
  --output experiments/hypothesis_ab_signal/plots/ \
  --title " (Signal Processing)"
```

## What Each Run Produces

Per task output directory:
```
experiments/hypothesis_ab_<task>/
  treatment_run_100/     # Run with hypothesis_driven=true
  treatment_run_101/
  treatment_run_102/
  control_run_100/       # Run with hypothesis_driven=false
  control_run_101/
  control_run_102/
  convergence.csv        # Combined convergence data
  run_results.json       # Raw run metadata
```

Per analysis output:
```
experiments/hypothesis_ab_<task>/plots/
  convergence_curves.png     # Median + IQR bands
  final_scores_boxplot.png   # Final score distribution
  statistics.json            # Mann-Whitney U test, medians, IQR
```

## Experiment Design

| Parameter | Value |
|-----------|-------|
| Iterations per run | 10 |
| Runs per condition | 3 |
| Conditions | treatment (hypothesis_driven=true), control (false) |
| Tasks | blis_router, function_minimization, signal_processing |
| Total runs | 3 tasks x 2 conditions x 3 runs = 18 |

### Treatment vs Control Differences

| Aspect | Treatment | Control |
|--------|-----------|---------|
| `hypothesis_driven` config | `true` | `false` |
| System prompt | Includes hypothesis instructions | No hypothesis instructions |
| Prompt injection | `HYPOTHESIS_INSTRUCTIONS_TEMPLATE` appended | Nothing appended |
| Evaluator behavior | Parses HYPOTHESIS/EXPECT comments, updates ledger, returns knowledge base artifact | No hypothesis parsing (no comments to parse) |
| LLM models | Identical | Identical |
| Database/evolution settings | Identical | Identical |

### LLM Configs by Task

| Task | Primary Model | Secondary Model | API Base |
|------|--------------|-----------------|----------|
| blis_router | aws/claude-sonnet-4-5 (70%) | aws/claude-opus-4-6 (30%) | ete-litellm |
| function_minimization | GCP/gemini-2.5-flash (80%) | gcp/gemini-3-flash-preview (20%) | ete-litellm |
| signal_processing | GCP/gemini-2.5-flash (80%) | gcp/gemini-3-flash-preview (20%) | ete-litellm |

## Statistical Analysis

The analysis script computes:
- **Median final score** per condition
- **IQR** (interquartile range) for variability
- **Mann-Whitney U test** (one-sided: treatment > control)
- **Rank-biserial correlation** (effect size)

Significance threshold: p < 0.05 (note: with n=3 per group, power is limited).

## Pilot Validation

Before running the full experiment, validate the pipeline:
```bash
# Quick pilot with 1 run per condition
python scripts/run_experiment.py \
  --task function_minimization \
  --condition both \
  --runs 1 \
  --seed-start 42 \
  --output-dir experiments/pilot_test

# Verify analysis works
python scripts/analyze_experiment.py \
  --data experiments/pilot_test/convergence.csv \
  --output experiments/pilot_test/plots/

# Clean up
rm -rf experiments/pilot_test
```

## Branch Info

All experiment code lives on the `hypothesis-experiment` branch (branched from `blis`).
