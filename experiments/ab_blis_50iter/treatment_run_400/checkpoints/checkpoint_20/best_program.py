"""
Initial Program: BLIS Router Weight Optimization

This contains the full routing.go file (synced with inference-sim v0.6.1)
with EVOLVE-BLOCK markers around the WeightedScoring logic.

Goal: Evolve the routing policy to minimize end-to-end latency across workloads.
"""

# Full routing.go file with EVOLVE-BLOCK markers (synced with inference-sim v0.6.1)
GO_ROUTING_CODE = """package sim

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

// NewRoutingSnapshot creates a RoutingSnapshot with the given instance ID.
// All numeric fields are zero-valued. Used for initial snapshot creation;
// field-by-field refresh via CachedSnapshotProvider.Snapshot() is a separate concern.
func NewRoutingSnapshot(id string) RoutingSnapshot {
	if id == "" {
		panic("NewRoutingSnapshot: id must not be empty")
	}
	return RoutingSnapshot{ID: id}
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

// NewRoutingDecision creates a RoutingDecision with the given target and reason.
// Scores is nil and Priority is 0.0 (defer to instance-level PriorityPolicy).
// This is the canonical constructor for policies that do not produce per-instance scores.
func NewRoutingDecision(target string, reason string) RoutingDecision {
	if target == "" {
		panic("NewRoutingDecision: target must not be empty")
	}
	return RoutingDecision{
		TargetInstance: target,
		Reason:         reason,
	}
}

// NewRoutingDecisionWithScores creates a RoutingDecision with target, reason, and per-instance scores.
// Priority is 0.0 (defer to instance-level PriorityPolicy).
// Used by scoring-based routing policies (e.g., WeightedScoring).
func NewRoutingDecisionWithScores(target string, reason string, scores map[string]float64) RoutingDecision {
	if target == "" {
		panic("NewRoutingDecisionWithScores: target must not be empty")
	}
	return RoutingDecision{
		TargetInstance: target,
		Reason:         reason,
		Scores:         scores,
	}
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
	return NewRoutingDecision(target.ID, fmt.Sprintf("round-robin[%d]", rr.counter-1))
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

	return NewRoutingDecision(target.ID, fmt.Sprintf("least-loaded (load=%d)", minLoad))
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

	// EVOLVE-BLOCK-START
	// HYPOTHESIS-1: Restoring proven minimal approach (96-token threshold, maxPrefix bypass, no hot-spot detection) recovers best program performance
	// MECHANISM-1: Hot-spot detection was refuted across all workloads; returning to confirmed components eliminates interference
	// EXPECT-1: cache_warmup_e2e_ms < 4280
	// HYPOTHESIS-2: Adding QueueDepth-aware tiebreaker when prefix scores are similar reduces p95 tail latency in load_spikes
	// MECHANISM-2: When multiple instances have similar prefix match (within 0.15), prefer the one with lowest QueueDepth to reduce queue buildup
	// EXPECT-2: load_spikes_e2e_ms < 3360
	// HYPOTHESIS-3: Confirmed session override and overload penalties preserve multiturn cache benefits
	// MECHANISM-3: These components were proven in best programs; no changes ensures +0.4% multiturn performance maintained
	// EXPECT-3: multiturn_e2e_ms < 162
	inputLen := len(req.InputTokens)
	w0 := ws.weights[0]
	w1 := ws.weights[1]
	if len(ws.weights) >= 2 {
		if inputLen < 96 {
			w0, w1 = 0.03, 0.97
		} else if inputLen < 256 {
			w0, w1 = 0.25, 0.75
		} else {
			w0, w1 = 0.55, 0.45
		}
		if req.SLOClass == "realtime" {
			w0 *= 0.4
			w1 *= 1.5
		} else if req.SLOClass == "batch" {
			w0 *= 1.2
			w1 *= 0.85
		}
		if req.SessionID != "" && inputLen >= 128 {
			w0, w1 = 0.87, 0.13
		}
		t := w0 + w1
		if t > 0 { w0 /= t; w1 /= t }
	}
	prefixScores := ws.scorers[0](req, snapshots)
	maxPrefix := 0.0
	for _, snap := range snapshots {
		if prefixScores[snap.ID] > maxPrefix { maxPrefix = prefixScores[snap.ID] }
	}
	// Cold cache bypass: no instance has meaningful cache
	if maxPrefix < 0.05 {
		w0, w1 = 0.0, 1.0
	}
	scores := make(map[string]float64, len(snapshots))
	for _, snap := range snapshots {
		s := prefixScores[snap.ID]
		if s < 0 { s = 0 }
		if s > 1 { s = 1 }
		scores[snap.ID] += s * w0
	}
	for i := 1; i < len(ws.scorers); i++ {
		dimScores := ws.scorers[i](req, snapshots)
		w := w1
		if i >= 2 { w = ws.weights[i] }
		for _, snap := range snapshots {
			s := dimScores[snap.ID]
			if s < 0 { s = 0 }
			if s > 1 { s = 1 }
			scores[snap.ID] += s * w
		}
	}
	minLoad, totalLoad := snapshots[0].EffectiveLoad(), 0
	for _, snap := range snapshots {
		el := snap.EffectiveLoad()
		if el < minLoad { minLoad = el }
		totalLoad += el
	}
	avgLoad := float64(totalLoad) / float64(len(snapshots))
	for _, snap := range snapshots {
		el := snap.EffectiveLoad()
		diff := float64(el - minLoad)
		if diff > 0 {
			p := 0.06 * diff
			if req.SLOClass == "realtime" { p = 0.09 * diff }
			scores[snap.ID] -= p
		}
		thresh := avgLoad + 2.0
		if thresh < 4.0 { thresh = 4.0 }
		if float64(el) > thresh {
			ex := float64(el) - thresh
			scores[snap.ID] -= 0.10 * ex * ex
		}
		if el <= minLoad+1 && minLoad < 3 {
			scores[snap.ID] += 0.04
		}
		// Session CacheHitRate tiebreaker (confirmed in best program)
		if req.SessionID != "" && snap.CacheHitRate > 0.3 {
			scores[snap.ID] += 0.02 * snap.CacheHitRate
		}
	}
	
	// QueueDepth-aware tiebreaker: when prefix scores are similar, prefer lower queue
	// This helps reduce p95 tail latency in bursty workloads without disrupting cache affinity
	if maxPrefix > 0.15 {
		for _, snap := range snapshots {
			ps := prefixScores[snap.ID]
			if ps >= maxPrefix - 0.15 {
				// This instance has competitive prefix match
				// Small penalty proportional to its queue depth relative to minimum
				queuePenalty := float64(snap.QueueDepth - minLoad) * 0.01
				if queuePenalty > 0 {
					scores[snap.ID] -= queuePenalty
				}
			}
		}
	}
	
	bestScore := -1e9
	bestIdx := 0
	for i, snap := range snapshots {
		if scores[snap.ID] > bestScore {
			bestScore = scores[snap.ID]
			bestIdx = i
		}
	}
	// EVOLVE-BLOCK-END

	// Notify observers of routing decision (stateful scorers update their state)
	for _, obs := range ws.observers {
		obs(req, snapshots[bestIdx].ID)
	}

	return NewRoutingDecisionWithScores(
		snapshots[bestIdx].ID,
		fmt.Sprintf("weighted-scoring (score=%.3f)", bestScore),
		scores,
	)
}

// PrefixAffinity routes requests with matching prefixes to the same instance (cache-aware).
// On cache miss, falls back to LeastLoaded. Maintains prefix-to-instance mapping.
// Note: prefixMap grows with unique prefix count and is not evicted. This is acceptable
// for finite-duration simulations; large-cardinality workloads will consume proportional memory.
type PrefixAffinity struct {
	prefixMap map[string]string // prefix hash → instance ID (unbounded; grows with unique prefix count)
	blockSize int64             // KV cache block size for block-aligned prefix hashing
}

// Route implements RoutingPolicy for PrefixAffinity.
// Uses block-aligned hierarchical hashing (same scheme as the weighted-scoring
// prefix-affinity scorer) so requests sharing block-aligned prefixes route together.
func (pa *PrefixAffinity) Route(req *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("PrefixAffinity.Route: empty snapshots")
	}

	// Compute block-aligned prefix hashes; use the last (longest prefix) as affinity key
	blockHashes := computeBlockHashes(int(pa.blockSize), req.InputTokens)
	var prefixHash string
	if len(blockHashes) > 0 {
		prefixHash = blockHashes[len(blockHashes)-1]
	} else {
		// Tokens shorter than one block: fall back to whole-input hash
		prefixHash = hashTokens(req.InputTokens)
	}

	// Check cache for existing mapping
	if targetID, found := pa.prefixMap[prefixHash]; found {
		// Verify target still in snapshots (instance may have been removed)
		for _, snap := range snapshots {
			if snap.ID == targetID {
				return NewRoutingDecision(targetID, "prefix-affinity (cache-hit)")
			}
		}
	}

	// Cache miss or stale entry: fallback to LeastLoaded, passing state through
	ll := &LeastLoaded{}
	decision := ll.Route(req, state)

	// Update cache with new mapping
	pa.prefixMap[prefixHash] = decision.TargetInstance

	return NewRoutingDecision(decision.TargetInstance, "prefix-affinity (cache-miss, fallback to least-loaded)")
}

// computeBlockHashes returns hierarchical block hashes without requiring a PrefixCacheIndex.
// Reuses the same hashBlock function from prefix_cache_index.go for consistency.
func computeBlockHashes(blockSize int, tokens []int) []string {
	numBlocks := len(tokens) / blockSize
	if numBlocks == 0 {
		return nil
	}
	hashes := make([]string, numBlocks)
	prevHash := ""
	for i := 0; i < numBlocks; i++ {
		start := i * blockSize
		end := start + blockSize
		hashes[i] = hashBlock(prevHash, tokens[start:end])
		prevHash = hashes[i]
	}
	return hashes
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

	return NewRoutingDecision(target.ID, fmt.Sprintf("always-busiest (load=%d)", maxLoad))
}

// NewRoutingPolicy creates a routing policy by name.
// Valid names are defined in validRoutingPolicies (bundle.go).
// Empty string defaults to round-robin.
// For weighted scoring, scorerConfigs configures the scorer pipeline.
// If scorerConfigs is nil/empty for "weighted", DefaultScorerConfigs() is used.
// Non-weighted policies ignore scorerConfigs.
// Panics on unrecognized names.
func NewRoutingPolicy(name string, scorerConfigs []ScorerConfig, blockSize int64) RoutingPolicy {
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
			scorer, obs := newScorerWithObserver(cfg.Name, int(blockSize))
			scorers[i] = scorer
			if obs != nil {
				observers = append(observers, obs)
			}
		}
		weights := normalizeScorerWeights(scorerConfigs)
		return &WeightedScoring{scorers: scorers, weights: weights, observers: observers}
	case "prefix-affinity":
		return &PrefixAffinity{prefixMap: make(map[string]string), blockSize: blockSize}
	case "always-busiest":
		return &AlwaysBusiest{}
	default:
		panic(fmt.Sprintf("unhandled routing policy %q", name))
	}
}
"""

# This will be used as the initial program for OpenEvolve
if __name__ == "__main__":
    print(GO_ROUTING_CODE)
