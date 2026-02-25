> **For Claude:** Use superpowers:executing-plans to implement `docs/plans/2026-02-25-hypothesis-ab-experiment-plan.md`

# Hypothesis-Driven Evolution — A/B Experiment (Simple Plan)

## What We're Proving

The LLM doesn't just write code blindly — it writes predictions ("I think this change will reduce latency by X%"). The system tests those predictions, keeps a scoreboard of what worked/didn't, and shows it back next time. The LLM learns from its own reasoning, not just scores.

**Experiment:** Run OpenEvolve twice — with hypothesis feedback loop vs without — and compare. 3 runs each, 10 iterations, 3 tasks. Plot convergence and run stats.

---

## Branch Strategy

```
main
  └── blis              ← existing results stay here, don't touch
       └── hypothesis-experiment  ← all work happens here
```

---

## What Gets Built (11 tasks)

### Task 0: Branch
- `git checkout blis && git checkout -b hypothesis-experiment`

### Task 1: Core hypothesis module
- Create `openevolve/hypothesis.py` — generic version of `examples/blis_router/hypothesis.py`
- Supports `#`, `//`, `--` comments (Python, Go, SQL)
- `valid_metrics` passed as parameter (not hardcoded)
- Tests: `tests/test_hypothesis.py`

### Task 2: Config flag
- Add `hypothesis_driven: true` (default) to `openevolve/config.py`
- One flag to toggle the whole feature on/off

### Task 3: Prompt injection
- When `hypothesis_driven: true`, append hypothesis instructions to system prompt
- Generic template in `openevolve/prompt/templates.py`
- LLM told: write HYPOTHESIS/MECHANISM/EXPECT comments, reference the knowledge base

### Task 4: Migrate BLIS router
- Delete `examples/blis_router/hypothesis.py` (no duplicates)
- Update `evaluator.py` to import from `openevolve.hypothesis`
- Pass `VALID_METRICS` as parameter — **functionally identical, no behavior change**

### Task 5: BLIS router experiment configs
- **Treatment:** copy existing config, set `max_iterations: 10`, `hypothesis_driven: true`
- **Control:** same but `hypothesis_driven: false`, strip hypothesis instructions from system prompt
- Models: `aws/claude-sonnet-4-5` (70%) + `aws/claude-opus-4-6` (30%) via ete-litellm

### Task 6: Function minimization — add hypothesis support
- Add hypothesis pipeline to `examples/function_minimization/evaluator.py`
- Same pattern: parse hypotheses from code → test → ledger → knowledge base → artifact
- Metrics: `value_score`, `distance_score`, `reliability_score`, `combined_score`
- Treatment + control configs
- Models: `GCP/gemini-2.5-flash` (80%) + `gcp/gemini-3-flash-preview` (20%) via ete-litellm

### Task 6b: Signal processing — add hypothesis support
- Add hypothesis pipeline to `examples/signal_processing/evaluator.py`
- Metrics: `composite_score`, `slope_changes`, `lag_error`, `correlation`, `noise_reduction`, etc.
- Treatment + control configs
- Models: `GCP/gemini-2.5-flash` (80%) + `gcp/gemini-3-flash-preview` (20%) via ete-litellm

### Task 7: Experiment runner
- `scripts/run_experiment.py`
- Takes: task name, condition, number of runs, output dir
- Launches independent OpenEvolve runs, collects convergence CSVs

### Task 8: Analysis script
- `scripts/analyze_experiment.py`
- Convergence curves (median ± IQR bands)
- Box plots of final scores
- Mann-Whitney U test for significance

### Task 9: Pilot validation
- 1 treatment + 1 control run on function_minimization (fastest task)
- Verify hypothesis artifacts are created, CSV collected, plots generated

### Task 10: Run full experiment
- 3 runs × 2 conditions × 3 tasks = **18 total runs**
- Analyze and generate plots

---

## The Three Tasks

| Task | Language | LLM Ensemble | Eval Speed | Why It's Interesting |
|------|----------|-------------|------------|---------------------|
| BLIS Router | Go | Sonnet + Opus | ~60s | Conflicting workloads, no single optimal strategy |
| Function Min | Python | Flash + Flash-3 | ~1s | Known global minimum, clear ground truth |
| Signal Processing | Python | Flash + Flash-3 | ~5-10s | Multi-objective (7 metrics), real DSP tradeoffs |

---

## What We Measure

| Metric | What It Tells Us |
|--------|-----------------|
| Convergence curve | Does hypothesis-driven improve faster? |
| Final best score (iter 10) | Does it find better solutions? |
| AUCC (area under curve) | Single number for efficiency + quality |
| Build success rate | Does hypothesis structure reduce wasted iterations? |

**Stats:** Median ± IQR, Mann-Whitney U test (N=3 per condition)

---

## Key Design Decisions

1. **Each task keeps its own models** — we're not testing "does it work with Gemini Flash", we're testing "does hypothesis feedback help regardless of model"
2. **Treatment vs control differ ONLY by `hypothesis_driven` flag** — everything else is identical (same models, same database, same iterations)
3. **10 iterations** — tight budget makes sample efficiency the critical differentiator
4. **3 runs first** — quick sanity check before scaling up to 5+ runs for paper

---

## Detailed Plan

See `docs/plans/2026-02-25-hypothesis-ab-experiment-plan.md` for full implementation with exact file paths, code, and commands.