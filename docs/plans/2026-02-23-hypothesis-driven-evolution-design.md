# Hypothesis-Driven Evolution for BLIS Router

## Problem

OpenEvolve generates code mutations and evaluates them, but the LLM never commits to *why* a change should work. Without explicit predictions, the LLM cannot learn which reasoning was correct and which was wrong. Failed strategies get re-tried because there is no structured memory of what was attempted.

## Solution

Make the LLM write testable hypotheses alongside code mutations. The evaluator tests each hypothesis against a fixed baseline, accumulates results in a persistent ledger, and feeds a knowledge base summary back via artifacts. The LLM sees confirmed and refuted strategies across all iterations, enabling it to build on what works and avoid what doesn't.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Hypothesis location | Go comments in EVOLVE-BLOCK | Zero OpenEvolve core changes; comments compile fine |
| Reference point | Initial program baseline (cached) | Fixed reference avoids noise from stochastic parent sampling |
| EXPECT format | Per-workload metric + absolute threshold | LLM sees parent metrics in prompt, can set thresholds; per-workload gives causal signal |
| Verdict context | Also reports overall combined_score delta | Pragmatic signal alongside diagnostic signal |
| Ledger grouping | By target metric (7 groups max) | Deterministic, no ambiguity, avoids semantic clustering complexity |
| Ledger summary | Top N confirmed + top N refuted (N configurable) | Lineage-agnostic; works with stochastic parent sampling |
| Scope of changes | evaluator.py + config.yaml system_message only | Zero OpenEvolve core changes |

## Hypothesis Format

The LLM writes structured hypothesis comments inside the EVOLVE-BLOCK:

```go
// EVOLVE-BLOCK-START

// HYPOTHESIS-1: Large-prefix requests benefit from cache affinity boost
// MECHANISM-1: Requests with >400 tokens have more KV cache blocks to reuse,
//   so routing to high-CacheHitRate instances avoids recomputation
// EXPECT-1: prefix_caching_e2e_ms < 235

// HYPOTHESIS-2: Realtime requests need aggressive queue avoidance
// MECHANISM-2: Realtime SLO is latency-sensitive; deep queues add wait time
// EXPECT-2: signal_freshness_e2e_ms < 175

scores := make(map[string]float64, len(snapshots))
// ... scoring logic that implements the above hypotheses ...

// EVOLVE-BLOCK-END
```

Each hypothesis requires all 3 lines:
- `HYPOTHESIS-N`: One-line claim about what will improve and why
- `MECHANISM-N`: Causal explanation of what signal/behavior drives the improvement
- `EXPECT-N`: `<metric_name> < <threshold>` (lower latency = better, so always `<`)

Available metrics for EXPECT:
- `prefix_caching_e2e_ms`, `signal_freshness_e2e_ms`, `multiturn_affinity_e2e_ms`
- `sjf_bimodal_e2e_ms`, `combined_stress_e2e_ms`
- `avg_e2e_ms`, `avg_p95_ms`

## Evaluator Changes

### Baseline Caching

On first evaluation, run the initial program through all 5 workloads and cache results to `baseline_metrics.json`. All subsequent evaluations read from cache.

```python
BASELINE_CACHE = script_dir / "baseline_metrics.json"

def get_baseline_metrics():
    if BASELINE_CACHE.exists():
        return json.loads(BASELINE_CACHE.read_text())
    result = run_all_workloads(initial_program)
    BASELINE_CACHE.write_text(json.dumps(result))
    return result
```

### Hypothesis Parsing

Extract `HYPOTHESIS-N`, `MECHANISM-N`, `EXPECT-N` blocks from Go code using regex. Parse EXPECT into `(metric_name, operator, threshold)`.

### Hypothesis Testing

After running workloads, for each parsed hypothesis:
1. Look up the EXPECT metric in child's actual results
2. Compare actual vs threshold -> `CONFIRMED` or `REFUTED`
3. If the referenced workload failed -> `INCONCLUSIVE`
4. Compute delta vs baseline for context

### Ledger Accumulation

Append results to persistent `hypothesis_ledger.json`:

```json
{
  "baseline": {
    "prefix_caching_e2e_ms": 248.5,
    "signal_freshness_e2e_ms": 188.2,
    "combined_score": -210.0
  },
  "entries": [
    {
      "iteration_timestamp": "2026-02-23T14:30:00",
      "hypothesis": "cache affinity boost for large requests",
      "mechanism": "large prefix = more cache blocks to reuse",
      "metric": "prefix_caching_e2e_ms",
      "threshold": 235,
      "actual": 228.4,
      "baseline_value": 248.5,
      "delta_vs_baseline_pct": -8.1,
      "verdict": "CONFIRMED",
      "overall_combined_score": -205.3
    }
  ]
}
```

### Artifact Return

Return two new artifact keys:

1. `hypothesis_results` - This iteration's hypothesis verdicts:
```
HYPOTHESIS-1: "cache affinity boost for large requests"
  EXPECT: prefix_caching_e2e_ms < 235
  ACTUAL: prefix_caching_e2e_ms = 228.4
  VERDICT: CONFIRMED (-8.1% vs baseline of 248.5)

HYPOTHESIS-2: "aggressive queue penalty for realtime"
  EXPECT: signal_freshness_e2e_ms < 175
  ACTUAL: signal_freshness_e2e_ms = 193.7
  VERDICT: REFUTED (+2.9% vs baseline of 188.2)

OVERALL: combined_score = -205.3 (baseline = -210.0, delta = +2.2%)
```

2. `hypothesis_knowledge_base` - Aggregated ledger summary grouped by target metric:
```
HYPOTHESIS KNOWLEDGE BASE:

CONFIRMED STRATEGIES (build on these):
  prefix_caching_e2e_ms:
    - 4/6 confirmed, avg improvement -7.2%
    - Best achieved: 221ms (baseline: 248ms)
  multiturn_affinity_e2e_ms:
    - 2/2 confirmed, avg improvement -4.8%

REFUTED STRATEGIES (avoid these):
  signal_freshness_e2e_ms:
    - 1/5 confirmed, avg regression +2.1%
    - Repeated queue-penalty approaches don't help

INCONCLUSIVE:
  sjf_bimodal_e2e_ms:
    - 1/1 confirmed, needs more trials
```

Top N confirmed and top N refuted are shown (N configurable, default 5).

## Evaluation Flow

```
evaluate(program_path)
  +-- extract Go code (existing)
  +-- get_or_compute_baseline()              <- NEW
  +-- parse_hypotheses(go_code)              <- NEW
  +-- write routing.go + build (existing)
  +-- run 5 workloads (existing)
  +-- test_hypotheses(parsed, actuals, baseline)  <- NEW
  +-- update_ledger(hypothesis_results)      <- NEW
  +-- compute score (existing)
  +-- return EvaluationResult(
        metrics={...},                       (existing)
        artifacts={
          workload_results: {...},           (existing)
          hypothesis_results: "...",         <- NEW
          hypothesis_knowledge_base: "...",  <- NEW
        }
      )
```

## System Prompt Additions

Add to `config.yaml` system_message:

```
HYPOTHESIS REQUIREMENTS:
You MUST include at least 1 hypothesis (max 3) as Go comments in the EVOLVE-BLOCK.

Format (each hypothesis needs all 3 lines):
  // HYPOTHESIS-N: <one-line claim about what will improve and why>
  // MECHANISM-N: <causal explanation - what signal/behavior drives the improvement>
  // EXPECT-N: <metric_name> < <threshold>

Available metrics for EXPECT:
  prefix_caching_e2e_ms, signal_freshness_e2e_ms, multiturn_affinity_e2e_ms,
  sjf_bimodal_e2e_ms, combined_stress_e2e_ms, avg_e2e_ms, avg_p95_ms

Rules:
  - EXPECT must use < operator (lower latency = better)
  - Set thresholds based on the baseline values shown in the HYPOTHESIS KNOWLEDGE BASE artifact
  - Be specific: "helps latency" is too vague,
    "reduces prefix_caching_e2e_ms by targeting cache-warm instances" is good
  - If a strategy was REFUTED in the knowledge base, explain why your new approach differs
  - Build on CONFIRMED strategies; combine proven techniques
```

## Files Changed

| File | Change | Approx Size |
|------|--------|-------------|
| `evaluator.py` | Add hypothesis parsing, baseline caching, testing, ledger logic | ~120 lines |
| `config.yaml` | Expand system_message with hypothesis instructions | ~30 lines |
| `baseline_metrics.json` | Auto-generated on first eval run | N/A |
| `hypothesis_ledger.json` | Auto-generated, grows across iterations | N/A |

Zero changes to OpenEvolve core. Everything lives in `examples/blis_router/`.

## Data Flow

```
LLM generates code with HYPOTHESIS/MECHANISM/EXPECT comments
  -> evaluator parses hypotheses from Go code
  -> runs 5 workloads (existing pipeline)
  -> compares actuals vs EXPECT thresholds + baseline
  -> appends entries to hypothesis_ledger.json
  -> generates knowledge base summary (top N confirmed/refuted by metric)
  -> returns artifacts: {hypothesis_results, hypothesis_knowledge_base}
  -> OpenEvolve stores artifacts in database (existing artifact pipeline)
  -> next iteration: LLM sees knowledge base in prompt (existing artifact rendering)
  -> LLM writes new hypotheses informed by accumulated knowledge
```
