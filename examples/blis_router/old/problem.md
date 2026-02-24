# Research Problem: Adaptive Routing Algorithm Discovery for LLM Inference Clusters

## File References

**OpenEvolve Setup:**
- Initial program: `examples/blis_router/initial_program.py`
- Config: `examples/blis_router/config.yaml`
- Evaluator: `examples/blis_router/evaluator.py`

**BLIS Routing Source (inference-sim):**
- Main routing: `examples/blis_router/inference-sim/sim/routing.go`
- Scorers: `examples/blis_router/inference-sim/sim/routing_scorers.go`
- Prefix scorer: `examples/blis_router/inference-sim/sim/routing_prefix_scorer.go`

**Starting Policy Examples (llm-d parity):**
- EPP Precise: https://github.com/inference-sim/inference-sim/blob/add-llmd-policy-examples/examples/epp-precise-prefix.yaml
- EPP Estimate: https://github.com/inference-sim/inference-sim/blob/add-llmd-policy-examples/examples/epp-estimate-prefix.yaml

**Workloads:**
- `examples/blis_router/workload_burst_steady.yaml`
- `examples/blis_router/workload_context_growth.yaml`
- `examples/blis_router/workload_multi_tenant_chat.yaml`
- `examples/blis_router/workload_prefix_pressure.yaml`

**Hypothesis Experiments:**
- H3 Signal Freshness: `examples/blis_router/inference-sim/hypotheses/h3-signal-freshness/FINDINGS.md`
- H9 Prefix Caching: `examples/blis_router/inference-sim/hypotheses/h9-prefix-caching/FINDINGS.md`
- Prefix-Affinity: `examples/blis_router/inference-sim/hypotheses/prefix-affinity/FINDINGS.md`

---

## Problem Statement

**Discover an adaptive routing algorithm for multi-instance LLM inference clusters that surpasses static weighted scoring by exploiting workload-aware adaptation and novel decision structures.**

**Context:** BLIS (Blackbox Inference Simulator) models LLM serving with configurable routing policies. The current best-performing policy (WeightedScoring) combines prefix-affinity, queue-depth, and kv-utilization scorers with fixed weights. However:

- **CacheHitRate is used only indirectly** (via prefix-affinity scorer internals) — the main scoring loop doesn't expose it for direct optimization
- **Weights are static** regardless of workload characteristics
- **No temporal reasoning** (e.g., burst detection, trend analysis using `state.Clock`)
- **No request-aware routing** (e.g., routing large-input requests differently than small ones)

**Goal:** Use OpenEvolve to discover routing algorithms that achieve 10-20% latency reduction over the llm-d default (`prefix-affinity:3, queue-depth:2, kv-utilization:2`) across diverse workloads.

---

## Research Questions

**IMPORTANT: Each research idea iteration must address ALL THREE questions jointly.** The three questions (EVOLVE-BLOCK placement, system prompt, workload design) are interdependent — the optimal block placement depends on what the prompt guides toward, and workloads must stress-test the capabilities enabled by the block boundaries. Do NOT address one question per iteration; instead, propose a coherent solution across all three dimensions in each iteration, refining the joint solution based on feedback.

### Q1: EVOLVE-BLOCK Placement

**Where should the SINGLE EVOLVE-BLOCK be placed in routing.go to maximize discovery potential while maintaining compilability?**

Considerations:
- Current marker: only `WeightedScoring.Route()` scoring loop (lines 137-165)
- **Only ONE contiguous EVOLVE-BLOCK is supported** — choose boundaries that include all code that should evolve together
- Candidate regions to include in the single block:
  - The scoring loop (current)
  - Pre-scoring logic (request classification, adaptive weight computation)
  - Post-scoring logic (tie-breaking, adjustments based on CacheHitRate)
  - Potentially the entire `WeightedScoring.Route()` method body
- Tradeoff: broader scope = more innovation potential, but higher build failure risk
- Single file constraint: OpenEvolve takes one initial_program.py containing the Go code
- NOTE: Code from other files (routing_scorers.go, routing_prefix_scorer.go) cannot be directly evolved unless copied into the single initial_program.py file

### Q2: System Prompt Design

**What guidance in the OpenEvolve config helps LLMs discover novel routing strategies rather than minor weight tweaks?**

Considerations:
- Highlight unused/underutilized signals:
  - `snap.CacheHitRate` — available but not used in main scoring loop
  - `state.Clock` — simulation time, enables temporal reasoning
  - `req.InputTokens` length — request size awareness
  - `req.SLOClass`, `req.TenantID` — differentiated routing
- Suggest structural innovations:
  - Threshold-based decisions (e.g., skip overloaded instances)
  - Conditional logic based on cluster state
  - Adaptive weights computed from runtime metrics
  - Multi-stage routing (filter then score)
- Reference hypothesis findings as optimization targets:
  - H3: signal freshness matters at high rates
  - H9: prefix caching dramatically reduces TTFT
  - Prefix-affinity vs queue-depth tradeoffs

### Q3: Workload Design

**What fixed workload suite reveals significant performance differences between routing strategies?**

Considerations:
- **Exploit H3 (Signal Freshness):** High-rate scenarios (400+ req/s) where queue-depth's freshness advantage over kv-utilization becomes critical
- **Exploit H9 (Prefix Caching):** Prefix-heavy workloads where cache locality creates 2-10x TTFT differences
- **Exploit Prefix-Affinity Findings:** Multi-turn sessions with context accumulation where routing affects cache hit rates
- **Diversity:** Mix of bursty, steady, prefix-heavy, and multi-tenant patterns
- **Same workloads every iteration** for fair comparison of evolved algorithms

---

## Constraints

### OpenEvolve Constraints
- **Single file input:** only `initial_program.py` (containing routing.go) can be evolved
- **SINGLE EVOLVE-BLOCK only:** OpenEvolve supports exactly ONE contiguous EVOLVE-BLOCK region per file. Multiple blocks are NOT supported — the LLM prompts assume a single block, and all examples use one block. Choose the block boundaries carefully to include all code that should evolve together.
- **EVOLVE-BLOCK markers** define mutation scope — code outside markers is preserved
- **LLM sees full file** but only modifies marked regions
- **Each iteration must produce valid Go** that compiles and runs

### BLIS Architecture Constraints
- **RoutingPolicy interface:** `Route(req *Request, state *RouterState) RoutingDecision`
- **Must return valid TargetInstance** (must match a snapshot ID)
- **Scorers return** `map[string]float64` with scores in [0,1]
- **DES event ordering:** cluster events at time T process before instance events (causes signal staleness for KV metrics at high rates)

### Available State (what evolution can use)

**Request fields (`req *Request`):**
- `req.InputTokens` — full token sequence (can compute length, hash, etc.)
- `req.OutputTokens` — expected output length
- `req.Priority` — request priority value
- `req.SLOClass` — service level objective class (realtime, interactive, batch)
- `req.TenantID` — tenant identifier

**Per-instance snapshot (`snap RoutingSnapshot`):**
- `snap.ID` — instance identifier
- `snap.QueueDepth` — requests waiting in queue (fresh signal)
- `snap.BatchSize` — requests currently processing (fresh signal)
- `snap.PendingRequests` — requests routed but not yet queued (fresh signal)
- `snap.KVUtilization` — cache usage ratio [0.0-1.0] (stale at high rate)
- `snap.FreeKVBlocks` — available KV cache blocks (stale at high rate)
- `snap.CacheHitRate` — **currently unused in main scoring, available for evolution**
- `snap.EffectiveLoad()` — helper returning QueueDepth + BatchSize + PendingRequests

**Cluster state (`state *RouterState`):**
- `state.Snapshots` — all instance snapshots
- `state.Clock` — simulation time in microseconds (enables temporal reasoning)

### Evaluation Constraints
- **4 workloads** run per iteration: burst_steady, context_growth, multi_tenant_chat, prefix_pressure
- **Score formula:** `-0.5 × avg_e2e_ms - 0.5 × avg_p95_ms` (lower latency = higher score)
- **Build failures** → score of -100000 (strongly penalized)
- **Timeout:** 120 seconds per workload

---

## Success Criteria

### For the Research-Ideas Skill Output

**Each iteration must produce a JOINT solution addressing all three questions together.** The output should be a coherent OpenEvolve configuration (block placement + prompt + workloads) that work as a system.

**Q1 (EVOLVE-BLOCK Placement):** Concrete recommendation for the SINGLE block boundaries
- Exact start and end points in routing.go
- What capabilities this boundary enables (e.g., adaptive weights, new signals, structural changes)
- Why this scope balances innovation potential vs build failure risk

**Q2 (System Prompt):** A refined system prompt that:
- Is tailored to the chosen EVOLVE-BLOCK boundaries (guides LLM toward innovations that the block scope enables)
- Directs LLMs toward structural innovations (not just weight tuning)
- Highlights underutilized signals (CacheHitRate, Clock, request size)
- References hypothesis findings as optimization targets
- Suggests specific algorithmic patterns to explore (thresholds, conditionals, adaptive weights)

**Q3 (Workload Design):** A workload suite (4-6 workloads) that:
- Stress-tests the capabilities enabled by the chosen EVOLVE-BLOCK scope
- Covers scenarios where current routing is suboptimal (per hypothesis findings)
- Creates measurable differentiation between naive and sophisticated routing
- Balances prefix-heavy, load-heavy, and mixed scenarios
- Includes specific parameter choices (rate, num_requests, prefix_groups, SLO mix)

### For the OpenEvolve Experiment (ultimate goal)
- 10-20% latency improvement over llm-d default baseline
- Results reproducible across multiple seeds
- Bonus: if the algorithm discovers novel patterns (new signals, adaptive weights, structural innovations), that's valuable insight — but not required

---

## Appendix A: Full routing.go

```go
package sim

import "fmt"

// RoutingSnapshot is a lightweight view of instance state for policy decisions.
// Populated by ClusterSimulator from cluster.InstanceSnapshot when building RouterState
// (used by both AdmissionPolicy and RoutingPolicy).
// Timestamp is intentionally excluded: snapshot freshness is managed by
// CachedSnapshotProvider and is not a policy concern.
type RoutingSnapshot struct {
	ID              string
	QueueDepth      int
	BatchSize       int
	KVUtilization   float64
	FreeKVBlocks    int64
	CacheHitRate    float64
	PendingRequests int // Requests routed to this instance but not yet in queue
}

// EffectiveLoad returns the total effective load on this instance:
// QueueDepth + BatchSize + PendingRequests.
// Used by routing policies and counterfactual scoring for consistent load calculations.
func (s RoutingSnapshot) EffectiveLoad() int {
	return s.QueueDepth + s.BatchSize + s.PendingRequests
}

// RoutingDecision encapsulates the routing decision for a request.
type RoutingDecision struct {
	TargetInstance string             // Instance ID to route to (must match a snapshot ID)
	Reason         string             // Human-readable explanation
	Scores         map[string]float64 // Instance ID → composite score (nil for policies without scoring)
	// Priority is a one-shot cluster-level priority hint applied before instance injection.
	// Zero (default) means defer to instance-level PriorityPolicy entirely.
	// Non-zero value sets req.Priority for initial queue ordering only — the instance-level
	// PriorityPolicy recomputes priority each step, so this hint affects first-step scheduling
	// but does not persist. This is intentional: it allows priority to evolve over time
	// (e.g., SLOBasedPriority ages requests) while giving routing a way to influence initial placement.
	Priority float64
}

// RoutingPolicy decides which instance should handle a request.
// Implementations receive request and cluster-wide state via *RouterState.
type RoutingPolicy interface {
	Route(req *Request, state *RouterState) RoutingDecision
}

// RoundRobin routes requests in round-robin order across instances.
type RoundRobin struct {
	counter int
}

// Route implements RoutingPolicy for RoundRobin.
func (rr *RoundRobin) Route(req *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("RoundRobin.Route: empty snapshots")
	}
	target := snapshots[rr.counter%len(snapshots)]
	rr.counter++
	return RoutingDecision{
		TargetInstance: target.ID,
		Reason:         fmt.Sprintf("round-robin[%d]", rr.counter-1),
	}
}

// LeastLoaded routes requests to the instance with minimum (QueueDepth + BatchSize + PendingRequests).
// PendingRequests prevents pile-on at high request rates where multiple routing decisions
// occur at the same timestamp before instance events process (#175).
// Ties are broken by first occurrence in snapshot order (lowest index).
type LeastLoaded struct{}

// Route implements RoutingPolicy for LeastLoaded.
func (ll *LeastLoaded) Route(req *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("LeastLoaded.Route: empty snapshots")
	}

	minLoad := snapshots[0].EffectiveLoad()
	target := snapshots[0]

	for i := 1; i < len(snapshots); i++ {
		load := snapshots[i].EffectiveLoad()
		if load < minLoad {
			minLoad = load
			target = snapshots[i]
		}
	}

	return RoutingDecision{
		TargetInstance: target.ID,
		Reason:         fmt.Sprintf("least-loaded (load=%d)", minLoad),
	}
}

// observerFunc is called after each routing decision to update stateful scorer state.
// Used by scorers like prefix-affinity that track routing history.
type observerFunc func(req *Request, targetInstance string)

// WeightedScoring routes requests using a composable scorer pipeline.
//
// Each scorer evaluates all instances on a [0,1] scale. Scores are combined
// with configurable weights: composite = Σ clamp(s_i) × w_i, then argmax.
//
// Available scorers: prefix-affinity (proportional prefix match ratio),
// queue-depth (min-max normalization of EffectiveLoad),
// kv-utilization (1 - KVUtilization), load-balance (1/(1 + EffectiveLoad)).
// See sim/routing_scorers.go and sim/routing_prefix_scorer.go for implementations.
//
// Stateful scorers (prefix-affinity) register observers that update internal
// state after each routing decision. Observers are called after argmax selection.
//
// Higher scores are preferred. Ties broken by first occurrence in snapshot order.
type WeightedScoring struct {
	scorers   []scorerFunc
	weights   []float64 // normalized to sum to 1.0
	observers []observerFunc
}

// Route implements RoutingPolicy for WeightedScoring.
func (ws *WeightedScoring) Route(req *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("WeightedScoring.Route: empty snapshots")
	}

	// Compute composite scores from all scorers
	scores := make(map[string]float64, len(snapshots))
	for i, scorer := range ws.scorers {
		dimScores := scorer(req, snapshots)
		for _, snap := range snapshots {
			s := dimScores[snap.ID]
			// Clamp to [0,1] per INV-1
			if s < 0 {
				s = 0
			}
			if s > 1 {
				s = 1
			}
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

	// Notify observers of routing decision (stateful scorers update their state)
	for _, obs := range ws.observers {
		obs(req, snapshots[bestIdx].ID)
	}

	return RoutingDecision{
		TargetInstance: snapshots[bestIdx].ID,
		Reason:         fmt.Sprintf("weighted-scoring (score=%.3f)", bestScore),
		Scores:         scores,
	}
}

// PrefixAffinity routes requests with matching prefixes to the same instance (cache-aware).
// On cache miss, falls back to LeastLoaded. Maintains prefix-to-instance mapping.
// Note: prefixMap grows with unique prefix count and is not evicted. This is acceptable
// for finite-duration simulations; large-cardinality workloads will consume proportional memory.
type PrefixAffinity struct {
	prefixMap map[string]string // prefix hash → instance ID (unbounded; grows with unique prefix count)
}

// Route implements RoutingPolicy for PrefixAffinity.
func (pa *PrefixAffinity) Route(req *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("PrefixAffinity.Route: empty snapshots")
	}

	// Compute prefix hash using KVCache's hashTokens (pipe-delimited decimal strings)
	prefixHash := hashTokens(req.InputTokens)

	// Check cache for existing mapping
	if targetID, found := pa.prefixMap[prefixHash]; found {
		// Verify target still in snapshots (instance may have been removed)
		for _, snap := range snapshots {
			if snap.ID == targetID {
				return RoutingDecision{
					TargetInstance: targetID,
					Reason:         "prefix-affinity (cache-hit)",
				}
			}
		}
	}

	// Cache miss or stale entry: fallback to LeastLoaded, passing state through
	ll := &LeastLoaded{}
	decision := ll.Route(req, state)

	// Update cache with new mapping
	pa.prefixMap[prefixHash] = decision.TargetInstance

	return RoutingDecision{
		TargetInstance: decision.TargetInstance,
		Reason:         "prefix-affinity (cache-miss, fallback to least-loaded)",
	}
}

// AlwaysBusiest routes requests to the instance with maximum (QueueDepth + BatchSize + PendingRequests).
// Pathological template for testing load imbalance detection.
// Ties broken by first occurrence in snapshot order (lowest index).
type AlwaysBusiest struct{}

// Route implements RoutingPolicy for AlwaysBusiest.
func (ab *AlwaysBusiest) Route(_ *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("AlwaysBusiest.Route: empty snapshots")
	}

	maxLoad := snapshots[0].EffectiveLoad()
	target := snapshots[0]

	for i := 1; i < len(snapshots); i++ {
		load := snapshots[i].EffectiveLoad()
		if load > maxLoad {
			maxLoad = load
			target = snapshots[i]
		}
	}

	return RoutingDecision{
		TargetInstance: target.ID,
		Reason:         fmt.Sprintf("always-busiest (load=%d)", maxLoad),
	}
}

// NewRoutingPolicy creates a routing policy by name.
// Valid names are defined in validRoutingPolicies (bundle.go).
// Empty string defaults to round-robin.
// For weighted scoring, scorerConfigs configures the scorer pipeline.
// If scorerConfigs is nil/empty for "weighted", DefaultScorerConfigs() is used.
// Non-weighted policies ignore scorerConfigs.
// Panics on unrecognized names.
func NewRoutingPolicy(name string, scorerConfigs []ScorerConfig) RoutingPolicy {
	if !IsValidRoutingPolicy(name) {
		panic(fmt.Sprintf("unknown routing policy %q", name))
	}
	switch name {
	case "", "round-robin":
		return &RoundRobin{}
	case "least-loaded":
		return &LeastLoaded{}
	case "weighted":
		if len(scorerConfigs) == 0 {
			scorerConfigs = DefaultScorerConfigs()
		}
		scorers := make([]scorerFunc, len(scorerConfigs))
		var observers []observerFunc
		for i, cfg := range scorerConfigs {
			scorer, obs := newScorerWithObserver(cfg.Name, defaultBlockSize)
			scorers[i] = scorer
			if obs != nil {
				observers = append(observers, obs)
			}
		}
		weights := normalizeScorerWeights(scorerConfigs)
		return &WeightedScoring{scorers: scorers, weights: weights, observers: observers}
	case "prefix-affinity":
		return &PrefixAffinity{prefixMap: make(map[string]string)}
	case "always-busiest":
		return &AlwaysBusiest{}
	default:
		panic(fmt.Sprintf("unhandled routing policy %q", name))
	}
}
```

---

## Appendix B: Full routing_scorers.go

```go
package sim

import (
	"fmt"
	"math"
	"strconv"
	"strings"
)

// ScorerConfig describes a named scorer with a weight for weighted routing.
type ScorerConfig struct {
	Name   string  `yaml:"name"`
	Weight float64 `yaml:"weight"`
}

// scorerFunc computes per-instance scores in [0,1] for a scoring dimension.
// The req parameter provides request metadata (e.g., InputTokens for prefix matching).
// Stateless scorers may ignore it.
type scorerFunc func(req *Request, snapshots []RoutingSnapshot) map[string]float64

// defaultBlockSize is the default block size for the prefix cache index.
// Matches the most common KV cache block size. Used when constructing
// the prefix-affinity scorer without explicit configuration.
const defaultBlockSize = 16

// validScorerNames maps scorer names to validity. Unexported to prevent mutation (antipattern rule 8).
var validScorerNames = map[string]bool{
	"prefix-affinity": true,
	"queue-depth":     true,
	"kv-utilization":  true,
	"load-balance":    true,
}

// IsValidScorer returns true if name is a recognized scorer.
func IsValidScorer(name string) bool { return validScorerNames[name] }

// ValidScorerNames returns sorted valid scorer names.
func ValidScorerNames() []string { return validNamesList(validScorerNames) }

// DefaultScorerConfigs returns the default scorer configuration for weighted routing.
// Default profile: prefix-affinity:3, queue-depth:2, kv-utilization:2 (llm-d parity).
func DefaultScorerConfigs() []ScorerConfig {
	return []ScorerConfig{
		{Name: "prefix-affinity", Weight: 3.0},
		{Name: "queue-depth", Weight: 2.0},
		{Name: "kv-utilization", Weight: 2.0},
	}
}

// ParseScorerConfigs parses a comma-separated string of "name:weight" pairs.
// Returns nil for empty input. Returns error for invalid names, non-positive weights,
// NaN, Inf, or malformed input.
func ParseScorerConfigs(s string) ([]ScorerConfig, error) {
	if s == "" {
		return nil, nil
	}
	parts := strings.Split(s, ",")
	configs := make([]ScorerConfig, 0, len(parts))
	seen := make(map[string]bool, len(parts))
	for _, part := range parts {
		kv := strings.SplitN(strings.TrimSpace(part), ":", 2)
		if len(kv) != 2 {
			return nil, fmt.Errorf("invalid scorer config %q (expected name:weight)", strings.TrimSpace(part))
		}
		name := strings.TrimSpace(kv[0])
		if !IsValidScorer(name) {
			return nil, fmt.Errorf("unknown scorer %q; valid: %s", name, strings.Join(ValidScorerNames(), ", "))
		}
		if seen[name] {
			return nil, fmt.Errorf("duplicate scorer %q; each scorer may appear at most once", name)
		}
		seen[name] = true
		weight, err := strconv.ParseFloat(strings.TrimSpace(kv[1]), 64)
		if err != nil {
			return nil, fmt.Errorf("invalid weight for scorer %q: %w", name, err)
		}
		if weight <= 0 || math.IsNaN(weight) || math.IsInf(weight, 0) {
			return nil, fmt.Errorf("scorer %q weight must be a finite positive number, got %v", name, weight)
		}
		configs = append(configs, ScorerConfig{Name: name, Weight: weight})
	}
	return configs, nil
}

// normalizeScorerWeights returns weights normalized to sum to 1.0.
// Panics if total weight is zero (should be prevented by validation).
func normalizeScorerWeights(configs []ScorerConfig) []float64 {
	total := 0.0
	for _, c := range configs {
		total += c.Weight
	}
	if total <= 0 {
		panic(fmt.Sprintf("scorer weights sum to %f; must be positive", total))
	}
	weights := make([]float64, len(configs))
	for i, c := range configs {
		weights[i] = c.Weight / total
	}
	return weights
}

// newScorerWithObserver creates a scorer function and optional observer for a named scorer.
// Returns (scorer, observer) where observer is nil for stateless scorers.
// blockSize is used by stateful scorers (prefix-affinity) for block hash computation.
// Panics on unknown name (validation should catch this before reaching here).
func newScorerWithObserver(name string, blockSize int) (scorerFunc, observerFunc) {
	switch name {
	case "prefix-affinity":
		return newPrefixAffinityScorer(blockSize)
	case "queue-depth":
		return scoreQueueDepth, nil
	case "kv-utilization":
		return scoreKVUtilization, nil
	case "load-balance":
		return scoreLoadBalance, nil
	default:
		panic(fmt.Sprintf("unknown scorer %q", name))
	}
}

// scoreQueueDepth computes per-instance queue depth scores using min-max normalization.
// Lower effective load → higher score. All-equal loads → all score 1.0.
// Matches llm-d's queue-scorer semantics.
func scoreQueueDepth(_ *Request, snapshots []RoutingSnapshot) map[string]float64 {
	scores := make(map[string]float64, len(snapshots))
	minLoad, maxLoad := math.MaxInt, 0
	for _, snap := range snapshots {
		load := snap.EffectiveLoad()
		if load < minLoad {
			minLoad = load
		}
		if load > maxLoad {
			maxLoad = load
		}
	}
	for _, snap := range snapshots {
		if maxLoad == minLoad {
			scores[snap.ID] = 1.0
		} else {
			load := snap.EffectiveLoad()
			scores[snap.ID] = float64(maxLoad-load) / float64(maxLoad-minLoad)
		}
	}
	return scores
}

// scoreKVUtilization computes per-instance KV utilization scores.
// Lower utilization → higher score: score = 1 - KVUtilization.
// Matches llm-d's kv-cache-utilization-scorer semantics.
func scoreKVUtilization(_ *Request, snapshots []RoutingSnapshot) map[string]float64 {
	scores := make(map[string]float64, len(snapshots))
	for _, snap := range snapshots {
		scores[snap.ID] = 1.0 - snap.KVUtilization
	}
	return scores
}

// scoreLoadBalance computes per-instance load balance scores using inverse transform.
// Lower effective load → higher score: score = 1/(1 + effectiveLoad).
// BLIS-native formula preserving absolute load differences (alternative to min-max).
func scoreLoadBalance(_ *Request, snapshots []RoutingSnapshot) map[string]float64 {
	scores := make(map[string]float64, len(snapshots))
	for _, snap := range snapshots {
		scores[snap.ID] = 1.0 / (1.0 + float64(snap.EffectiveLoad()))
	}
	return scores
}
```

---

## Appendix C: Full routing_prefix_scorer.go

```go
package sim

// defaultLRUCapacity is the default number of block hashes tracked per instance
// in the router-side prefix cache. 10,000 blocks × 16 tokens/block = 160K tokens.
const defaultLRUCapacity = 10000

// newPrefixAffinityScorer creates a prefix-affinity scorer and its observer.
// The scorer returns per-instance scores based on how much of the request's
// prefix each instance has cached. The observer updates the cache index
// after each routing decision.
//
// Both the scorer and observer share the same PrefixCacheIndex via closure.
// The blockSize should match the simulation's KV cache block size.
func newPrefixAffinityScorer(blockSize int) (scorerFunc, observerFunc) {
	idx := NewPrefixCacheIndex(blockSize, defaultLRUCapacity)

	scorer := func(req *Request, snapshots []RoutingSnapshot) map[string]float64 {
		scores := make(map[string]float64, len(snapshots))
		if req == nil {
			return scores
		}
		hashes := idx.ComputeBlockHashes(req.InputTokens)
		totalBlocks := len(hashes)
		for _, snap := range snapshots {
			if totalBlocks == 0 {
				scores[snap.ID] = 0.0
			} else {
				matched := idx.MatchLength(hashes, snap.ID)
				scores[snap.ID] = float64(matched) / float64(totalBlocks)
			}
		}
		return scores
	}

	observer := func(req *Request, targetInstance string) {
		if req == nil {
			return
		}
		hashes := idx.ComputeBlockHashes(req.InputTokens)
		idx.RecordBlocks(hashes, targetInstance)
	}

	return scorer, observer
}
```

---

## Appendix D: Starting Policy YAMLs

### EPP Precise Prefix (prefix-affinity:2, kv-utilization:1, queue-depth:1)

```yaml
admission:
  policy: always-admit

routing:
  policy: weighted
  scorers:
    - name: prefix-affinity
      weight: 2.0
    - name: kv-utilization
      weight: 1.0
    - name: queue-depth
      weight: 1.0

priority:
  policy: constant

scheduler: fcfs
```

### EPP Estimate Prefix (prefix-affinity:1, load-balance:1)

```yaml
admission:
  policy: always-admit

routing:
  policy: weighted
  scorers:
    - name: prefix-affinity
      weight: 1.0
    - name: load-balance
      weight: 1.0

priority:
  policy: constant

scheduler: fcfs
```

---

## Appendix E: Hypothesis Findings Summary

### H3: Signal Freshness (queue-depth vs kv-utilization)

**Status:** Confirmed | **Key Finding:** At high request rates, queue-depth distributes 200x more evenly than kv-utilization.

| Scorer | TTFT Mean | TTFT P99 | Dist StdDev |
|--------|-----------|----------|-------------|
| queue-depth | 1290-1319ms | 2532-2604ms | 0.7-1.0 |
| kv-utilization | 2259-3644ms | 7870-12285ms | 142-226 |

**Root Cause:** DES event ordering causes KV utilization to be stale at high rates. Queue-depth uses `PendingRequests` which updates synchronously at routing time.

**Implication:** Always include queue-depth in weighted routing. Never use kv-utilization as the sole scorer at high rates.

### H9: Prefix Caching Effectiveness

**Status:** Confirmed | **Key Finding:** 95.8% TTFT reduction at maximum prefix length.

| Prefix Length | TTFT Mean (ms) | Cache Hit Rate | TTFT Δ vs Baseline |
|:---:|:---:|:---:|:---:|
| 0 | 728.3 | 0.0000 | baseline |
| 64 | 571.5 | 0.0754 | -21.5% |
| 128 | 429.2 | 0.1511 | -41.1% |
| 256 | 184.6 | 0.3032 | -74.7% |
| 512 | 30.2 | 0.6071 | -95.8% |

**Implication:** Workloads with shared system prompts benefit massively from prefix caching. Use prefix-affinity routing at cluster scale.

### Prefix-Affinity vs Queue-Depth

**Status:** Confirmed | **Key Finding:** Prefix-affinity is 2.45x better than queue-depth for multi-turn chat (28.2ms vs 69.0ms TTFT).

| Configuration | TTFT Mean | Cache Hit Rate |
|--------------|-----------|----------------|
| prefix-affinity:3,qd:2 | 28.2ms | 55.7% |
| queue-depth:1 | 69.0ms | 23.3% |
| round-robin | 21.8ms | 62.9% |

**Root Cause:** Queue-depth actively destroys cache locality by routing sessions away from their cached instance (load balancing vs cache affinity tradeoff).

**High Load Crossover:** At rate=5000, prefix-affinity wins decisively (205ms vs 892ms) because reduced prefill outweighs concentration overhead.

**Implication:** Multi-turn chat should always use prefix-affinity. Queue-depth alone is harmful for session-based workloads.

---

## Appendix F: Current Workloads

### burst_steady (250 req/s, 6000 requests)

**Pattern:** Bursty batch jobs competing with steady realtime traffic.

- Realtime chat (30%): Poisson arrival, streaming, 100-120 token inputs
- Batch storms (50%): Gamma CV=5.0 (extreme bursts), Pareto-lognormal inputs (200-1500 tokens)
- Interactive API (20%): Gamma CV=2.0, 150 token inputs

**Tests:** SLO conflict handling, burst absorption, load distribution under extreme burstiness.

### context_growth (150 req/s, 3000 requests)

**Pattern:** Multi-turn conversations that build KV pressure over time.

- Long coding sessions (40%): Up to 8 rounds, context accumulation, 200-1000 token inputs
- Document Q&A (30%): Up to 5 rounds, context accumulation, 500-2000 token inputs
- Quick queries (30%): No multi-turn, bursty (CV=4.0), 80 token inputs

**Tests:** Context accumulation handling, KV cache pressure, multi-turn routing consistency.

### multi_tenant_chat (200 req/s, 5000 requests)

**Pattern:** Production chat with many tenants sharing system prompts.

- Tenant A Support (15%): Realtime, streaming, 4-round multi-turn
- Tenant A Analytics (10%): Batch, bursty, shared prefix with Support
- Tenant B Coding (20%): Interactive, 3-round multi-turn, different prefix
- Tenant C Docs (25%): Batch, very bursty (CV=4.0), large inputs
- Shared API (30%): Interactive, global shared prompt

**Tests:** Multi-tenant isolation, prefix sharing across tenants, SLO differentiation.

### prefix_pressure (400 req/s, 8000 requests)

**Pattern:** 8 prefix groups vs 4 instances — forces routing tradeoffs.

- 8 equal client groups (12.5% each): Different prefix groups
- Mix of SLO classes: interactive (groups 1-4), batch (groups 5-6), realtime (groups 7-8)
- Input sizes: 400-600 tokens (interactive/batch), 200 tokens (realtime)
- Burstiness: Gamma CV=2.5-3.0

**Tests:** Prefix-to-instance assignment with more prefixes than instances, load/cache tradeoff under high rate.
