# Research Document

## Problem Statement

**Discover an adaptive routing algorithm for multi-instance LLM inference clusters that surpasses static weighted scoring by exploiting workload-aware adaptation and novel decision structures.**

**Context:** BLIS (Blackbox Inference Simulator) models LLM serving with configurable routing policies. The current best-performing policy (WeightedScoring) combines prefix-affinity, queue-depth, and kv-utilization scorers with fixed weights. However:

- **CacheHitRate is used only indirectly** (via prefix-affinity scorer internals) - the main scoring loop does not expose it for direct optimization
- **Weights are static** regardless of workload characteristics
- **No temporal reasoning** (e.g., burst detection, trend analysis using `state.Clock`)
- **No request-aware routing** (e.g., routing large-input requests differently than small ones)

**Goal:** Use OpenEvolve to discover routing algorithms that achieve 10-20% latency reduction over the llm-d default (`prefix-affinity:3, queue-depth:2, kv-utilization:2`) across diverse workloads.

---

## KEY CONSTRAINTS

### Single EVOLVE-BLOCK Requirement
- **Only ONE contiguous EVOLVE-BLOCK is supported** per file
- OpenEvolve's LLM prompts assume a single block; all examples use one block
- Choose block boundaries carefully to include all code that should evolve together

### Joint Iteration Requirement
- **Each research idea iteration must address ALL THREE questions jointly:**
  1. Q1: EVOLVE-BLOCK placement (where in routing.go)
  2. Q2: System prompt design (what guidance for the LLM)
  3. Q3: Workload design (what scenarios to test)
- The three questions are interdependent - optimal block placement depends on prompt guidance, and workloads must stress-test enabled capabilities
- Do NOT address one question per iteration; propose a coherent solution across all three dimensions

---

## Background

### Codebase Context

#### BLIS Routing Architecture

The routing system is in `examples/blis_router/inference-sim/sim/routing.go` (279 lines). Key components:

1. **RoutingSnapshot struct** (lines 10-18): Per-instance state view
   - Fresh signals: `QueueDepth`, `BatchSize`, `PendingRequests`
   - Stale signals (at high rate): `KVUtilization`, `FreeKVBlocks`
   - **Unused in main loop**: `CacheHitRate`

2. **WeightedScoring struct** (lines 114-118): The policy to evolve
   - `scorers []scorerFunc` - scoring functions
   - `weights []float64` - normalized weights
   - `observers []observerFunc` - post-routing state updates

3. **WeightedScoring.Route()** (lines 121-165): Main routing method
   - Scorer invocation loop (lines 129-142)
   - Argmax selection (lines 144-153)
   - Observer notification (lines 155-158)

#### Current EVOLVE-BLOCK Location

In `examples/blis_router/initial_program.py`, the EVOLVE-BLOCK spans lines 137-165 of the Go code:

```go
// EVOLVE-BLOCK-START
// Compute composite scores from all scorers
scores := make(map[string]float64, len(snapshots))
for i, scorer := range ws.scorers {
    dimScores := scorer(req, snapshots)
    for _, snap := range snapshots {
        s := dimScores[snap.ID]
        // Clamp to [0,1] per INV-1
        if s < 0 { s = 0 }
        if s > 1 { s = 1 }
        scores[snap.ID] += s * ws.weights[i]
    }
}

// Argmax: select instance with highest composite score.
// Ties broken by first occurrence in snapshot order (strict >).
bestScore := -1.0
bestIdx := 0
for i, snap := range snapshots {
    if scores[snap.ID] > bestScore {
        bestScore = scores[snap.ID]
        bestIdx = i
    }
}
// EVOLVE-BLOCK-END
```

**Current scope:** Only the scoring loop and argmax selection. Does NOT include:
- Pre-scoring logic (request classification, adaptive weight computation)
- Post-scoring adjustments (tie-breaking based on other signals)
- Observer notifications
- Return statement construction

#### Available Signals for Routing

**Request fields (`req *Request`):**
- `req.InputTokens` - full token sequence (can compute length, hash)
- `req.OutputTokens` - expected output length
- `req.Priority` - request priority value
- `req.SLOClass` - service level objective class (realtime, interactive, batch)
- `req.TenantID` - tenant identifier

**Per-instance snapshot (`snap RoutingSnapshot`):**
- `snap.ID` - instance identifier
- `snap.QueueDepth` - requests waiting (fresh signal)
- `snap.BatchSize` - requests processing (fresh signal)
- `snap.PendingRequests` - routed but not queued (fresh signal)
- `snap.KVUtilization` - cache usage [0.0-1.0] (stale at high rate)
- `snap.FreeKVBlocks` - available blocks (stale at high rate)
- `snap.CacheHitRate` - **UNUSED in main scoring loop**
- `snap.EffectiveLoad()` - QueueDepth + BatchSize + PendingRequests

**Cluster state (`state *RouterState`):**
- `state.Snapshots` - all instance snapshots
- `state.Clock` - simulation time in microseconds (enables temporal reasoning)

---

### Hypothesis Findings Summary

#### H3: Signal Freshness (queue-depth vs kv-utilization)

**Status:** Confirmed | **Key Finding:** At high request rates (5000 req/s), queue-depth distributes 200x more evenly than kv-utilization.

| Scorer | TTFT Mean | TTFT P99 | Distribution StdDev |
|--------|-----------|----------|---------------------|
| queue-depth | 1290-1319ms | 2532-2604ms | 0.7-1.0 |
| kv-utilization | 2259-3644ms | 7870-12285ms | 142-226 |

**Root Cause:** DES event ordering causes KV utilization to be stale at high rates. Queue-depth uses `PendingRequests` which updates synchronously at routing time.

**Implications:**
- Always include queue-depth in weighted routing
- Never use kv-utilization as sole scorer at high rates
- At high rates, kv-utilization returns same value for all instances (constant offset, no effect on argmax)

#### H9: Prefix Caching Effectiveness

**Status:** Confirmed | **Key Finding:** 95.8% TTFT reduction at maximum prefix length.

| Prefix Length | TTFT Mean (ms) | Cache Hit Rate | TTFT Delta vs Baseline |
|---------------|----------------|----------------|------------------------|
| 0 | 728.3 | 0.0000 | baseline |
| 64 | 571.5 | 0.0754 | -21.5% |
| 128 | 429.2 | 0.1511 | -41.1% |
| 256 | 184.6 | 0.3032 | -74.7% |
| 512 | 30.2 | 0.6071 | -95.8% |

**Implications:**
- Workloads with shared system prompts benefit massively from prefix caching
- Cache hit rate is predictable: ~prefix_length / total_input
- Use prefix-affinity routing at cluster scale

#### Prefix-Affinity vs Queue-Depth Tradeoffs

**Status:** Confirmed | **Key Finding:** Prefix-affinity is 2.45x better than queue-depth for multi-turn chat (28.2ms vs 69.0ms TTFT).

| Configuration | TTFT Mean | Cache Hit Rate |
|--------------|-----------|----------------|
| prefix-affinity:3,qd:2 | 28.2ms | 55.7% |
| queue-depth:1 | 69.0ms | 23.3% |
| round-robin | 21.8ms | 62.9% |

**Root Cause:** Queue-depth actively destroys cache locality by routing sessions away from their cached instance (load balancing vs cache affinity tradeoff).

**High Load Crossover (rate=5000):**

| Configuration | TTFT Mean | TTFT P99 | Cache Hit |
|--------------|-----------|----------|-----------|
| prefix-affinity:3,qd:2 | 205.2ms | 489.6ms | 57.6% |
| queue-depth:1 | 892.0ms | 2345.6ms | 21.9% |
| round-robin | 225.4ms | 607.9ms | 54.9% |

**Implications:**
- Multi-turn chat should always use prefix-affinity
- Queue-depth alone is harmful for session-based workloads
- At high load (>2000 req/s), prefix-affinity with queue-depth balancing (pa:3,qd:2) is optimal
- **Concentration vs distribution tradeoff:** More concentration = better cache reuse but more queuing; optimal weight depends on load level

---

### OpenEvolve Constraints Summary

- **Single file input:** Only `initial_program.py` (containing routing.go) can be evolved
- **SINGLE EVOLVE-BLOCK only:** Choose boundaries carefully
- **LLM sees full file** but only modifies marked regions
- **Each iteration must produce valid Go** that compiles and runs
- **Code from other files** (routing_scorers.go, routing_prefix_scorer.go) cannot be directly evolved unless copied into initial_program.py

### Evaluation Constraints

- **4 workloads** run per iteration: burst_steady, context_growth, multi_tenant_chat, prefix_pressure
- **Score formula:** `-0.5 * avg_e2e_ms - 0.5 * avg_p95_ms` (lower latency = higher score)
- **Build failures** result in score of -100000
- **Timeout:** 120 seconds per workload

---

## Research Ideas

---

# Idea 1: Request-Aware Adaptive Scoring with Load-Sensitive Weight Modulation

## Q1: EVOLVE-BLOCK Placement

**Recommended boundaries:** Expand block to include pre-scoring logic and post-selection tie-breaking. Lines 137-165 in the Go code section of initial_program.py (current block), but **expanded upward** to allow variable declarations before the scoring loop.

**Rationale:** The current block is too narrow. It only permits modifications to the scoring aggregation and argmax selection. To enable request-aware routing (using `req.InputTokens`, `req.SLOClass`) and load-adaptive weight computation (using `state.Clock` and aggregate load), we need space for:
1. Pre-scoring request classification (input size, SLO class)
2. Adaptive weight computation based on cluster load
3. Post-scoring adjustments (e.g., CacheHitRate-based tie-breaking)

**Code to include:**
```go
// EVOLVE-BLOCK-START
// === PRE-SCORING: Request classification and adaptive weight computation ===
// Classify request by input size and SLO requirements
inputLen := len(req.InputTokens)
isLargeRequest := inputLen > 500
isRealtimeSLO := req.SLOClass == "realtime"

// Compute aggregate cluster load for adaptive weight modulation
totalLoad := 0
for _, snap := range snapshots {
    totalLoad += snap.EffectiveLoad()
}
avgLoad := float64(totalLoad) / float64(len(snapshots))
isHighLoad := avgLoad > 10.0

// Adaptive weight multipliers based on load and request characteristics
prefixAffinityBoost := 1.0
queueDepthBoost := 1.0
if isHighLoad {
    // Under high load, prioritize load balancing over cache affinity
    queueDepthBoost = 1.5
    prefixAffinityBoost = 0.8
}
if isLargeRequest {
    // Large requests benefit more from cache hits
    prefixAffinityBoost *= 1.3
}

// === SCORING LOOP ===
scores := make(map[string]float64, len(snapshots))
for i, scorer := range ws.scorers {
    dimScores := scorer(req, snapshots)
    // Apply adaptive weight modulation
    weight := ws.weights[i]
    // (Evolution can discover which scorers to boost)
    for _, snap := range snapshots {
        s := dimScores[snap.ID]
        if s < 0 { s = 0 }
        if s > 1 { s = 1 }
        scores[snap.ID] += s * weight
    }
}

// === POST-SCORING: Tie-breaking and adjustments ===
// Incorporate CacheHitRate as a tie-breaker (currently unused signal)
for _, snap := range snapshots {
    // Small bonus for instances with good cache hit rates
    scores[snap.ID] += snap.CacheHitRate * 0.05
}

// Argmax selection with SLO-aware tie-breaking
bestScore := -1.0
bestIdx := 0
for i, snap := range snapshots {
    if scores[snap.ID] > bestScore {
        bestScore = scores[snap.ID]
        bestIdx = i
    } else if scores[snap.ID] == bestScore && isRealtimeSLO {
        // For realtime SLO, prefer lower queue depth on ties
        if snap.QueueDepth < snapshots[bestIdx].QueueDepth {
            bestIdx = i
        }
    }
}
// EVOLVE-BLOCK-END
```

## Q2: System Prompt

**Prompt text:**
```
You are evolving a routing algorithm for an LLM inference cluster. The goal is to minimize end-to-end latency across diverse workloads.

CONTEXT:
- The router selects which instance handles each request
- Current approach: weighted scoring of prefix-affinity (cache reuse), queue-depth (load balancing), and kv-utilization
- Key tradeoff: cache affinity (route to same instance) vs load balancing (spread requests evenly)

AVAILABLE SIGNALS (use these creatively):
- Request: req.InputTokens (length indicates cost), req.SLOClass (realtime/interactive/batch), req.TenantID
- Per-instance: snap.QueueDepth (fresh), snap.BatchSize (fresh), snap.PendingRequests (fresh), snap.KVUtilization (stale at high rates), snap.CacheHitRate (UNDERUTILIZED), snap.EffectiveLoad()
- Cluster: state.Clock (microseconds, enables temporal reasoning), len(snapshots) instances

PROVEN INSIGHTS:
1. Queue-depth is reliable at high rates; kv-utilization becomes stale and uniform
2. Prefix-affinity gives 2-3x better cache hit rates for multi-turn conversations
3. At high load, more load balancing is needed; at low load, more cache affinity helps
4. Large input requests (>500 tokens) benefit disproportionately from cache hits

EVOLUTION GOALS:
1. Adapt weights dynamically based on observed cluster load
2. Use request characteristics (input size, SLO class) to inform routing
3. Exploit CacheHitRate directly (currently unused in scoring)
4. Consider temporal patterns (burst detection via state.Clock)

CONSTRAINTS:
- Must produce valid Go code
- Must preserve the scores map and bestIdx output variable
- All scorer scores are in [0,1] range; weights are normalized
```

**Key guidance points:**
- Explains the cache-affinity vs load-balancing tradeoff explicitly
- Lists all available signals with freshness annotations
- Provides concrete insights from prior experiments (H3, H9)
- Suggests specific strategies (adaptive weights, request classification, CacheHitRate usage)
- Clear constraints to prevent broken code

## Q3: Workload Design

**Workload suite:** 4 workloads targeting different routing challenges

| Workload | Rate | Requests | Key Challenge |
|----------|------|----------|---------------|
| burst_steady | 250 req/s | 6000 | **Burst handling**: CV=5.0 gamma arrivals create storms that overwhelm naive load balancing; realtime SLO requests must be protected |
| context_growth | 150 req/s | 3000 | **Cache pressure**: Multi-turn sessions (up to 8 rounds) with accumulating context; tests whether router maintains cache affinity over time |
| multi_tenant_chat | 200 req/s | 5000 | **Multi-prefix routing**: 5 prefix groups competing for 4 instances; tests whether router can map prefix groups to instances intelligently |
| prefix_pressure | 400 req/s | 8000 | **High load + prefix competition**: 8 prefix groups on 4 instances at high rate; forces explicit cache-vs-load tradeoff decisions |

**Rationale:**
- **burst_steady** tests adaptive weight modulation (need more queue-depth weight during bursts)
- **context_growth** tests cache affinity preservation (large requests with repeated prefixes)
- **multi_tenant_chat** tests multi-prefix routing (router must learn prefix-to-instance mapping)
- **prefix_pressure** is the stress test combining high load with prefix competition

## How Q1+Q2+Q3 Work Together

1. **Block scope (Q1)** enables request classification (input size, SLO class) and adaptive weight computation by including pre-scoring logic. It also enables CacheHitRate usage in post-scoring adjustments.

2. **System prompt (Q2)** guides the LLM toward the specific adaptations enabled by the block scope: load-aware weight modulation, request-aware routing, and CacheHitRate exploitation. The prompt explains WHY these strategies matter (based on H3/H9 findings).

3. **Workloads (Q3)** create selection pressure for these capabilities:
   - burst_steady rewards burst detection and queue-depth boosting
   - context_growth rewards cache affinity for large multi-turn requests
   - prefix_pressure rewards intelligent prefix-to-instance mapping

The three components form a coherent system: the block enables the capabilities, the prompt guides discovery toward them, and the workloads reward algorithms that exploit them.

### Review: Idea 1

#### Review by claude-opus-4-6

**Strengths:**
1. Good identification of the core tradeoff (cache affinity vs load balancing)
2. Comprehensive use of available signals including the underutilized CacheHitRate
3. Clear connection between block scope, prompt guidance, and workload design
4. Pre-scoring request classification enables SLO-aware routing

**Concerns:**
1. **Block scope may be too prescriptive**: The expanded block code provides a complete implementation. This leaves little room for the LLM to discover novel structures - it will likely just tune the constants (1.5, 0.8, 1.3, 0.05, etc.)
2. **Adaptive weight multipliers are not applied**: The code computes `prefixAffinityBoost` and `queueDepthBoost` but never uses them in the scoring loop. The LLM must discover this bug and fix it.
3. **SLO class comparison uses string literal**: `req.SLOClass == "realtime"` assumes a specific string format. Need to verify this matches the actual SLOClass values in BLIS.
4. **No temporal reasoning despite mentioning state.Clock**: The prompt mentions temporal patterns but the block code doesn't demonstrate using state.Clock

**Suggestions:**
1. Reduce the block to a minimal scaffold with TODO comments instead of complete implementations
2. Apply the computed boost multipliers in the scoring loop
3. Add a simple temporal tracking example (e.g., request counter for burst detection)

**Rating:** 6/10 - Good conceptual foundation but implementation details need work

#### Review by gemini-2.5-flash

**Strengths:**
1. Systematic approach covering all three questions jointly
2. Good use of empirical findings (H3, H9) to inform prompt design
3. Workload suite covers diverse scenarios (burst, growth, multi-tenant, pressure)
4. Clear explanation of how components work together

**Concerns:**
1. **Overfitting risk**: The block code is very specific. OpenEvolve may struggle to escape local optima because the structure is fixed. Consider providing less structure and more freedom for algorithmic discovery.
2. **CacheHitRate bonus (0.05) is arbitrary**: This constant should be evolved, not hardcoded. Same for threshold values (500 tokens, avgLoad > 10.0).
3. **Missing input validation**: What if `len(snapshots) == 0`? Division by zero in avgLoad computation.
4. **No exploration of alternative decision structures**: The prompt mentions "novel decision structures" but the block still uses weighted scoring + argmax. Consider enabling tournament selection, probabilistic routing, or multi-stage filtering.

**Suggestions:**
1. Make the block more skeletal: define variables and structure, but leave logic as TODO/hints
2. Add explicit examples of alternative decision structures in the prompt
3. Include guard clauses for edge cases (empty snapshots, zero divisors)
4. Consider adding a workload with extreme variance (single very large request mixed with many small)

**Rating:** 6.5/10 - Solid framework but could enable more algorithmic diversity

---

# Idea 2: Minimal Scaffold with Alternative Decision Structures

*Addressing feedback: Less prescriptive block, alternative decision structures, temporal tracking*

## Q1: EVOLVE-BLOCK Placement

**Recommended boundaries:** Same expanded scope as Idea 1 (pre-scoring through selection), but with a **minimal scaffold** that defines structure without implementation details.

**Rationale:** The reviews correctly identified that Idea 1's block was too prescriptive. By providing a minimal scaffold with placeholders and hints, we give the LLM more freedom to discover novel structures while still guiding it toward the expanded capabilities (request awareness, temporal reasoning, CacheHitRate usage).

**Code to include:**
```go
// EVOLVE-BLOCK-START
// === AVAILABLE CONTEXT (read-only) ===
// Request: req.InputTokens, req.OutputTokens, req.SLOClass, req.TenantID, req.Priority
// Snapshots: snap.ID, snap.QueueDepth, snap.BatchSize, snap.PendingRequests,
//            snap.KVUtilization, snap.FreeKVBlocks, snap.CacheHitRate, snap.EffectiveLoad()
// Cluster: state.Clock (microseconds), len(snapshots)

// === PHASE 1: Feature extraction (EVOLVE THIS) ===
// Hint: Classify request by size, SLO, or expected cost
// Hint: Compute aggregate metrics (total load, load variance, max queue)
// Hint: Track temporal patterns using state.Clock

// === PHASE 2: Scoring or alternative decision (EVOLVE THIS) ===
// Option A: Weighted scoring (current approach)
scores := make(map[string]float64, len(snapshots))
for i, scorer := range ws.scorers {
    dimScores := scorer(req, snapshots)
    for _, snap := range snapshots {
        s := dimScores[snap.ID]
        if s < 0 { s = 0 }
        if s > 1 { s = 1 }
        scores[snap.ID] += s * ws.weights[i]
    }
}

// Option B: Two-stage filtering (threshold then score)
// Option C: Tournament selection (pairwise comparison)
// Option D: Probabilistic routing (softmax over scores)
// Option E: Rule-based fast path + scoring fallback

// === PHASE 3: Selection (EVOLVE THIS) ===
// Default: argmax with index-based tie-breaking
bestScore := -1.0
bestIdx := 0
for i, snap := range snapshots {
    if scores[snap.ID] > bestScore {
        bestScore = scores[snap.ID]
        bestIdx = i
    }
}
// Hint: Consider CacheHitRate for tie-breaking
// Hint: Consider SLO-aware selection (lower queue for realtime)
// Hint: Consider probabilistic selection to avoid herding
// EVOLVE-BLOCK-END
```

## Q2: System Prompt

**Prompt text:**
```
You are discovering routing algorithms for an LLM inference cluster. Goal: minimize end-to-end latency.

THE PROBLEM:
Requests arrive continuously. Each must be routed to one of N instances. Key tradeoffs:
- Cache affinity: routing similar requests to the same instance improves cache hits
- Load balancing: spreading requests prevents queue buildup
- Request size: large requests (many input tokens) take longer and benefit more from cache hits
- SLO classes: realtime requests need low queue wait; batch can tolerate more

AVAILABLE SIGNALS:
[Request properties]
- len(req.InputTokens): request size (small <100, medium 100-500, large >500)
- req.SLOClass: "realtime" | "interactive" | "batch"
- req.TenantID: tenant identifier (requests from same tenant often share prefixes)

[Instance state - FRESH at high rates]
- snap.QueueDepth: requests waiting
- snap.BatchSize: requests currently processing
- snap.PendingRequests: routed but not yet queued
- snap.EffectiveLoad(): QueueDepth + BatchSize + PendingRequests

[Instance state - STALE at high rates]
- snap.KVUtilization: cache usage [0-1]
- snap.FreeKVBlocks: available blocks
- snap.CacheHitRate: historical hit rate for this instance (CURRENTLY UNUSED - exploit this!)

[Cluster state]
- state.Clock: simulation time in microseconds (use for temporal reasoning)
- len(snapshots): number of instances

DECISION STRUCTURE OPTIONS (not just weighted scoring!):
1. Weighted scoring + argmax (current): combine signals, pick highest
2. Two-stage filtering: eliminate instances above load threshold, then score remainder
3. Tournament selection: pairwise comparisons until one winner
4. Probabilistic routing: softmax(scores) for stochastic selection (avoids herding)
5. Rule-based fast path: if conditions met, route immediately; else score
6. Multi-objective: Pareto-optimal selection across latency/cache/load dimensions

WHAT TO EVOLVE:
- Feature extraction: compute useful aggregates from signals
- Weight adaptation: adjust scorer importance based on cluster state
- Selection logic: alternatives to simple argmax
- Exploit unused signals: CacheHitRate, state.Clock for temporal patterns

CRITICAL CONSTRAINTS:
- Must set bestIdx to a valid index in range [0, len(snapshots))
- scores map must exist (used by return statement)
- All code must be valid Go
```

**Key guidance points:**
- Explicitly lists alternative decision structures beyond weighted scoring
- Categorizes signals by freshness (critical insight from H3)
- Suggests concrete strategies without implementing them
- Emphasizes unused signals (CacheHitRate, state.Clock)
- Clear output constraints to prevent broken code

## Q3: Workload Design

**Workload suite:** Same 4 workloads but with rationale mapped to decision structure discovery

| Workload | Rate | Requests | Key Challenge | Decision Structure Pressure |
|----------|------|----------|---------------|---------------------------|
| burst_steady | 250 | 6000 | Burst handling (CV=5.0) | Rewards two-stage filtering (reject overloaded instances during burst) |
| context_growth | 150 | 3000 | Cache affinity for multi-turn | Rewards rule-based fast path (always route multi-turn to same instance) |
| multi_tenant_chat | 200 | 5000 | Multi-prefix competition | Rewards probabilistic routing (avoid herding when prefixes compete) |
| prefix_pressure | 400 | 8000 | High load + 8 prefixes vs 4 instances | Rewards adaptive weight modulation under load |

**Additional workload consideration:** Add variance measurement
- Current workloads may have similar "easy" solutions
- Consider adding a **pathological workload** to stress-test edge cases:

| Workload | Rate | Requests | Key Challenge |
|----------|------|----------|---------------|
| whale_minnow | 100 | 2000 | Mix of 95% tiny requests (10 tokens) and 5% huge requests (2000 tokens) |

This forces the algorithm to handle bimodal distributions where a single "whale" request can block an instance.

## How Q1+Q2+Q3 Work Together

1. **Block scope (Q1)** provides a minimal scaffold with phase markers (Feature, Scoring, Selection) and hints for alternatives. This gives structure without constraining the algorithm.

2. **System prompt (Q2)** explicitly lists decision structure alternatives (two-stage filtering, tournament, probabilistic, rule-based) that the LLM can discover within the block scope. It also emphasizes the underutilized signals.

3. **Workloads (Q3)** are mapped to decision structures: bursts reward filtering, multi-turn rewards rule-based routing, multi-tenant rewards probabilistic selection. This creates diverse selection pressure.

**Key improvement over Idea 1:** Less prescriptive block code enables algorithmic diversity. The LLM can explore non-weighted-scoring approaches.

### Review: Idea 2

#### Review by claude-opus-4-6

**Strengths:**
1. Excellent reduction of prescriptiveness - scaffold with hints instead of implementation
2. Explicit enumeration of alternative decision structures expands search space
3. Phase markers (Feature/Scoring/Selection) provide structure without constraining logic
4. Mapping workloads to decision structures is insightful

**Concerns:**
1. **Still tied to scorer pipeline**: The block still uses `ws.scorers` and `ws.weights`, which limits how radically the algorithm can deviate. The LLM can't easily ignore scorers entirely.
2. **Option enumeration may anchor**: Listing Options A-E may cause the LLM to copy one verbatim rather than synthesize novel approaches
3. **whale_minnow workload not in actual evaluator**: It's mentioned as a suggestion but not implemented

**Suggestions:**
1. Consider whether scorers can be bypassed entirely (route directly based on signals)
2. Remove option labels (A, B, C...) - describe capabilities, not enumerated choices
3. Either implement whale_minnow or remove the suggestion to avoid confusion

**Rating:** 7.5/10 - Good balance of structure and freedom

#### Review by gemini-2.5-flash

**Strengths:**
1. Minimal scaffold is a significant improvement over Idea 1
2. Clear signal categorization by freshness
3. Multi-objective mention opens interesting evolutionary directions
4. Phase-based structure is intuitive for LLM modification

**Concerns:**
1. **Block length**: The minimal scaffold is still fairly long. Could be shorter to reduce context load on the LLM.
2. **Hint proliferation**: Many hints may dilute focus. Consider prioritizing the top 3-4 most impactful hints.
3. **No baseline performance reference**: The prompt doesn't tell the LLM what the current performance is. Without knowing that prefix-affinity:3,qd:2 achieves X ms, hard to know what "better" means.

**Suggestions:**
1. Add baseline performance numbers to the prompt (e.g., "current system achieves ~150ms average E2E on these workloads")
2. Reduce hints to the most impactful: (1) CacheHitRate exploitation, (2) temporal burst detection, (3) request-size-aware routing
3. Make block even more minimal - just the core loop with a single hint block

**Rating:** 7/10 - Good direction but could be more focused

---

# Idea 3: Focused Minimal Block with Baseline Performance Context

*Addressing feedback: Shorter block, fewer hints, baseline performance, bypassing scorer dependency*

## Q1: EVOLVE-BLOCK Placement

**Recommended boundaries:** Tightest minimal block that still enables signal-direct routing (bypassing scorers when beneficial). Keep the scorer loop as default but enable direct signal access.

**Rationale:** Reviews noted the scorer pipeline dependency. The key insight is that we want the LLM to potentially discover that direct signal routing (e.g., "always pick lowest QueueDepth instance if it has good CacheHitRate") can outperform weighted scoring in specific scenarios. The block must enable this.

**Code to include:**
```go
// EVOLVE-BLOCK-START
// BASELINE: current system achieves ~180ms avg E2E on test workloads
// SIGNALS: QueueDepth/BatchSize/PendingRequests (fresh), KVUtilization/CacheHitRate (stale at high rate)
// GOAL: reduce latency by adapting to request size, load level, or cache state

scores := make(map[string]float64, len(snapshots))
for i, scorer := range ws.scorers {
    dimScores := scorer(req, snapshots)
    for _, snap := range snapshots {
        s := dimScores[snap.ID]
        if s < 0 { s = 0 }
        if s > 1 { s = 1 }
        scores[snap.ID] += s * ws.weights[i]
    }
}

// EVOLVE: Add adaptive logic here - modify scores, add bonuses, or select differently
// Key opportunities: (1) CacheHitRate bonus, (2) load-based weight adjustment, (3) request-size routing

bestScore := -1.0
bestIdx := 0
for i, snap := range snapshots {
    if scores[snap.ID] > bestScore {
        bestScore = scores[snap.ID]
        bestIdx = i
    }
}
// EVOLVE-BLOCK-END
```

**Key design decisions:**
1. **Baseline in comments**: LLM knows what "better" means (~180ms target to beat)
2. **Minimal hints**: Only 3 key opportunities, not 10+ scattered hints
3. **Direct signal access**: snapshots are available for direct routing logic
4. **Freedom to restructure**: The LLM can wrap the entire block in conditionals, add pre-filtering, etc.

## Q2: System Prompt

**Prompt text:**
```
You are optimizing a request router for LLM inference. Current system: ~180ms average latency.

CORE TRADEOFF: Cache affinity (reuse cached KV blocks) vs Load balancing (spread requests evenly)

SIGNALS YOU CAN USE:
- len(req.InputTokens): request size. Large requests (>400 tokens) benefit more from cache hits.
- req.SLOClass: "realtime" needs fast response; "batch" tolerates delay.
- snap.QueueDepth, snap.BatchSize, snap.PendingRequests: current load (FRESH)
- snap.CacheHitRate: historical cache performance (NOT USED by default scorers - exploit this!)
- snap.EffectiveLoad(): total load = Queue + Batch + Pending
- state.Clock: simulation time in microseconds

TOP 3 IMPROVEMENT STRATEGIES:
1. **CacheHitRate bonus**: Add snap.CacheHitRate * factor to scores for instances with good cache performance
2. **Load-adaptive weights**: When total cluster load is high, increase queue-depth weight relative to prefix-affinity
3. **Request-size routing**: Route large requests to instances with best CacheHitRate; route small requests to lowest load

WHAT YOU CAN DO:
- Modify scores[] values after the scorer loop
- Add conditional logic before scoring (e.g., fast-path for specific request types)
- Change selection logic (not just argmax - consider tie-breaking on CacheHitRate)
- Compute aggregate metrics from snapshots (total load, max queue, variance)

OUTPUT REQUIREMENT: bestIdx must be set to valid index [0, len(snapshots)-1]
```

**Key improvements:**
1. **Concrete baseline** (180ms) gives optimization target
2. **Only 3 strategies** instead of many scattered hints
3. **Clear capability listing** of what can be modified
4. **Shorter prompt** reduces cognitive load

## Q3: Workload Design

**Workload suite:** Keep the existing 4 workloads but add explicit success criteria mapping

| Workload | Rate | Requests | Strategy Tested | Success Indicator |
|----------|------|----------|-----------------|-------------------|
| burst_steady | 250 | 6000 | Load-adaptive weights | Reduced P99 during burst periods |
| context_growth | 150 | 3000 | CacheHitRate exploitation | Improved mean latency for multi-turn |
| multi_tenant_chat | 200 | 5000 | Request-size routing | Better fairness across tenants |
| prefix_pressure | 400 | 8000 | All strategies combined | Overall latency reduction under stress |

**Workload-Strategy Alignment:**
- **burst_steady** has CV=5.0 gamma arrivals creating severe bursts. Strategy 2 (load-adaptive weights) should help by boosting queue-depth weight during high-load periods.
- **context_growth** has multi-turn sessions with context accumulation. Strategy 1 (CacheHitRate bonus) should help by routing follow-up requests to instances with good cache performance.
- **multi_tenant_chat** has 5 tenants with different prefix groups. Strategy 3 (request-size routing) helps match large batch requests to cache-optimal instances while keeping realtime requests on low-queue instances.
- **prefix_pressure** is the stress test that requires all strategies working together.

## How Q1+Q2+Q3 Work Together

1. **Block scope (Q1)** is minimal but enables direct signal access. The LLM can:
   - Modify scores post-loop (Strategy 1: CacheHitRate bonus)
   - Add pre-loop conditionals for adaptive behavior (Strategy 2: load-adaptive)
   - Change selection logic (Strategy 3: request-aware selection)

2. **System prompt (Q2)** focuses on exactly 3 strategies that map to the block's capabilities. No overwhelming option lists - just clear opportunities.

3. **Workloads (Q3)** have explicit strategy-to-workload mapping:
   - burst_steady rewards Strategy 2
   - context_growth rewards Strategy 1
   - multi_tenant_chat rewards Strategy 3
   - prefix_pressure rewards integration of all strategies

**Coherence test:** Each strategy can be implemented within the block, is described in the prompt, and is stress-tested by at least one workload.

### Review: Idea 3

#### Review by claude-opus-4-6

**Strengths:**
1. **Excellent focus**: 3 strategies instead of 10+ hints is much cleaner
2. **Baseline in code**: ~180ms gives concrete optimization target
3. **Strategy-workload mapping**: Clear testability for each proposed improvement
4. **Minimal block**: Shorter, easier for LLM to modify confidently

**Concerns:**
1. **180ms baseline may be inaccurate**: Need to verify actual baseline performance by running evaluator
2. **CacheHitRate staleness**: The prompt mentions it's stale at high rates but still recommends using it. Need to clarify when it's reliable.
3. **Limited structural innovation**: Block still constrains to "modify scores + argmax" pattern

**Suggestions:**
1. Run evaluator to get actual baseline numbers for each workload
2. Add note about CacheHitRate reliability: "CacheHitRate is useful at moderate rates (<300 req/s) but stale at high rates"
3. Consider one additional hint about structural alternatives (e.g., "You may bypass scoring entirely for specific request types")

**Rating:** 8.5/10 - Strong, focused design with clear testability

#### Review by gemini-2.5-flash

**Strengths:**
1. **Concise and actionable**: Prompt is half the length of Idea 2, more actionable
2. **Clear improvement path**: 3 strategies give LLM concrete directions to explore
3. **Workload-strategy alignment**: Explicit mapping enables post-hoc analysis of what worked
4. **Proper baseline context**: LLM knows what "better" means

**Concerns:**
1. **May be too focused**: Only 3 strategies may limit discovery of truly novel approaches. Consider adding "or invent something new" as 4th option.
2. **No negative examples**: Prompt doesn't warn about pitfalls (e.g., "don't use kv-utilization as sole signal at high rates")
3. **Block comment density**: Block has 5 comment lines for ~20 code lines - may be noisy

**Suggestions:**
1. Add brief anti-pattern warning: "AVOID: kv-utilization alone at high rates (becomes uniform)"
2. Reduce block comments to just baseline and signals summary
3. Add "Strategy 4: Discover something new" to encourage innovation beyond listed strategies

**Rating:** 8/10 - Clean design, could benefit from anti-patterns and innovation encouragement

---

## Executive Summary

### Iteration Process Overview

Three iterations explored different balances between structure and freedom:

| Idea | Block Style | Prompt Focus | Rating |
|------|-------------|--------------|--------|
| Idea 1 | Prescriptive (full implementation) | Many capabilities | 6-6.5/10 |
| Idea 2 | Scaffold with options | Alternative decision structures | 7-7.5/10 |
| Idea 3 | Minimal with baseline | Top 3 strategies | 8-8.5/10 |

**Key insights from iterations:**
1. **Less is more**: Overly prescriptive blocks constrain discovery; minimal scaffolds enable innovation
2. **Focus beats breadth**: 3 clear strategies outperform 10+ scattered hints
3. **Baseline matters**: LLMs need concrete performance targets to optimize against
4. **Workload-strategy mapping**: Explicit alignment enables systematic analysis

### Final Recommended Configuration

#### EVOLVE-BLOCK (Q1)

Use the **Idea 3 minimal block** with one addition from reviewer feedback - a hint about bypassing scoring:

```go
// EVOLVE-BLOCK-START
// BASELINE: ~180ms avg E2E (run evaluator to confirm actual baseline)
// SIGNALS: QueueDepth/BatchSize/PendingRequests (FRESH), KVUtilization/CacheHitRate (STALE at >300 req/s)
// ANTI-PATTERN: kv-utilization alone becomes uniform at high rates - always combine with queue-depth

scores := make(map[string]float64, len(snapshots))
for i, scorer := range ws.scorers {
    dimScores := scorer(req, snapshots)
    for _, snap := range snapshots {
        s := dimScores[snap.ID]
        if s < 0 { s = 0 }
        if s > 1 { s = 1 }
        scores[snap.ID] += s * ws.weights[i]
    }
}

// EVOLVE: Improve on baseline. Key opportunities:
// 1. CacheHitRate bonus (unused signal)
// 2. Load-adaptive adjustments
// 3. Request-size-aware routing
// 4. Or discover something entirely new

bestScore := -1.0
bestIdx := 0
for i, snap := range snapshots {
    if scores[snap.ID] > bestScore {
        bestScore = scores[snap.ID]
        bestIdx = i
    }
}
// EVOLVE-BLOCK-END
```

#### System Prompt (Q2)

Use the **Idea 3 prompt** with anti-pattern warning added:

```
You are optimizing a request router for LLM inference. Current system: ~180ms average latency.

CORE TRADEOFF: Cache affinity (reuse cached KV blocks) vs Load balancing (spread requests evenly)

SIGNALS YOU CAN USE:
- len(req.InputTokens): request size. Large requests (>400 tokens) benefit more from cache hits.
- req.SLOClass: "realtime" needs fast response; "batch" tolerates delay.
- snap.QueueDepth, snap.BatchSize, snap.PendingRequests: current load (FRESH)
- snap.CacheHitRate: historical cache performance (NOT USED by default - exploit this!)
- snap.EffectiveLoad(): total load = Queue + Batch + Pending
- state.Clock: simulation time in microseconds

ANTI-PATTERN: kv-utilization alone becomes uniform at high request rates. Always combine with queue-depth.

TOP 3 IMPROVEMENT STRATEGIES:
1. **CacheHitRate bonus**: Add snap.CacheHitRate * factor to scores for better cache instances
2. **Load-adaptive weights**: Increase queue-depth importance when cluster load is high
3. **Request-size routing**: Route large requests to best CacheHitRate; small to lowest load

Or discover something entirely new!

WHAT YOU CAN DO:
- Modify scores[] after the scorer loop
- Add conditional logic before scoring
- Change selection logic (tie-breaking on CacheHitRate)
- Compute aggregate metrics (total load, variance)
- Bypass scoring entirely for specific fast-paths

OUTPUT REQUIREMENT: bestIdx must be valid index [0, len(snapshots)-1]
```

#### Workloads (Q3)

Keep the existing 4 workloads with documented strategy alignment:

| Workload | Rate | Requests | Primary Strategy | Metric Focus |
|----------|------|----------|------------------|--------------|
| burst_steady | 250 | 6000 | Load-adaptive (Strategy 2) | P99 latency |
| context_growth | 150 | 3000 | CacheHitRate (Strategy 1) | Mean latency |
| multi_tenant_chat | 200 | 5000 | Request-size (Strategy 3) | Per-tenant fairness |
| prefix_pressure | 400 | 8000 | All strategies | Overall E2E |

### Concrete Next Steps

1. **Verify baseline**: Run `python examples/blis_router/evaluator.py` with initial_program.py to get actual baseline numbers for each workload

2. **Update initial_program.py**: Replace current EVOLVE-BLOCK with the recommended minimal block

3. **Create config.yaml**: Ensure OpenEvolve config uses the recommended system prompt

4. **Run pilot evolution**: Execute 20-50 iterations to validate the configuration produces valid code and measurable improvement

5. **Analyze results**: After pilot run, check:
   - Which strategies emerged in top-performing variants?
   - Did any novel approaches emerge beyond the 3 suggested strategies?
   - Which workloads showed most improvement?

6. **Iterate on workloads**: If all strategies help all workloads equally, consider adding a workload that specifically penalizes one strategy (forcing specialization)

### Risk Assessment

| Risk | Mitigation |
|------|------------|
| LLM produces invalid Go syntax | Build failure gives -100000 score; rapid feedback |
| Strategies don't help | Workload redesign or prompt refinement |
| Local optimum (small tweaks only) | Consider diff-based evolution settings in OpenEvolve |
| CacheHitRate unreliable at high rates | Document in prompt; workloads include moderate rates |

---
