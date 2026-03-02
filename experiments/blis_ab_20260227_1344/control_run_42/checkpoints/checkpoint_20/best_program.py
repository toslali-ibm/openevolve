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
	scores := make(map[string]float64, len(snapshots))

	// Request-aware adaptive weight modulation
	prefixBoost := 1.0
	loadBoost := 1.0

	// Sessions strongly benefit from prefix cache hits
	if req.SessionID != "" {
		prefixBoost = 4.0
		loadBoost = 0.35
	}

	// Large inputs benefit more from prefix caching
	inputLen := len(req.InputTokens)
	if inputLen > 512 {
		prefixBoost *= 2.0
	} else if inputLen > 256 {
		prefixBoost *= 1.4
	}

	// SLO-aware: realtime prioritizes load, batch tolerates queuing for cache
	if req.SLOClass == "realtime" {
		loadBoost *= 2.8
		prefixBoost *= 0.5
	} else if req.SLOClass == "batch" {
		loadBoost *= 0.35
		prefixBoost *= 1.6
	}

	// Cluster-wide load analysis
	maxLoad := 1
	minLoad := 999999
	totalLoad := 0
	for _, snap := range snapshots {
		el := snap.EffectiveLoad()
		if el > maxLoad {
			maxLoad = el
		}
		if el < minLoad {
			minLoad = el
		}
		totalLoad += el
	}
	// Load imbalance: if spread is high, load-balance matters more
	loadSpread := maxLoad - minLoad
	if loadSpread > 1 {
		loadBoost *= (1.0 + 0.25*float64(loadSpread))
	}
	// Under high cluster-wide load, strongly favor load balancing
	avgLoad := float64(totalLoad) / float64(len(snapshots))
	if avgLoad > 3.0 {
		loadBoost *= 1.5
		prefixBoost *= 0.7
	}

	// Compute base composite scores with adapted weights
	for i, scorer := range ws.scorers {
		dimScores := scorer(req, snapshots)
		w := ws.weights[i]
		if i == 0 {
			w *= prefixBoost
		} else {
			w *= loadBoost
		}
		for _, snap := range snapshots {
			s := dimScores[snap.ID]
			if s < 0 {
				s = 0
			}
			if s > 1 {
				s = 1
			}
			scores[snap.ID] += s * w
		}
	}

	// Find max FreeKVBlocks for normalization
	maxFreeKV := int64(1)
	for _, snap := range snapshots {
		if snap.FreeKVBlocks > maxFreeKV {
			maxFreeKV = snap.FreeKVBlocks
		}
	}

	// Post-scoring adjustments using instance signals
	for _, snap := range snapshots {
		// Bonus for cache hit rate (rewards warm caches)
		scores[snap.ID] += snap.CacheHitRate * 0.35 * prefixBoost

		// Memory availability bonus (smaller to reduce noise)
		if maxFreeKV > 0 {
			memBonus := float64(snap.FreeKVBlocks) / float64(maxFreeKV) * 0.12
			scores[snap.ID] += memBonus
		}

		// Tiered KV utilization penalty (tighter thresholds)
		if snap.KVUtilization > 0.90 {
			scores[snap.ID] *= 0.1
		} else if snap.KVUtilization > 0.82 {
			scores[snap.ID] *= 0.3
		} else if snap.KVUtilization > 0.72 {
			scores[snap.ID] *= 0.6
		}

		// Inverse cubic load penalty (steeper than quadratic)
		el := snap.EffectiveLoad()
		elF := float64(el)
		loadPenalty := 1.0 / (1.0 + elF*elF*0.06 + elF*elF*elF*0.005)
		scores[snap.ID] *= loadPenalty

		// Pending requests pile-on penalty
		if snap.PendingRequests > 2 {
			scores[snap.ID] *= 0.6
		} else if snap.PendingRequests > 0 {
			scores[snap.ID] *= 0.85
		}

		// Tiered queue depth penalty (lower thresholds for earlier avoidance)
		if snap.QueueDepth > 6 {
			scores[snap.ID] *= 0.08
		} else if snap.QueueDepth > 4 {
			scores[snap.ID] *= 0.25
		} else if snap.QueueDepth > 2 {
			scores[snap.ID] *= 0.5
		}
	}

	// Argmax with tie-breaking by lowest effective load
	bestScore := -1.0
	bestIdx := 0
	for i, snap := range snapshots {
		if scores[snap.ID] > bestScore {
			bestScore = scores[snap.ID]
			bestIdx = i
		} else if scores[snap.ID] == bestScore && snap.EffectiveLoad() < snapshots[bestIdx].EffectiveLoad() {
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
