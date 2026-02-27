# ADR: Why BLIS Router Evolution Gains Are Limited and How to Fix It

## Status: Proposed

## Context

The OpenEvolve experiment evolves a Go routing policy for an LLM inference simulator
(BLIS). After 20 iterations with Claude Sonnet 4.5 (70%) + Opus 4.6 (30%), the best
discovered algorithm achieves ~15.5% improvement on combined score but **regresses on 2
of 3 workloads**:

| Workload       | Baseline (ms) | Evolved (ms) | Delta   | Oracle (ms) | Oracle Delta (mean) | Oracle Delta (p95) |
|----------------|---------------|--------------|---------|-------------|--------------------|--------------------|
| cache_warmup   | 5734.57       | 4285.26      | **-25.3%** | 4103.88  | **-28.4%**         | **-18.1%**         |
| load_spikes    | 3285.44       | 3367.90      | **+2.5%**  | 3237.17  | **-1.5%**          | **+1.9%** (regress)|
| multiturn      | 160.77        | 163.45       | **+1.7%**  | 160.89   | **+0.08%** (flat)  | **-1.5%**          |
| **combined_score** | -4564.48  | -3856.68     | **+15.5%** | ~-3988   | ~+12.6%            |                    |

**Critical finding**: The oracle doesn't improve all workloads either. It regresses on
load_spikes p95 (+1.9%) and is flat on multiturn mean (+0.08%). This means the
workloads have **genuinely conflicting optima** — no single adaptive strategy can
improve all three simultaneously with the current workload parameters.

---

## Root Cause Analysis

### RC-1: Extreme Latency-Scale Disparity Makes 2 of 3 Workloads Irrelevant to Score

The scoring function averages latencies equally across workloads:

```
avg_e2e = (cache_warmup + load_spikes + multiturn) / 3
score   = -0.5 * avg_e2e - 0.5 * avg_p95
```

But the latency magnitudes differ by 35x:

| Workload     | Baseline Mean | % of avg_e2e | Effective Weight in Score |
|--------------|---------------|-------------|--------------------------|
| cache_warmup | 5734 ms       | 62.5%       | **Dominates**            |
| load_spikes  | 3285 ms       | 35.8%       | Secondary                |
| multiturn    | 161 ms        | 1.7%        | **Irrelevant**           |

A 25% improvement on cache_warmup saves ~1450ms. A 2.5% regression on load_spikes
costs only ~82ms. A 1.7% regression on multiturn costs ~3ms. The net gain is ~1365ms,
which the score happily accepts. The LLM quickly learns that cache_warmup dominance
means it can ignore multiturn entirely and tolerate load_spikes regressions.

**Impact**: Evolution is incentivized to be a single-workload optimizer.

### RC-2: load_spikes AND multiturn Are Both Near-Optimal — the Oracle Can't Win Either

**load_spikes**:
- Baseline (1:1 weights): mean=3285ms, p95=7186ms
- Load-only: mean=3358ms (+2.2%), p95=6938ms (-3.4%)
- Oracle: mean=3237ms (-1.5%), **p95=7323ms (+1.9% REGRESSION)**

The 1:1 weight combination provides enough load-balance signal to counteract
prefix-affinity pile-on. The oracle improves mean by 48ms but regresses p95. The
workload sits at an equilibrium where static weights are hard to beat.

**multiturn**:
- Baseline (1:1 weights): mean=160.77ms, p95=457.93ms
- Prefix-only: mean=160.77ms (**0.00%**), p95=457.93ms (**0.00%**)
- Load-only: mean=169.61ms (+5.5%), p95=488.13ms (+6.6%)
- Oracle: mean=160.89ms (+0.08% — flat), p95=451.06ms (-1.5%)

**Baseline = prefix-only exactly** for multiturn. The long prefixes (1024-4096 tokens)
create such large score gaps that prefix-affinity completely dominates the 1:1
combination — load-balance has zero practical influence. Sessions already stick to their
instance perfectly. At only 150 req/s across 4 instances (~37 req/s each), there's
almost no queueing, so routing quality barely matters beyond "did the session stay?"

**Root pattern**: 2 of 3 workloads are already optimally served by the baseline, each
for a different reason:
- load_spikes: load-balance already counteracts prefix pile-on
- multiturn: prefix-affinity already provides perfect session stickiness

**Impact**: This is a workload design problem. Evolution can only discover what exists.
Only cache_warmup has meaningful room for improvement, so that's all it optimizes.

### RC-3: The Evolved Algorithm's Input-Length Threshold Is Tuned for the Wrong Workload

The evolved code uses a 64-256 token gradient for prefix weight suppression. But
`len(req.InputTokens)` includes the prefix, so:

- cache_warmup traffic: 228-1312 tokens → most gets partial/full prefix suppression (helps!)
- load_spikes heavy-hitter: ~612-1312 tokens → gets **full prefix weight** (doesn't help!)
- multiturn sessions: 1044-4296 tokens → gets full prefix weight (correct)

The threshold was tuned by optimizing cache_warmup (where it works) without
consideration for load_spikes (where a higher threshold is needed). The LLM never
explored thresholds in the 800-1200 range that would also catch load_spikes
heavy-hitter traffic.

**Impact**: The LLM found a locally-optimal threshold for the dominant scoring signal
but missed the globally-correct threshold.

### RC-4: The LLM Only Explored Weight Scaling, Not Score Recomposition

Every evolved program uses the same pattern: multiply existing scorer weights by
adaptive factors. The prompt hints at blending (`scores[id] = original*alpha + newSignal*(1-alpha)`)
but this was never attempted across 20 iterations. Weight scaling can shift preference
but cannot override prefix-affinity when it produces large score gaps between instances
(cached=0.8 vs uncached=0.1). Even with `prefixWeight=0.1`, the gap persists
proportionally and pulls traffic to the cached instance.

**Impact**: The LLM is stuck in a suboptimal region of the search space where the
structural approach (weight scaling) has a performance ceiling below the oracle.

### RC-5: Overload Penalties Are Reactive — Too Late for High-Rate Bursty Workloads

The hypothesis ledger shows load_spikes EXPECT was **refuted in every single iteration**
(0/10 success rate across all attempts). The LLM tried: threshold 2, threshold 4,
cubic, quadratic, QueueDepth-specific, variance-based, mean-based — none worked.

At 1000 req/s, queue depths change faster than the penalty can react. Post-hoc
penalties on current load cannot prevent pile-on that has already happened. The
pattern fundamentally doesn't match the problem.

**Impact**: The LLM exhausted the reactive-penalty design space without success.

### RC-6: Hypothesis System Creates Conservative Convergence

After 5 iterations, the knowledge base reinforces:
- "Short-input downweighting CONFIRMED" → keeps reusing
- "Overload penalty REFUTED" → makes incremental variations instead of radical changes

Best program found at **iteration 5 of 20**. Iterations 6-20 produced no improvement.
The LLM never tried: removing the overload penalty, switching to score recomposition,
or raising the input-length threshold above 256.

**Impact**: Early confirmation locks the strategy; the system cannot escape.

### RC-7: Only 20 Iterations Is Insufficient

With 3 islands and 20 iterations, each island gets ~7 programs. The population never
becomes diverse enough to escape local optima.

---

## Recommendations

### Category A: Scoring Function (must fix)

#### R-1: Normalize Per-Workload Scores

**Problem**: Raw latency averaging lets cache_warmup dominate.

**Fix**: Score each workload as percentage improvement over baseline, then combine:

```python
improvements = []
for workload_name, latency in workload_latencies:
    baseline = baseline_metrics[f"{workload_name}_e2e_ms"]
    improvement_pct = (baseline - latency) / baseline  # positive = better
    improvements.append(improvement_pct)

score = mean(improvements)  # Each workload contributes equally
```

**Variant**: Geometric mean of ratios `(baseline / evolved)` penalizes regressions more
harshly than it rewards improvements — good for encouraging Pareto dominance.

#### R-2: Add Per-Workload Regression Penalty

**Problem**: No penalty for regressing on individual workloads.

**Fix**: Any workload regression beyond 1% tolerance incurs a score penalty:

```python
REGRESSION_PENALTY = 0.10  # 10% penalty per regressed workload (in normalized score)
TOLERANCE = 0.01

for workload_name, latency in workload_latencies:
    baseline_lat = baseline_metrics[f"{workload_name}_e2e_ms"]
    if latency > baseline_lat * (1 + TOLERANCE):
        score -= REGRESSION_PENALTY
```

Forces Pareto improvements rather than single-workload exploits.

### Category B: Workload Design (must fix for load_spikes)

#### R-3: Redesign load_spikes So an Adaptive Router Can Actually Win

**Problem**: Baseline is within 1.5% of oracle on mean, and oracle regresses p95. The
workload's equilibrium is too favorable to the static 1:1 weighting.

**Diagnosis**: With 50% heavy-hitter at 4 instances, the load-balance scorer provides
enough counterforce. We need to tip the balance so static weights fail more.

**Options** (pick one or combine):

a. **Increase heavy-hitter to 60-65%**: Makes prefix-affinity dominate more in the
   static 1:1 combination, creating a larger gap for adaptive routing to close.

b. **Increase burstiness (CV=5 instead of 3)**: More extreme bursts create transient
   overloads that static weights can't handle but adaptive logic can anticipate.

c. **Add a second heavy prefix group (20% each)**: Two concentrated groups create
   more complex routing decisions where request-aware adaptation outperforms static
   weights.

d. **Increase request rate to 1500-2000**: Higher load amplifies the cost of
   suboptimal routing, widening the gap between good and mediocre strategies.

**Validation required**: After adjustment, re-run the oracle to confirm it now
achieves 5-10% improvement on load_spikes (both mean and p95) so there's a meaningful
gap for evolution to target.

#### R-4: Redesign multiturn So Prefix-Affinity Doesn't Automatically Win

**Problem**: Baseline = prefix-only on this workload (identical numbers). At 150 req/s
with 4 instances, there's no queueing tension — prefix-affinity dominates completely
and sessions stick perfectly. An adaptive router has nothing to improve.

**Diagnosis**: Two factors make the baseline unbeatable:
1. **No queueing**: 37 req/s per instance creates no load imbalance to exploit
2. **No competing traffic**: 80% of traffic is long-prefix sessions that all benefit
   from the same strategy (stick to instance)

**Options** (combine for best effect):

a. **Increase rate to 400-600 req/s**: Creates real queueing, so session-stickiness
   competes with load-balance. When a popular session type concentrates on one instance,
   an adaptive router should shed non-session traffic to keep queues manageable.

b. **Increase single-turn/realtime traffic to 35-40%** (from 20%): More traffic that
   doesn't benefit from affinity means the router must actively balance two goals:
   keep sessions sticky AND keep non-session traffic load-balanced. Static 1:1 weights
   can't optimize both.

c. **Add short-prefix sessions** (e.g., prefix=128, 2 rounds): Sessions where the
   cache-miss cost is low (~2ms), so bouncing them is cheap. A smart router should
   bounce these to preserve capacity for expensive sessions (4096-token prefix).
   Static weights can't distinguish cheap vs expensive sessions.

d. **Add bursty session arrivals** (gamma CV=3 for one session type): Bursty sessions
   create transient hotspots that static routing can't adapt to.

**Recommended**: (a) + (b). Increase rate to 500 and realtime to 35%. This creates
genuine tension between session-stickiness and load-balance that only an adaptive
router can navigate.

**Validation required**: Re-run oracle after changes. Target: oracle achieves 3-8%
improvement on multiturn mean vs baseline, confirming room for evolution.

### Category C: Prompt Improvements (high-level directions only)

#### R-5: Add Direction on When Weight Adjustment Is Insufficient

**Problem**: The LLM only tried weight scaling. It never explored recomposing scores
from scratch for certain traffic classes.

**Fix**: Add a strategy direction (no code, no specific thresholds):

```
6. **When weight adjustment isn't enough**:
   Adjusting the weight on prefix-affinity shifts how much it matters, but can't
   eliminate its influence entirely. When prefix-affinity is actively HARMFUL
   (concentrating traffic on one instance), consider whether you need to
   recompute scores from different signals entirely for that class of traffic,
   rather than just reducing the weight. Think about: what makes prefix-affinity
   harmful? It's not input length per se — it's when many requests share the
   SAME prefix and pile onto one instance.
```

#### R-6: Clarify That InputTokens Includes Prefix

**Problem**: The LLM set thresholds at 64-256 tokens, likely not realizing that a
request with prefix_length=512 + body=400 has `len(req.InputTokens)` = 912.

**Fix**: Add factual clarification (not a solution hint):

```
IMPORTANT: len(req.InputTokens) is the TOTAL input length including any shared
prefix tokens. A request in a prefix group with prefix_length=512 and a body
of 400 tokens has len(req.InputTokens) ≈ 912.
```

This is pure API documentation, not strategy guidance.

#### R-7: Add Explicit Multi-Workload Objective

**Problem**: The LLM sees only combined score and optimizes the easiest workload.

**Fix**:

```
OBJECTIVE: Improve latency across ALL workloads. A solution that improves one
workload but regresses another is penalized. Think about what makes each
workload different and what routing strategy each one needs — then find the
signal that lets your code adapt per-request.
```

#### R-8: Add Direction on Score Concentration Detection

**Problem**: The LLM tried reactive overload penalties. It never considered detecting
that prefix-affinity is creating a concentration problem.

**Fix**:

```
7. **Detecting when prefix-affinity creates concentration**:
   After the scorer loop runs, look at the score distribution across instances.
   If one instance scores much higher than all others on prefix-affinity,
   that means this prefix group is concentrated — many requests will pile onto
   that instance. The wider the gap between the top-scoring instance and the
   rest, the higher the concentration risk. Think about how to use this signal.
```

### Category D: Evolution Parameters

#### R-9: Increase to 50-100 Iterations

20 iterations is insufficient. Best found at iteration 5 means the search barely
started. 50-100 iterations with 3 islands gives 17-33 programs per island.

#### R-10: Break Convergence Loops

**Options**:

a. **Stale strategy marking**: After 5 iterations without score improvement, add a
   prompt injection:
   ```
   NOTE: The best score has not improved in N iterations. The current approach
   may be a local optimum. Consider trying a fundamentally different strategy
   rather than refining the current one.
   ```

b. **Reduce exploitation ratio**: After convergence, shift from 65/35 to 50/50
   exploit/explore to encourage more radical departures.

c. **Periodic island reset**: Every 15 iterations, clear one island to force fresh
   exploration.

---

## Priority Matrix

| # | Recommendation | Category | Impact | Effort | Priority |
|---|----------------|----------|--------|--------|----------|
| R-1 | Normalize per-workload scores | Scoring | High | Low | **P0** |
| R-2 | Per-workload regression penalty | Scoring | High | Low | **P0** |
| R-3 | Redesign load_spikes workload | Workload | **Critical** | Medium | **P0** |
| R-4 | Redesign multiturn workload | Workload | **Critical** | Medium | **P0** |
| R-5 | Direction: weight adj. insufficiency | Prompt | High | Low | **P0** |
| R-6 | Clarify InputTokens includes prefix | Prompt | High | Low | **P0** |
| R-7 | Multi-workload objective in prompt | Prompt | Medium | Low | **P1** |
| R-8 | Direction: concentration detection | Prompt | Medium | Low | **P1** |
| R-9 | Increase to 50-100 iterations | Evolution | Medium | Low | **P1** |
| R-10 | Break convergence loops | Evolution | Medium | Medium | **P2** |

### What Changed vs. V1 of This ADR

- **R-3 AND R-4 elevated to P0**: The oracle can't win on load_spikes (regresses p95
  +1.9%) or multiturn (flat on mean, +0.08%). 2 of 3 workloads are already optimal
  for the static baseline — one because load-balance already counteracts pile-on,
  the other because prefix-affinity already provides perfect session stickiness at
  low rate. Both must be redesigned so an adaptive router has room to win.

- **Old R-4 (show oracle code) removed**: Giving the solution away. Replaced with
  high-level directional guidance (R-5, R-8).

- **Old R-5 narrowed**: Only the factual API clarification (InputTokens includes
  prefix) is kept. The per-workload token ranges were removed — that's close to
  telling the LLM where thresholds should be.

---

## Expected Outcome

**After workload + scoring fixes (R-1, R-2, R-3, R-4)**:
- All 3 workloads have meaningful room for adaptive routing to improve (target: 3-10%
  oracle-vs-baseline gap on each)
- Evolution is forced to improve all workloads equally (not just cache_warmup)
- Normalized scoring eliminates the cache_warmup dominance exploit

**After prompt fixes (R-5, R-6, R-7, R-8)**:
- LLM explores score recomposition (not just weight scaling)
- LLM reasons correctly about input token lengths
- LLM considers concentration risk, not just reactive overload
- No specific thresholds, code patterns, or solution hints given

**After evolution parameter fixes (R-9, R-10)**:
- More iterations to escape local optima
- Convergence detection prevents wasted iterations

**Target**: 20-30% combined improvement with no per-workload regression exceeding 1%.

## Decision

Mean-only scoring (no p95 in score). See Implementation Plan below.

---

## Implementation Plan

### Step 1: Adjust `workload_v2_load_spikes.yaml`

**Problem**: At 50% heavy-hitter with CV=3, baseline's 1:1 weights already counteract
pile-on. Oracle wins by only 1.5% on mean, regresses p95.

**Changes**:
- `heavy-prefix-batch.rate_fraction`: 0.50 → **0.60**
- `heavy-prefix-batch.arrival.cv`: 3.0 → **4.0**
- `realtime-critical.rate_fraction`: 0.25 → **0.20**
- `light-prefix-interactive.rate_fraction`: 0.25 → **0.20**
- Update header comments (validated results TBD after validation)

**Why**: 60% heavy-hitter creates 2.4x overload on one instance (vs 2.0x at 50%). CV=4
creates sharper burst peaks. The static 1:1 load-balance signal is no longer sufficient.

### Step 2: Adjust `workload_v2_multiturn.yaml`

**Problem**: At 150 req/s, no queueing. Prefix-affinity perfectly handles sessions.
Baseline = prefix-only (identical to 0.00%).

**Changes**:
- `aggregate_rate`: 150.0 → **400.0**
- `num_requests`: 1500 → **4000** (maintains 10s simulation)
- `heavy-coding-sessions.rate_fraction`: 0.40 → **0.30**
- `chat-sessions.rate_fraction`: 0.25 → **0.20**
- `qa-sessions.rate_fraction`: 0.15 → **0.15** (keep)
- `realtime-api.rate_fraction`: 0.20 → **0.35**
- Update header comments (validated results TBD)

**Why**: At 400 req/s, each instance handles ~100 req/s. 35% realtime (140 req/s) creates
load that competes with 65% session traffic. An adaptive router that routes realtime to
less-loaded instances while keeping sessions sticky will beat static 1:1 weights.

### Step 3: New oracle

#### 3a: `test_workloads/oracle_program.py`

Replace EVOLVE-BLOCK with three-signal classification:

```
Signal 1: req.SessionID != "" AND inputLen > 800
  → Multi-turn session with valuable prefix
  → Keep prefix-affinity + tiered overload protection (load>20: 0.5x, load>10: 0.8x)

Signal 2: inputLen < 1000 (and not Signal 1)
  → Short input, prefix-affinity causes pile-on
  → Recompute scores: 85% load-balance, 15% prefix as tiebreaker

Signal 3: else (long non-session)
  → Preserve prefix-affinity + mild overload check (load>15: 0.7x)

Plus: SLO-aware realtime penalty (QueueDepth > 5 → 0.6x)
```

**Why this wins all 3 workloads:**
- cache_warmup: all inputs < 1000, no sessions → Signal 2 → avoids prefix imbalance
- load_spikes: heavy-hitter ~900 tokens, no session → Signal 2 → avoids 60% pile-on
- multiturn: sessions 1044-4296 tokens + SessionID → Signal 1 → session stickiness;
  realtime ~50 tokens → Signal 2 → routed by load-balance

**Risk**: `req.SessionID` may not be set by simulator. Fallback: remove SessionID check,
use inputLen > 800 alone (all multi-turn sessions have inputLen > 1000).

#### 3b: `test_workloads/validate_workloads.py`

Replace `ORACLE_EVOLVE_BLOCK` (lines 106-163) with same Go code as 3a, `\t`-indented.

### Step 4: Normalize scoring in `evaluator.py`

#### 4a: New scoring formula (replaces lines ~539-554)

```python
# Per-workload mean improvement (each workload contributes equally)
mean_improvements = []
regression_count = 0
REGRESSION_TOLERANCE = 0.01  # 1%
REGRESSION_PENALTY = 10.0

for workload_name, workload_file in WORKLOADS:
    result = workload_results.get(workload_name)
    if result is None or result.get("e2e_ms") is None:
        continue
    actual_mean = result["e2e_ms"]
    baseline_mean = baseline_metrics.get(f"{workload_name}_e2e_ms")
    if baseline_mean and baseline_mean > 0:
        imp = (baseline_mean - actual_mean) / baseline_mean * 100.0
        mean_improvements.append(imp)
        if actual_mean > baseline_mean * (1 + REGRESSION_TOLERANCE):
            regression_count += 1

score = (sum(mean_improvements) / len(mean_improvements)) if mean_improvements else -100.0
score -= regression_count * REGRESSION_PENALTY

# Keep raw averages for backward compat / logging
avg_latency = sum(latencies) / len(latencies)
avg_tail_latency = sum(tail_latencies) / len(tail_latencies)
```

**Score interpretation**: positive = better than baseline (% improvement). 0 = same.
Each workload contributes equally. Any workload regressing >1% → -10 points.

#### 4b: Baseline combined_score

In `get_or_compute_baseline()`: `baseline["combined_score"] = 0.0`

#### 4c: Add `avg_mean_improvement_pct` and `regression_count` to returned metrics dict.

#### 4d: Update summary logging to show improvement percentages.

### Step 5: Update prompt in `config.yaml`

All in `system_message` section. **High-level directions only.**

#### 5a: EVALUATION line (line 202)

```
EVALUATION: Score = average improvement percentage across all 3 workloads (mean latency).
Each workload is normalized: improvement_pct = (baseline - actual) / baseline * 100.
Positive score = better than baseline. Regressing any workload by >1% incurs a penalty.
```

#### 5b: New strategy direction 6 (after existing direction 5)

```
6. **When weight adjustment isn't enough**:
   Adjusting the weight on prefix-affinity shifts how much it matters, but can't
   eliminate its influence entirely. When prefix-affinity is actively HARMFUL
   (concentrating traffic on one instance), consider whether you need to
   recompute scores from different signals entirely for that class of traffic,
   rather than just reducing the weight.
```

#### 5c: New strategy direction 7

```
7. **Detecting when prefix-affinity creates concentration**:
   After the scorer loop runs, look at the score distribution across instances.
   If one instance scores much higher than all others on prefix-affinity,
   that means this prefix group is concentrated — many requests will pile onto
   that instance. The wider the gap between the top-scoring instance and the
   rest, the higher the concentration risk.
```

#### 5d: InputTokens clarification (after `len(req.InputTokens)` bullet)

```
NOTE: len(req.InputTokens) is the TOTAL input length including any shared prefix
tokens. A request in a prefix group with prefix_length=512 and a body of 400
tokens has len(req.InputTokens) approximately equal to 912.
```

#### 5e: Multi-workload objective (after ANTI-PATTERNS)

```
MULTI-WORKLOAD OBJECTIVE:
Your code is evaluated on ALL 3 workloads simultaneously. Each workload contributes
equally to the score. Improving one workload while regressing another is penalized.
Find the signal that lets your code adapt per-request to serve all workloads well.
```

#### 5f: Update workload descriptions to match new parameters

- load_spikes: "60% of traffic (very bursty, CV=4)", "20%+20%"
- multiturn: "rate=400, 4000 reqs", "65% session traffic", "35% single-turn realtime"

### Step 6: Validate

1. Delete stale baseline: `rm examples/blis_router/openevolve_output/baseline_metrics.json`
2. Run: `cd examples/blis_router/test_workloads && python validate_workloads.py`
3. **Success criteria**:
   - Oracle beats baseline on ALL 3 workloads (mean), target 3-10% each
   - Sabotaged is >>baseline on all workloads
   - load-only and prefix-only show expected tradeoffs
4. If oracle doesn't win all 3: iterate on workload parameters

### Files Modified

| File | Change |
|------|--------|
| `examples/blis_router/workload_v2_load_spikes.yaml` | 60% heavy-hitter, CV=4, rebalance |
| `examples/blis_router/workload_v2_multiturn.yaml` | rate=400, 35% realtime, rebalance sessions |
| `examples/blis_router/test_workloads/oracle_program.py` | Three-signal oracle |
| `examples/blis_router/test_workloads/validate_workloads.py` | Update ORACLE_EVOLVE_BLOCK |
| `examples/blis_router/evaluator.py` | Normalized mean-only scoring + regression penalty |
| `examples/blis_router/config.yaml` | Prompt: 2 new directions, InputTokens note, multi-workload objective, updated descriptions, new EVALUATION line |
