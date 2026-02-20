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

## Background

### Codebase Context

**BLIS Routing Architecture:**
The routing system uses a `RoutingPolicy` interface where `Route(req *Request, state *RouterState)` returns a `RoutingDecision`. The `WeightedScoring` policy combines multiple scorers with configurable weights, computing composite scores and selecting via argmax.

**Available Signals:**
- **Request fields:** `InputTokens` (length, hash), `OutputTokens`, `Priority`, `SLOClass`, `TenantID`
- **Per-instance snapshot:** `QueueDepth` (fresh), `BatchSize` (fresh), `PendingRequests` (fresh), `KVUtilization` (stale at high rate), `FreeKVBlocks` (stale), `CacheHitRate` (unused in main loop), `EffectiveLoad()` helper
- **Cluster state:** `state.Snapshots` (all instances), `state.Clock` (simulation time - enables temporal reasoning)

**Current Scorers:**
- `prefix-affinity`: Proportional prefix match ratio via router-side cache
- `queue-depth`: Min-max normalization of EffectiveLoad (fresh signal)
- `kv-utilization`: 1 - KVUtilization (stale at high rates)
- `load-balance`: 1/(1 + EffectiveLoad)

**Key Limitations:**
1. Static weights regardless of workload phase (burst vs steady)
2. No request-size-aware routing (large inputs routed same as small)
3. Clock signal unused - no temporal adaptation
4. CacheHitRate available but not directly used in scoring

### Related Work

**Prefix-Aware Routing in LLM Serving:**
Systems like vLLM and SGLang implement prefix caching where shared prompts (system prompts, few-shot examples) are cached and reused. The key routing challenge is balancing cache locality against load distribution. Heavy prefix-affinity concentrates requests on cached instances but risks queue buildup.

**Load Balancing for ML Inference:**
Traditional approaches include round-robin, least-connections, and weighted scoring. For LLM inference, the challenge is that request costs vary dramatically (10x+ based on input length and cache state). Queue-depth signals provide fresher load information than utilization metrics at high request rates.

**Adaptive Request Scheduling:**
Research in adaptive scheduling suggests that workload-aware policies outperform static configurations. Key signals include request arrival patterns (bursty vs steady), request characteristics (size, priority), and system state trends. Temporal reasoning enables burst detection and preemptive load balancing.

**Evolutionary Algorithm Discovery:**
AlphaEvolve demonstrates using LLMs to evolve code for optimization problems. The approach iteratively mutates code within marked regions, evaluates against fitness functions, and maintains diversity via MAP-Elites. For routing, this enables discovering novel decision structures beyond hand-designed heuristics.

### Hypothesis Findings Summary

**H3: Signal Freshness (queue-depth vs kv-utilization)**

At high request rates (5000 req/s), queue-depth distributes 200x more evenly than kv-utilization alone. The root cause is DES event ordering: all routing decisions at tick T drain before instance-level events (batch formation, KV allocation) update. Queue-depth uses `PendingRequests` which updates synchronously at routing time, while KVUtilization only changes after batch formation.

Key results at rate=5000:
| Scorer | TTFT Mean | TTFT P99 | Dist StdDev |
|--------|-----------|----------|-------------|
| queue-depth | 1290-1319ms | 2532-2604ms | 0.7-1.0 |
| kv-utilization | 2259-3644ms | 7870-12285ms | 142-226 |

**Implication:** Always include queue-depth in weighted routing. Never use kv-utilization as sole scorer at high rates. Combined scorers (even kv:5,qd:1) produce near-perfect balance because stale scorers add zero information.

**H9: Prefix Caching Effectiveness**

Prefix caching dramatically reduces TTFT - up to 95.8% reduction at maximum prefix length (512 of 768 total tokens). Cache hit rate is predictable: approximately `prefix_length / total_input` for large request counts.

| Prefix Length | TTFT Mean | Cache Hit Rate | TTFT Reduction |
|:---:|:---:|:---:|:---:|
| 0 | 728.3ms | 0.0000 | baseline |
| 256 | 184.6ms | 0.3032 | -74.7% |
| 512 | 30.2ms | 0.6071 | -95.8% |

**Implication:** Workloads with shared system prompts benefit massively from prefix caching. Use prefix-affinity routing at cluster scale to maintain cache locality.

**Prefix-Affinity vs Queue-Depth Tradeoff**

For multi-turn chat, prefix-affinity is 2.45x better than queue-depth (28.2ms vs 69.0ms TTFT) because queue-depth actively destroys cache locality by routing sessions away from cached instances.

However, there is a concentration vs distribution tradeoff:
- At low load: Round-robin achieves 62.9% cache hit rate with perfect distribution (21.8ms TTFT), beating prefix-affinity (55.7% hits, 28.2ms TTFT)
- At high load (rate=5000): Prefix-affinity wins decisively (205ms vs 892ms) because reduced prefill outweighs concentration overhead

**Implication:** Multi-turn chat should always use prefix-affinity. The optimal weight depends on load level - heavy prefix-affinity hurts at low load (creates unnecessary concentration), but wins at high load where cache reuse dominates.

---

# Idea 1: Multi-Layer EVOLVE-BLOCK Strategy for Routing Discovery

**Research Question:** Q1 - Where to place EVOLVE-BLOCK markers

## Proposed Approach

Place EVOLVE-BLOCK markers at **three hierarchical levels** to enable discovery of both local optimizations and structural innovations:

### Level 1: Score Computation Block (Lines 137-165 in initial_program.py)
**Current placement** - Already marked. This is the innermost loop where composite scores are computed and argmax selection happens.

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

// Argmax: select instance with highest composite score
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

**Evolution potential:** Weight modulation based on request size (`len(req.InputTokens)`), dynamic weight adjustment using snapshot signals, non-linear score combination.

### Level 2: Pre-Scoring Request Classification (NEW - Insert before Line 137)
Add a **second EVOLVE-BLOCK** for request-aware preprocessing:

```go
// EVOLVE-BLOCK-START (REQUEST-CLASSIFIER)
// Request classification for adaptive routing
requestClass := 0  // 0=small, 1=medium, 2=large
inputLen := len(req.InputTokens)
if inputLen > 512 {
    requestClass = 2
} else if inputLen > 128 {
    requestClass = 1
}

// Cluster state classification
avgLoad := 0.0
for _, snap := range snapshots {
    avgLoad += float64(snap.EffectiveLoad())
}
avgLoad /= float64(len(snapshots))
loadClass := 0  // 0=low, 1=high
if avgLoad > 10.0 {
    loadClass = 1
}
// EVOLVE-BLOCK-END (REQUEST-CLASSIFIER)
```

**Evolution potential:** Discover request size thresholds, cluster load thresholds, temporal patterns using `state.Clock`, multi-factor classification logic.

### Level 3: Per-Instance Score Adjustment (NEW - Insert after score accumulation, before argmax)
Add a **third EVOLVE-BLOCK** for instance-specific adjustments:

```go
// After score accumulation loop, before argmax
// EVOLVE-BLOCK-START (INSTANCE-ADJUST)
// Per-instance score adjustment based on direct signals
for _, snap := range snapshots {
    // Cache hit rate bonus (currently unused signal)
    scores[snap.ID] += snap.CacheHitRate * 0.1

    // Penalize heavily loaded instances for large requests
    if requestClass == 2 && snap.EffectiveLoad() > 15 {
        scores[snap.ID] *= 0.8
    }

    // Bonus for instances with free KV blocks
    if snap.FreeKVBlocks > 1000 {
        scores[snap.ID] += 0.05
    }
}
// EVOLVE-BLOCK-END (INSTANCE-ADJUST)
```

**Evolution potential:** Discover how to use CacheHitRate directly, request-size-aware load penalties, KV block thresholds.

## Rationale

This three-level approach addresses the hypothesis findings:

1. **H3 (Signal Freshness):** Level 1 can evolve to weight queue-depth more heavily, while Level 3 can add direct load penalties that respond to fresh signals.

2. **H9 (Prefix Caching):** Level 3 introduces CacheHitRate as a direct signal, enabling discovery of cache-aware adjustments beyond the prefix-affinity scorer.

3. **Prefix-Affinity vs Queue-Depth Tradeoff:** Level 2 enables workload-adaptive weight selection - the evolved code can choose different strategies based on load class (low load = more distribution, high load = more cache affinity).

The hierarchical structure ensures:
- **Exploration breadth:** LLM can mutate any of three blocks independently
- **Composition:** Innovations at different levels can combine synergistically
- **Fallback safety:** If one level produces invalid code, others remain functional

## Expected Impact

- **10-15% latency reduction** from request-size-aware routing (routing large requests away from loaded instances)
- **5-10% additional reduction** from direct CacheHitRate utilization (currently unused signal)
- **Adaptive behavior** across workload phases without manual tuning

## Risks/Limitations

1. **Increased complexity:** Three EVOLVE-BLOCKS means 3x search space, potentially slower convergence
2. **Block interaction bugs:** Mutations in one block may conflict with assumptions in another
3. **Go syntax errors:** LLM may generate invalid Go code, requiring robust validation
4. **Overfitting:** Evolved code may specialize to evaluation workloads rather than generalizing

**Mitigation:** Use staged evaluation (quick syntax check, then short sim, then full sim) to fail fast on invalid mutations. Include diverse workloads in evaluation to prevent overfitting.

## Reviews for Idea 1

### Review by Claude Opus (aws/claude-opus-4-6)

**Strengths:**
- The hierarchical decomposition is well-motivated and maps cleanly to the identified limitations (static weights, no request awareness, unused signals)
- Level 2 (request classification) directly addresses the hypothesis finding that optimal prefix-affinity weight depends on load level - this is the most promising aspect
- The proposal to use CacheHitRate directly in Level 3 is valuable since H9 shows cache hits reduce TTFT by up to 95.8%

**Concerns:**
1. **Block interaction complexity:** The proposal assumes Level 3 can reference `requestClass` from Level 2, but OpenEvolve mutates blocks independently. If Level 2 is mutated to remove `requestClass`, Level 3 breaks. Consider making blocks self-contained or explicitly documenting cross-block dependencies.

2. **Threshold magic numbers:** The initial values (512, 128, 10.0, 15, 1000) are arbitrary. While evolution can discover better values, starting far from optimal may slow convergence. Recommend: derive initial thresholds from hypothesis data (e.g., "large" = requests that exceed typical batch capacity).

3. **Missing temporal dimension:** The proposal mentions `state.Clock` but doesn't include it in any block. Consider adding a Level 0 block for temporal state tracking (exponential moving average of request rate, burst detection).

**Recommendation:** Proceed with modification. Consolidate Levels 1 and 3 into a single block to avoid cross-block dependencies. Add explicit clock-based temporal features to Level 2.

**Score:** 7/10

### Review by GPT-4o (Azure/gpt-4o)

**Strengths:**
- Clear structure with specific line numbers and concrete code examples
- Good alignment with hypothesis findings - each level maps to a specific H3/H9 insight
- The mitigation strategy (staged evaluation) is practical and addresses the main risk

**Concerns:**
1. **Search space explosion:** Three independent EVOLVE-BLOCKs with O(n) possible mutations each creates O(n^3) interaction space. OpenEvolve's MAP-Elites may struggle to explore this efficiently. Consider: start with single block, add others incrementally based on convergence.

2. **CacheHitRate staleness:** The proposal uses CacheHitRate in Level 3, but per the background, this signal is "stale at high rate" like KVUtilization. H3 shows stale signals become useless at rate=5000. The proposed 0.1 weight may not be robust.

3. **No baseline preservation:** All three blocks are fully mutable from iteration 1. Risk: evolution destroys working baseline before discovering improvements. Consider: mark a "frozen core" region that implements the current llm-d default, evolve around it.

**Recommendation:** Conditionally accept. Add constraint that Level 1 core scoring loop is preserved for first N iterations, allowing only Level 2/3 modifications initially.

**Score:** 6.5/10

### Review by Gemini Flash (GCP/gemini-2.5-flash)

**Strengths:**
- Actionable proposal with exact insertion points and working Go code
- The request classification approach (Level 2) is the key innovation - enables the adaptive behavior that static weights cannot achieve
- Risk section is honest about complexity tradeoffs

**Concerns:**
1. **Multiplicative vs additive adjustments:** Level 3 mixes additive (`+= snap.CacheHitRate * 0.1`) and multiplicative (`*= 0.8`) score modifications. This makes the score range unpredictable and may break the argmax assumption that higher is always better.

2. **FreeKVBlocks threshold (1000) is cluster-dependent:** Different instance configurations have different total KV blocks. A fixed threshold won't generalize. Consider: normalize to `snap.FreeKVBlocks / snap.TotalKVBlocks` (requires adding TotalKVBlocks to RoutingSnapshot).

3. **Missing SLO-awareness:** The background mentions `SLOClass` and `Priority` in request fields, but none of the blocks use them. For production routing, SLO-aware prioritization may be more impactful than size-based classification.

**Recommendation:** Accept with revisions. Normalize all adjustments to additive-only in [0,1] range. Add SLOClass to Level 2 classification. Consider making thresholds relative to cluster capacity rather than absolute.

**Score:** 7/10

---

# Idea 2: Domain-Specific System Prompt for LLM Routing Discovery

**Research Question:** Q2 - What system prompt guides novel routing discovery

## Proposed Approach

Design a system prompt that encodes domain knowledge about LLM inference routing while encouraging exploration beyond conventional approaches. The prompt should be placed in OpenEvolve's configuration as the `system_prompt` field.

### Proposed System Prompt

```
You are an expert in distributed systems optimization, specializing in request routing for large language model (LLM) inference clusters. Your task is to evolve Go code that implements routing decisions for the BLIS simulator.

## Domain Context

LLM inference has unique characteristics that differ from traditional load balancing:
1. **Prefix caching:** Requests sharing input prefixes benefit from routing to instances with cached KV blocks. Cache hits can reduce time-to-first-token by 74-96% (measured in BLIS).
2. **Signal freshness:** At high request rates (>1000 req/s), some signals become stale due to discrete event simulation ordering:
   - FRESH signals (update synchronously): QueueDepth, BatchSize, PendingRequests, EffectiveLoad()
   - STALE signals (update after batch events): KVUtilization, FreeKVBlocks, CacheHitRate
3. **Concentration vs distribution tradeoff:** Heavy prefix-affinity creates cache locality but risks queue buildup. The optimal balance depends on current load.

## Available Signals

For each instance snapshot, you have access to:
- `snap.QueueDepth` (int): Requests waiting in queue [FRESH]
- `snap.BatchSize` (int): Requests currently in batch [FRESH]
- `snap.PendingRequests` (int): Routed but not queued [FRESH]
- `snap.EffectiveLoad()` (int): QueueDepth + BatchSize + PendingRequests [FRESH]
- `snap.KVUtilization` (float64): 0.0-1.0 memory usage [STALE at high rate]
- `snap.FreeKVBlocks` (int64): Available KV cache blocks [STALE at high rate]
- `snap.CacheHitRate` (float64): Historical cache hit ratio [UNUSED - opportunity!]

For the request, you have:
- `req.InputTokens` ([]int): Input token sequence (use len() for size)
- `req.OutputTokens` (int): Expected output length
- `req.Priority` (float64): Request priority
- `req.SLOClass` (string): SLO tier ("latency-sensitive", "throughput", etc.)

For cluster state:
- `state.Clock` (time value): Current simulation time [UNUSED - enables temporal reasoning]
- `state.Snapshots` ([]RoutingSnapshot): All instance states

## Optimization Objectives

Primary: Minimize mean time-to-first-token (TTFT) across all requests
Secondary: Minimize P99 TTFT (tail latency)
Constraint: Maintain reasonable load distribution (avoid >50% of requests to single instance)

## Innovation Directions to Explore

1. **Request-size-aware routing:** Route large requests (>512 tokens) to less-loaded instances even if prefix affinity is lower.
2. **Temporal adaptation:** Use `state.Clock` to detect burst patterns and shift weight toward distribution during bursts.
3. **Direct CacheHitRate usage:** The CacheHitRate signal is currently unused in scoring. Consider adding bonus for high-cache-hit instances.
4. **Non-linear score combination:** Instead of weighted sum, explore min(), max(), or conditional selection.
5. **Load-adaptive weights:** Multiply prefix-affinity weight by (1 - avgLoad/threshold) to reduce affinity under high load.

## Code Constraints

- Output must be valid Go code
- Scores should remain in [0, 1] range or be normalized
- Use only the available signals listed above
- The final selection must use argmax over the scores map

## Example Mutation Ideas

```go
// Idea: Reduce prefix-affinity weight under high load
avgLoad := 0.0
for _, s := range snapshots { avgLoad += float64(s.EffectiveLoad()) }
avgLoad /= float64(len(snapshots))
affinityDamper := 1.0 - (avgLoad / 20.0)  // Reduce affinity as load approaches 20
if affinityDamper < 0.3 { affinityDamper = 0.3 }  // Floor at 30%
```

```go
// Idea: Bonus for unused CacheHitRate signal
for _, snap := range snapshots {
    scores[snap.ID] += snap.CacheHitRate * 0.15  // Direct cache hit bonus
}
```

```go
// Idea: Penalize large requests to loaded instances
inputLen := len(req.InputTokens)
if inputLen > 400 {
    for _, snap := range snapshots {
        if snap.EffectiveLoad() > 10 {
            scores[snap.ID] *= 0.7  // 30% penalty
        }
    }
}
```

Think creatively but stay grounded in the domain constraints. Small, targeted changes often outperform radical rewrites.
```

### Prompt Structure Rationale

The prompt is organized into six sections with specific purposes:

1. **Domain Context:** Establishes the unique characteristics of LLM routing (prefix caching, signal freshness) - directly from H3 and H9 findings
2. **Available Signals:** Complete API reference with freshness annotations to guide signal selection
3. **Optimization Objectives:** Clear fitness function to guide evolution direction
4. **Innovation Directions:** Seed ideas based on identified limitations, steering exploration
5. **Code Constraints:** Guardrails to prevent invalid code generation
6. **Example Mutations:** Concrete code snippets as starting points for variation

## Rationale

This prompt design addresses several challenges in using LLMs for code evolution:

1. **Grounding in empirical data:** The freshness annotations (FRESH/STALE) encode H3 findings, preventing the LLM from over-relying on stale signals like KVUtilization.

2. **Explicit unused signals:** Highlighting CacheHitRate and state.Clock as "UNUSED - opportunity!" directs exploration toward novel features rather than rehashing existing scorers.

3. **Quantitative guidance:** Including specific numbers (74-96% TTFT reduction, >1000 req/s staleness threshold) helps the LLM calibrate its mutations.

4. **Balanced exploration-exploitation:** The "Innovation Directions" section seeds creative directions without being prescriptive, while example code provides exploitation anchors.

5. **Safety constraints:** Explicit score range constraints and "use only available signals" prevent hallucination of non-existent APIs.

## Expected Impact

- **Faster convergence:** Domain knowledge reduces random exploration, focusing mutations on promising regions
- **Novel discoveries:** Explicit mention of unused signals (CacheHitRate, Clock) increases probability of exploiting them
- **Fewer invalid mutations:** API documentation and constraints reduce syntax errors and invalid signal usage
- **Better generalization:** Multi-objective framing (mean + P99 + distribution) prevents overfitting to single metrics

## Risks/Limitations

1. **Over-specification:** Too much guidance may constrain creativity, causing the LLM to only produce variations of the example code
2. **Prompt length:** At ~800 tokens, this prompt may consume significant context window in smaller models
3. **Stale prompt:** If BLIS API changes, the signal documentation becomes incorrect
4. **Bias toward additive changes:** Example mutations all show additive improvements; may discourage structural changes

**Mitigation:** A/B test prompt variants - one with examples, one without. Track mutation diversity (unique AST patterns) as a secondary metric alongside fitness.

## Reviews for Idea 2

### Review by Claude Opus (aws/claude-opus-4-6)

**Strengths:**
- Excellent encoding of H3 signal freshness findings via FRESH/STALE annotations - this is exactly the kind of domain knowledge that prevents LLMs from making uninformed choices
- The "UNUSED - opportunity!" markers are a clever nudge that should increase exploration of CacheHitRate and Clock signals
- Example mutations are well-calibrated - specific enough to be useful, general enough to allow variation
- Multi-objective framing (mean TTFT + P99 + distribution constraint) is important for production-ready routing

**Concerns:**
1. **Missing negative examples:** The prompt shows what to do, but not what to avoid. Consider adding: "Avoid: using KVUtilization alone at high rates (200x worse distribution per H3), removing queue-depth entirely, ignoring load balance."

2. **Quantitative guidance could backfire:** Stating "74-96% TTFT reduction" may anchor the LLM to expect similar gains, leading to disappointment when incremental improvements are smaller. Consider framing as "up to 96% in ideal conditions."

3. **No guidance on mutation granularity:** Should mutations be single-line changes or multi-line restructuring? AlphaEvolve works best with small, targeted changes. Add: "Prefer single-concept changes per mutation."

4. **Clock usage is mentioned but not explained:** "Use state.Clock to detect burst patterns" assumes the LLM knows how to implement burst detection. Consider adding a concrete example of clock-based temporal tracking.

**Recommendation:** Accept with additions. Add negative examples section and a concrete clock-based example. Clarify expected mutation granularity.

**Score:** 8/10

### Review by GPT-4o (Azure/gpt-4o)

**Strengths:**
- Comprehensive signal documentation with types - this is exactly what an LLM needs to generate valid Go code
- The "Innovation Directions" section strikes a good balance between guidance and freedom
- Code constraints section should reduce syntax errors significantly
- Well-structured with clear section boundaries

**Concerns:**
1. **Prompt length vs model context:** 800 tokens is substantial. For OpenEvolve with diff-based mutations, the prompt competes with code context. Calculate: if using GPT-4 (8K context), prompt (800) + code (300) + diff history (variable) could crowd out important context. Consider a shorter "core prompt" variant for constrained contexts.

2. **Example code creates mode collapse risk:** Three similar examples (all using for-loops, all additive/multiplicative adjustments) may cause the LLM to only generate variations of this pattern. Consider: one example each of different patterns (loop-based, conditional, table-lookup).

3. **Missing "what not to change" guidance:** The prompt doesn't clarify that the observer notification pattern (lines 167-169 in initial_program.py) must be preserved. Mutations that break observer calls would break prefix-affinity tracking.

4. **No temperature/sampling guidance:** The prompt focuses on content but doesn't address how to configure LLM sampling. For evolution, higher temperature (0.9-1.0) with nucleus sampling often produces more diverse mutations.

**Recommendation:** Accept with caveats. Test with and without examples to measure mode collapse. Add "preserve observer calls" to constraints.

**Score:** 7.5/10

### Review by Gemini Flash (GCP/gemini-2.5-flash)

**Strengths:**
- The six-section structure is pedagogically sound - context before API, API before objectives, objectives before examples
- Freshness annotations are the key insight - this distills H3 findings into actionable guidance
- Example mutations are production-quality Go code that would compile
- Explicit score range constraint prevents common failure mode of unbounded scores

**Concerns:**
1. **No validation feedback loop:** The prompt tells the LLM what to produce but doesn't describe how it will be evaluated. Adding "Your code will be tested against: (1) syntax check via `go build`, (2) 1000-request simulation, (3) 10000-request full evaluation" would help the LLM understand the fitness landscape.

2. **Request fields list incomplete:** The prompt lists `req.InputTokens`, `OutputTokens`, `Priority`, `SLOClass` but the background also mentions `TenantID`. For multi-tenant routing scenarios, tenant isolation may be important. Add TenantID or explicitly note it's excluded.

3. **"Think creatively" is vague:** The closing instruction could be more specific. Consider: "Explore one novel combination of signals that the current scorers don't use together."

4. **No versioning strategy:** If the prompt needs to evolve (e.g., new signals added to BLIS), there's no mechanism to track which prompt version produced which results. Consider adding a prompt version identifier.

**Recommendation:** Accept. Add evaluation feedback description and TenantID to signal list. Consider prompt versioning for reproducibility.

**Score:** 7.5/10

---

# Idea 3: Adversarial Workload Suite for Routing Differentiation

**Research Question:** Q3 - What workloads reveal routing performance differences

## Proposed Approach

Design a suite of **five complementary workloads** that stress different aspects of routing decisions, ensuring evolved algorithms are tested on scenarios where static weighted scoring fails. Each workload targets a specific limitation identified in the hypothesis findings.

### Workload 1: Burst-Then-Steady (Temporal Adaptation Test)

**Purpose:** Test whether routing adapts to changing load patterns. Static weights cannot handle transitions; adaptive routing should detect the burst and shift strategy.

**Parameters:**
```yaml
name: burst_then_steady
phases:
  - name: burst
    duration_seconds: 30
    request_rate: 5000  # High rate where H3 shows signal staleness matters
    input_tokens:
      distribution: normal
      mean: 256
      stddev: 64
    prefix_length: 128  # Shared system prompt

  - name: steady
    duration_seconds: 120
    request_rate: 500   # Lower rate where prefix-affinity should dominate
    input_tokens:
      distribution: normal
      mean: 256
      stddev: 64
    prefix_length: 128
```

**Expected behavior:**
- During burst: Should weight queue-depth heavily (fresh signal)
- During steady: Should weight prefix-affinity heavily (cache reuse dominates)
- Static weights: Optimal for one phase, suboptimal for other
- Adaptive routing: 15-25% TTFT reduction by phase-aware weight adjustment

**Baseline comparison:** llm-d default (pa:3, qd:2, kv:2) vs evolved routing

### Workload 2: Bimodal Request Sizes (Size-Aware Routing Test)

**Purpose:** Test whether routing handles heterogeneous request sizes. Large requests should avoid loaded instances; small requests can tolerate higher queue depth.

**Parameters:**
```yaml
name: bimodal_sizes
duration_seconds: 60
request_rate: 2000

request_distribution:
  - weight: 0.7
    name: small_requests
    input_tokens: 64
    output_tokens: 32

  - weight: 0.3
    name: large_requests
    input_tokens: 1024
    output_tokens: 256

prefix_length: 0  # No prefix caching - isolate size effect
```

**Expected behavior:**
- Small requests: Route based on queue-depth (fast processing)
- Large requests: Route to instances with lowest KV utilization (need memory)
- Static weights: Treats all requests identically, large requests queue behind small
- Size-aware routing: 20-30% P99 reduction for large requests

**Metric focus:** Stratified TTFT by request size (small_p99, large_p99)

### Workload 3: Prefix Affinity Stress (Cache Locality Test)

**Purpose:** Maximize the prefix-affinity vs queue-depth tradeoff. Uses multiple distinct prefixes to create cache pressure, revealing whether routing balances locality and distribution.

**Parameters:**
```yaml
name: prefix_stress
duration_seconds: 90
request_rate: 3000

prefix_configuration:
  num_distinct_prefixes: 8  # More than instance count (4) - creates competition
  prefix_length: 512        # Long prefix - high cache value (H9: 95.8% TTFT reduction)

input_tokens:
  total: 768
  # 512 prefix + 256 unique per request

instance_count: 4
```

**Expected behavior:**
- With 8 prefixes across 4 instances: Some prefixes must share instances
- Naive prefix-affinity: Creates hot spots (2 prefixes per instance)
- Queue-depth only: Destroys cache locality entirely
- Optimal routing: Dynamic rebalancing when prefix concentration exceeds threshold

**Key insight:** This workload has no single optimal static configuration - requires adaptive behavior.

### Workload 4: Cold Start Recovery (Fresh Instance Test)

**Purpose:** Test routing behavior when a new instance joins mid-workload. Fresh instance has empty cache but zero load - reveals whether routing exploits fresh signals correctly.

**Parameters:**
```yaml
name: cold_start
phases:
  - name: warmup
    duration_seconds: 60
    request_rate: 2000
    instance_count: 4
    prefix_length: 256

  - name: expansion
    duration_seconds: 60
    request_rate: 2000
    instance_count: 5  # Add one fresh instance
    prefix_length: 256
    # Fresh instance has: QueueDepth=0, CacheHitRate=0, KVUtilization=0
```

**Expected behavior:**
- Immediately after expansion: Fresh instance has lowest load but zero cache value
- Prefix-affinity only: Ignores new instance (no cached prefixes)
- Queue-depth only: Floods new instance (lowest load)
- Optimal routing: Gradual ramp-up - route some requests to build cache, not all

**Metric focus:** Load distribution stddev immediately after expansion, TTFT during transition

### Workload 5: SLO-Mixed Traffic (Priority-Aware Test)

**Purpose:** Test whether routing respects SLO classes. Latency-sensitive requests need immediate service; throughput-oriented requests can tolerate queuing.

**Parameters:**
```yaml
name: slo_mixed
duration_seconds: 90
request_rate: 2500

traffic_mix:
  - weight: 0.2
    slo_class: "latency-critical"
    priority: 1.0
    input_tokens: 128
    output_tokens: 64
    # Expect: Route to lowest-load instance regardless of cache

  - weight: 0.5
    slo_class: "standard"
    priority: 0.5
    input_tokens: 256
    output_tokens: 128
    # Expect: Balance cache and load

  - weight: 0.3
    slo_class: "batch"
    priority: 0.1
    input_tokens: 512
    output_tokens: 256
    # Expect: Strong prefix-affinity, tolerate queuing

prefix_length: 128
```

**Expected behavior:**
- Latency-critical: Minimize TTFT at all costs - route to emptiest instance
- Standard: Normal weighted scoring
- Batch: Maximize throughput - route to cached instance even if queued
- Static weights: Same treatment for all SLO classes
- SLO-aware routing: 30-40% P99 reduction for latency-critical class

**Metric focus:** Per-SLO-class TTFT percentiles

## Rationale

This workload suite is designed to be **adversarial to static weighted scoring**:

1. **Workload 1** exploits the temporal blind spot - static weights cannot adapt to phase changes, creating a 15%+ gap for adaptive approaches.

2. **Workload 2** exploits the request-size blind spot - static weights treat all requests identically, but large requests have 10x higher cost sensitivity.

3. **Workload 3** creates a mathematically impossible optimization for static weights - with more prefixes than instances, any fixed prefix-affinity weight is suboptimal for some prefix subset.

4. **Workload 4** tests signal interpretation - a cold instance has contradictory signals (low load = good, zero cache = bad), requiring nuanced decision logic.

5. **Workload 5** tests multi-objective reasoning - different SLO classes have incompatible optimal strategies, requiring request-aware routing.

The suite is also designed for **staged evaluation**:
- **Stage 1 (fast):** Workload 1, first 30s only (burst phase) - 10 seconds runtime
- **Stage 2 (medium):** Workloads 1-3 at 50% duration - 90 seconds total
- **Stage 3 (full):** All 5 workloads at full duration - 6 minutes total

This staging enables quick rejection of poor mutations while thoroughly testing promising ones.

## Expected Impact

- **Differentiation:** 20-40% TTFT gap between static weights and oracle-optimal routing on these workloads
- **Generalization pressure:** Diverse scenarios prevent overfitting to single workload pattern
- **Signal utilization:** Workloads 4 and 5 specifically require using CacheHitRate and Priority signals
- **Reproducibility:** Deterministic parameters enable consistent fitness evaluation

## Risks/Limitations

1. **Workload complexity:** Five workloads with multiple phases increase evaluation time significantly
2. **BLIS configuration dependency:** Parameters assume specific instance counts and capacities
3. **Metric aggregation:** How to combine per-workload scores into single fitness value?
4. **Synthetic vs real:** These workloads are designed adversarially, may not represent production traffic

**Mitigation:**
- Use staged evaluation to manage time
- Parameterize workloads by instance count (scale with cluster)
- Fitness = weighted geometric mean of per-workload improvements
- Validate top candidates on real trace replay (ShareGPT, Alpaca)

## Reviews for Idea 3

### Review by Claude Opus (aws/claude-opus-4-6)

**Strengths:**
- Excellent adversarial design - each workload targets a specific static-weight limitation with clear expected gaps
- Workload 3 (prefix stress with 8 prefixes across 4 instances) is particularly clever - creates a mathematically impossible optimization for any fixed weight configuration
- Staged evaluation design is production-ready and addresses the evaluation time concern from Idea 1
- Per-workload expected behavior descriptions provide clear success criteria

**Concerns:**
1. **Workload 4 timing sensitivity:** The cold start scenario's behavior depends heavily on exactly when the new instance is added. If added mid-batch-formation, results may be noisy. Consider: add instance at a deterministic simulation tick (e.g., after warmup completes at tick T, add at T+1).

2. **Fitness aggregation underspecified:** "Weighted geometric mean" is mentioned but weights aren't defined. Different weight choices produce different evolutionary pressures. Propose: equal weights initially, then tune based on which workloads show most improvement headroom.

3. **Missing baseline measurements:** The expected gaps (15-25%, 20-30%, etc.) are estimates without baseline runs. Before evolution, run llm-d default on all workloads to establish actual baseline and calculate theoretical maximum improvement.

4. **Workload 5 may require instance-level priority support:** SLO-aware routing sends priority in RoutingDecision, but actual queue ordering depends on instance PriorityPolicy. If instances use FIFO, router-level priority has no effect. Verify BLIS instance configuration.

**Recommendation:** Accept with validation. Run baselines first to confirm expected gaps exist. Verify priority propagation through instance queues.

**Score:** 8.5/10

### Review by GPT-4o (Azure/gpt-4o)

**Strengths:**
- Comprehensive coverage of the four identified limitations (temporal, size, cache locality, signals)
- YAML parameter format is directly usable for BLIS configuration
- Staged evaluation (10s / 90s / 6min) provides practical runtime budget management
- Workload 2's stratified metrics (small_p99, large_p99) enable targeted optimization

**Concerns:**
1. **Request rate variability:** All workloads use fixed request rates, but real traffic has variance. Consider adding Poisson arrival process with specified mean rate to increase realism.

2. **Workload interdependence for evolution:** If fitness is a single aggregate score, the LLM doesn't know which workload it's failing on. Consider: return per-workload scores in artifacts, include in LLM context for targeted improvement hints.

3. **Duration proportions may bias evolution:** Workload 3 (90s) is 1.5x longer than others - contributes more to aggregate score. Ensure fitness aggregation normalizes by workload duration or request count.

4. **Prefix length 512 in Workload 3 may exceed BLIS cache:** H9 shows 512 prefix with 768 total input. Verify BLIS default cache size can accommodate 8 distinct 512-token prefixes without eviction during simulation.

**Recommendation:** Accept with refinements. Add arrival process variance. Return per-workload breakdown in evaluator output.

**Score:** 8/10

### Review by Gemini Flash (GCP/gemini-2.5-flash)

**Strengths:**
- The "adversarial to static weights" framing is exactly right for evolutionary discovery - creates selection pressure for adaptive behavior
- Workload 1's phase transition is the most actionable - clear before/after comparison for temporal adaptation
- Five workloads with distinct purposes prevent single-workload overfitting
- Expected behavior descriptions read like test assertions - easy to verify

**Concerns:**
1. **Six minutes for full evaluation is expensive:** With 1000+ iterations in OpenEvolve, full suite = 100+ hours. Suggest: reduce full evaluation to 3 minutes by halving durations, or use sampling (run full suite every 10th iteration).

2. **Workload 3 prefix count (8) is arbitrary:** Why 8 and not 6 or 12? The 2:1 ratio (8 prefixes : 4 instances) may not be the most discriminating. Consider: sweep prefix counts to find maximum differentiation.

3. **No throughput workload:** All workloads optimize for TTFT. Production routing also cares about requests/second. Consider adding a throughput-maximization workload where queue buildup is acceptable.

4. **Workload 5 SLO class strings must match BLIS:** "latency-critical" etc. are proposal-specific strings. Verify these match or are configurable in BLIS SLO handling.

**Recommendation:** Accept with timing optimization. Reduce full evaluation duration or implement sampling. Add throughput-focused workload variant.

**Score:** 7.5/10

---

# Executive Summary

## Key Recommendations

### 1. Implement Two-Block EVOLVE Structure (Consolidated from Idea 1)

Based on reviewer feedback, consolidate the three-level proposal into two self-contained blocks:

**Block A: Request-Aware Classification and Weight Adjustment**
- Insert before the scoring loop
- Contains: input size classification, cluster load detection, weight modulation logic
- Uses: `len(req.InputTokens)`, `state.Clock`, average `EffectiveLoad()`
- Self-contained: No dependencies on other blocks

**Block B: Score Computation with Direct Signal Bonuses**
- Replace existing EVOLVE-BLOCK (lines 137-165)
- Contains: scorer aggregation, CacheHitRate bonus, size-aware load penalties, argmax
- All adjustments additive and normalized to [0,1] (per Gemini feedback)
- Preserves observer notification pattern (per GPT-4o feedback)

This addresses the cross-block dependency concern while maintaining evolution flexibility.

### 2. Deploy Domain-Aware System Prompt with Validation Feedback

Adopt the proposed system prompt (Idea 2) with these reviewer-suggested additions:

1. **Add negative examples:** "Avoid using KVUtilization alone at high rates (200x worse per H3)"
2. **Add evaluation description:** "Code tested via: (1) go build, (2) 1000-req short sim, (3) 10000-req full sim"
3. **Add mutation granularity guidance:** "Prefer single-concept changes per mutation"
4. **Add observer preservation constraint:** "Do not modify observer notification code (lines 167-169)"

Estimated prompt length: ~900 tokens (acceptable for 8K+ context models).

### 3. Run Three-Stage Workload Evaluation with Baseline Calibration

Before evolution, run baseline measurements on all five workloads to:
1. Confirm expected gaps exist (20-40% improvement headroom)
2. Calibrate fitness weights based on actual baseline variance
3. Verify BLIS cache capacity for Workload 3 (8 x 512-token prefixes)

Staged evaluation schedule:
- **Stage 1 (10s):** Workload 1 burst phase only - quick rejection filter
- **Stage 2 (90s):** Workloads 1-3 at 50% duration - medium validation
- **Stage 3 (180s):** All 5 workloads at reduced duration - full validation

Total full evaluation: 3 minutes (reduced from 6 per Gemini feedback).

## Synthesis

The three ideas form an integrated system for routing algorithm discovery:

```
[System Prompt]           [EVOLVE-BLOCKS]            [Workloads]
       |                        |                        |
       v                        v                        v
  Domain knowledge    -->  Mutation targets  -->  Selection pressure
  + Signal freshness      + Request-aware        + Temporal adaptation
  + Unused signals        + Direct CacheHitRate  + Size differentiation
  + Constraints           + Load-adaptive        + Cache competition
```

**Idea 1 (EVOLVE-BLOCK placement)** defines WHERE the LLM can innovate.
**Idea 2 (System prompt)** guides WHAT innovations to explore.
**Idea 3 (Workloads)** creates WHY adaptive routing wins.

Together, they establish evolutionary pressure toward the target capability: routing that adapts to workload phase, request characteristics, and real-time cluster state.

## Next Steps

### Immediate (Week 1)
1. Implement two-block EVOLVE structure in `initial_program.py`
2. Create `system_prompt.txt` with the finalized prompt
3. Implement Workloads 1-3 in BLIS YAML format
4. Run baseline measurements with llm-d default weights

### Short-term (Week 2-3)
5. Configure OpenEvolve with staged evaluation
6. Run initial evolution (100 iterations) to validate pipeline
7. Analyze mutation patterns - track which block produces most improvements
8. Implement Workloads 4-5 based on initial findings

### Medium-term (Week 4-6)
9. Run full evolution (1000+ iterations)
10. Extract top-5 evolved routing algorithms
11. Validate on held-out workload (ShareGPT trace replay)
12. Compare against oracle (exhaustive weight sweep) to measure discovery quality

### Success Criteria
- At least one evolved algorithm achieves 10% TTFT reduction vs llm-d default
- Evolved algorithm uses at least one previously-unused signal (CacheHitRate or Clock)
- Algorithm generalizes to held-out workload without retuning
