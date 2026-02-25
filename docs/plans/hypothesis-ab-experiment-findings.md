# Hypothesis A/B Experiment: Findings

**Date:** 2026-02-25
**Branch:** `hypothesis-experiment`
**Design:** 3 tasks x 2 conditions x 3 runs = 18 runs, 10 iterations each

---

## Executive Summary

The hypothesis-driven evolution treatment was successfully injected into the LLM system prompt, but **only Claude (Sonnet/Opus) consistently followed the structured hypothesis format**. Gemini Flash completely ignored the hypothesis instructions across all 6 runs (function_minimization + signal_processing). This makes the experiment primarily a test of **LLM instruction-following compliance** rather than a clean comparison of hypothesis-driven vs vanilla evolution.

---

## 1. Hypothesis Compliance by LLM

| Task | LLM | Treatment Runs with Hypotheses | Control Runs with Hypotheses | Expected |
|------|-----|-------------------------------|------------------------------|----------|
| blis_router | Claude Sonnet/Opus | **3/3 (100%)** | 1/3 (33%)* | 3/3 treatment, 0/3 control |
| function_minimization | Gemini 2.5 Flash | **0/3 (0%)** | 0/3 (0%) | 3/3 treatment, 0/3 control |
| signal_processing | Gemini 2.5 Flash | **0/3 (0%)** | 0/3 (0%) | 3/3 treatment, 0/3 control |

*BLIS control seed=102 produced 3 hypotheses despite `hypothesis_driven=false`. This is because the BLIS config's existing `system_message` already contains hypothesis format examples (HYPOTHESIS REQUIREMENTS section was stripped from control config, but the LLM may have learned the pattern from training or previous context in the evolution loop).

### Hypothesis Detail (BLIS Treatment Runs)

All 3 BLIS treatment runs generated exactly 3 hypotheses each, perfectly following the format:

**Treatment seed=100 (best program):**
- H1: "Dynamically weighting load-balance higher for short inputs and realtime requests reduces cache_warmup and load_spikes latency" (EXPECT: cache_warmup_e2e_ms < 5000)
- H2: "Overload penalty on heavily loaded instances prevents hot-spotting from prefix-affinity concentrating traffic" (EXPECT: load_spikes_e2e_ms < 3000)
- H3: "Preserving high prefix-affinity weight for long-prefix sessions maintains multiturn performance" (EXPECT: multiturn_e2e_ms < 200)

### Key Finding: Gemini Flash Ignores Structured Output Instructions

Gemini 2.5 Flash (via ete-litellm) did not produce any HYPOTHESIS/MECHANISM/EXPECT comments in any of 6 treatment runs. The hypothesis instructions were verified to be present in the system prompt (confirmed via code inspection), but the model simply didn't comply. This is a significant instruction-following gap that renders the function_minimization and signal_processing experiments non-differentiating.

---

## 2. Convergence Results

### 2.1 Function Minimization (Gemini Flash — no hypothesis compliance)

| Condition | Median Final Score | IQR | n |
|-----------|-------------------|-----|---|
| Treatment | **1.499** | 0.004 | 3 |
| Control | 1.487 | 0.006 | 3 |

- Mann-Whitney U = 8.0, **p = 0.10** (not significant at 0.05)
- Effect size: r = 0.78 (large, favoring treatment)
- **Caveat:** Since Gemini didn't generate hypotheses, both conditions ran identically. The treatment "advantage" is likely random variation or a subtle effect of the longer system prompt.

### 2.2 Signal Processing (Gemini Flash — no hypothesis compliance)

| Condition | Median Final Score | IQR | n |
|-----------|-------------------|-----|---|
| Treatment | 0.366 | 0.017 | 3 |
| Control | **0.390** | 0.042 | 3 |

- Mann-Whitney U = 3.0, **p = 0.81** (not significant)
- Effect size: r = -0.33 (small, favoring control)
- **Caveat:** Same as above — no hypothesis compliance, so conditions were effectively identical.

### 2.3 BLIS Router (Claude Sonnet/Opus — full hypothesis compliance)

| Condition | Scores at Checkpoint 5 | n |
|-----------|----------------------|---|
| Treatment | -4025, -3865, -3858 | 3 |
| Control | -3860, -3858, -3858 | 3 |

- Only 1 treatment run reached checkpoint 10 (score: -4025)
- Control runs didn't reach checkpoint 10
- Treatment seed=100 had a worse score (-4025 vs ~-3860), possibly due to the hypothesis comments causing compilation changes or different code paths
- **Insufficient data at final iteration** to compute meaningful statistics
- At checkpoint 5: treatment and control are comparable, with treatment seed=100 being an outlier

---

## 3. Hypothesis Knowledge Base & Ledger

No `hypothesis_ledger.json` files were created during the experiment. The evaluators write ledgers to `examples/<task>/openevolve_output/hypothesis_ledger.json`, but:

1. **For Gemini tasks:** No hypotheses were parsed (0 HYPOTHESIS comments), so the ledger pipeline never triggered
2. **For BLIS router:** The evaluator DID parse hypotheses from Go code, but the hypothesis testing requires baseline metrics to be computed and stored. The ledger writing path may not have been reached in all iterations, or the shared output path across runs caused conflicts.

This means the **knowledge base feedback loop** (a key feature of hypothesis-driven evolution) never activated in this experiment. The treatment was limited to the prompt injection alone.

---

## 4. Infrastructure Validation

The experiment infrastructure worked correctly:

| Component | Status |
|-----------|--------|
| Core hypothesis module (`openevolve/hypothesis.py`) | All 47 tests pass |
| Config flag (`hypothesis_driven`) | Correctly parsed from YAML |
| Prompt injection | Verified: treatment system prompt includes HYPOTHESIS instructions, control does not |
| Experiment runner (`scripts/run_experiment.py`) | All 18 runs completed without errors |
| Convergence data collection | Fixed: reads `best_program_info.json` with nested `metrics` |
| Analysis script | Produces plots and statistics correctly |

---

## 5. Recommendations for Next Experiment

### 5.1 Fix Gemini Compliance

The hypothesis instructions need to be much more prominent for Gemini Flash:
- Move hypothesis format instructions from system message to **user message** (closer to the code)
- Add **few-shot examples** showing evolved code WITH hypothesis comments
- Consider using the `diff_user` template to embed hypothesis requirements directly in the code edit instructions
- Test with Gemini 2.5 Pro or Gemini 3 instead, which may have better instruction-following

### 5.2 Fix Ledger Path

The hypothesis ledger writes to a shared path (`examples/<task>/openevolve_output/`) which:
- Gets overwritten between runs
- Should write to the **run-specific output directory** instead

### 5.3 Increase Runs and Iterations

- 3 runs per condition with 10 iterations is underpowered
- Recommend: 5+ runs, 20+ iterations
- Even at n=3, Mann-Whitney U can only achieve p=0.05 if all treatment scores beat all control scores

### 5.4 BLIS Control Config Leakage

The BLIS control config's system_message still contains evaluation workload descriptions and metric names, which may give the LLM enough context to generate hypothesis-like structures. The control should use a truly minimal prompt.

### 5.5 Separate Prompt Injection from Knowledge Base

The current design conflates two treatments:
1. Prompt injection (telling the LLM to write hypotheses)
2. Knowledge base feedback (feeding back confirmed/refuted strategies)

Since the knowledge base never activated, this experiment only tested (1). A factorial design separating these would be more informative.

---

## 6. Raw Data Location

```
experiments/
  hypothesis_ab_funcmin/     # Function minimization (6 runs)
    convergence.csv
    run_results.json
    plots/
      convergence_curves.png
      final_scores_boxplot.png
      statistics.json
  hypothesis_ab_signal/      # Signal processing (6 runs)
    convergence.csv
    run_results.json
    plots/
      convergence_curves.png
      final_scores_boxplot.png
      statistics.json
  hypothesis_ab_blis/        # BLIS router (6 runs)
    convergence.csv
    run_results.json
    plots/
      convergence_curves.png
      final_scores_boxplot.png
      statistics.json
```
