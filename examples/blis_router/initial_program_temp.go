package sim

import "fmt"

// RoutingSnapshot is a lightweight view of instance state for policy decisions.
// Populated by ClusterSimulator from cluster.InstanceSnapshot when building RouterState
// (used by both AdmissionPolicy and RoutingPolicy).
// Timestamp is intentionally excluded: snapshot freshness is managed by
// CachedSnapshotProvider and is not a policy concern.
type RoutingSnapshot struct {
	ID            string
	QueueDepth    int
	BatchSize     int
	KVUtilization float64
	FreeKVBlocks  int64
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

// LeastLoaded routes requests to the instance with minimum (QueueDepth + BatchSize).
// Ties are broken by first occurrence in snapshot order (lowest index).
type LeastLoaded struct{}

// Route implements RoutingPolicy for LeastLoaded.
func (ll *LeastLoaded) Route(req *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("LeastLoaded.Route: empty snapshots")
	}

	minLoad := snapshots[0].QueueDepth + snapshots[0].BatchSize
	target := snapshots[0]

	for i := 1; i < len(snapshots); i++ {
		load := snapshots[i].QueueDepth + snapshots[i].BatchSize
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

// WeightedScoring routes requests using a weighted combination of cache affinity and load balance.
// Score = (1 - KVUtilization) * cacheWeight + (1 - normalizedLoad) * loadWeight.
// Higher scores are preferred. Ties broken by first occurrence in snapshot order.
type WeightedScoring struct {
	cacheWeight float64
	loadWeight  float64
}

// Route implements RoutingPolicy for WeightedScoring.
func (ws *WeightedScoring) Route(req *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("WeightedScoring.Route: empty snapshots")
	}

	// Compute loads and find max for normalization
	loads := make([]int, len(snapshots))
	maxLoad := 0
	for i, snap := range snapshots {
		loads[i] = snap.QueueDepth + snap.BatchSize
		if loads[i] > maxLoad {
			maxLoad = loads[i]
		}
	}

	// Compute scores
	scores := make(map[string]float64, len(snapshots))
	bestScore := -1.0
	bestIdx := 0

	for i, snap := range snapshots {
		// Normalize load to [0,1] (handle uniform load: all zero → normalizedLoad = 0)
		normalizedLoad := 0.0
		if maxLoad > 0 {
			normalizedLoad = float64(loads[i]) / float64(maxLoad)
		}

		// EVOLVE-BLOCK-START
		// =====================================================================
		// OPTIMIZATION GOAL: Minimize average end-to-end latency across workloads
		//
		// CURRENT APPROACH: Static weighted combination
		//   - cacheWeight = 0.6 (prioritize cache affinity)
		//   - loadWeight = 0.4 (prioritize load balancing)
		//
		// AVAILABLE STATE (you can use these variables):
		//
		//   snap.KVUtilization (float64, range [0.0-1.0])
		//     - How full is this instance's KV cache?
		//     - 0.0 = completely empty (lots of room for new cached tokens)
		//     - 1.0 = completely full (will need to evict to cache new tokens)
		//     - Lower values mean better cache opportunity
		//
		//   normalizedLoad (float64, range [0.0-1.0])
		//     - How loaded is this instance relative to others?
		//     - 0.0 = least loaded (idle or light queue)
		//     - 1.0 = most loaded (longest queue + biggest batch)
		//     - Lower values mean better load balance
		//
		//   snap.QueueDepth (int)
		//     - Number of requests waiting in queue
		//     - Higher = more congestion
		//
		//   snap.BatchSize (int)
		//     - Number of requests currently being processed
		//     - Higher = more busy
		//
		//   snap.FreeKVBlocks (int64)
		//     - Number of available cache blocks
		//     - Higher = more cache capacity available
		//
		//   state.Clock (int64)
		//     - Current simulation time (microseconds)
		//     - Can use for detecting temporal patterns
		//
		//   ws.cacheWeight, ws.loadWeight (float64)
		//     - Current static weights (0.6, 0.4)
		//     - These are what we're trying to make adaptive!
		//
		// SCORING COMPONENTS:
		//   cacheScore = (1.0 - snap.KVUtilization) * cacheWeight
		//     - Higher when cache has room
		//     - Scaled by cacheWeight
		//
		//   loadScore = (1.0 - normalizedLoad) * loadWeight
		//     - Higher when instance is less loaded
		//     - Scaled by loadWeight
		//
		//   Final score = cacheScore + loadScore
		//     - Higher score = better choice for routing
		//
		// EVOLUTION IDEAS TO TRY:
		//
		//   1. Adaptive weights based on cache utilization:
		//      if snap.KVUtilization < 0.3 {
		//          // Lots of cache room → prioritize cache affinity
		//          cacheWeight = 0.8
		//          loadWeight = 0.2
		//      }
		//
		//   2. Adaptive weights based on load levels:
		//      if normalizedLoad > 0.7 {
		//          // High load → prioritize balancing
		//          cacheWeight = 0.3
		//          loadWeight = 0.7
		//      }
		//
		//   3. Consider absolute queue depth:
		//      if snap.QueueDepth > 50 {
		//          // Deep queue → avoid this instance
		//          // Could adjust score or change weights
		//      }
		//
		//   4. Hybrid scoring:
		//      - Use different formulas based on conditions
		//      - Combine multiple factors
		//      - Add non-linear transformations
		//
		//   5. Temporal patterns:
		//      - Detect burst periods using state.Clock
		//      - Adjust strategy over time
		//
		// CONSTRAINTS:
		//   - Weights should generally be in [0.0, 1.0] range
		//   - Final score should be computable (no NaN, Inf)
		//   - Logic should be fast (runs for every request)
		//
		// TESTING:
		//   Your evolved algorithm will be tested on:
		//   - Light load: 10 req/s, 100 requests
		//   - Heavy load: 50 req/s, 500 requests
		//   - Mixed load: 20 req/s, 300 requests
		//
		//   Score = 1.0 / avg(mean_e2e across all workloads)
		//   Lower latency = higher score = better!
		// =====================================================================

		// Composite score
		cacheScore := (1.0 - snap.KVUtilization) * ws.cacheWeight
		loadScore := (1.0 - normalizedLoad) * ws.loadWeight
		score := cacheScore + loadScore

		// EVOLVE-BLOCK-END

		scores[snap.ID] = score

		// Select argmax; first occurrence wins on tie (strict >)
		if score > bestScore {
			bestScore = score
			bestIdx = i
		}
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

// AlwaysBusiest routes requests to the instance with maximum (QueueDepth + BatchSize).
// Pathological template for testing load imbalance detection.
// Ties broken by first occurrence in snapshot order (lowest index).
type AlwaysBusiest struct{}

// Route implements RoutingPolicy for AlwaysBusiest.
func (ab *AlwaysBusiest) Route(_ *Request, state *RouterState) RoutingDecision {
	snapshots := state.Snapshots
	if len(snapshots) == 0 {
		panic("AlwaysBusiest.Route: empty snapshots")
	}

	maxLoad := snapshots[0].QueueDepth + snapshots[0].BatchSize
	target := snapshots[0]

	for i := 1; i < len(snapshots); i++ {
		load := snapshots[i].QueueDepth + snapshots[i].BatchSize
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
// For weighted scoring, cacheWeight and loadWeight configure the composite score.
// Panics on unrecognized names.
func NewRoutingPolicy(name string, cacheWeight, loadWeight float64) RoutingPolicy {
	if !IsValidRoutingPolicy(name) {
		panic(fmt.Sprintf("unknown routing policy %q", name))
	}
	switch name {
	case "", "round-robin":
		return &RoundRobin{}
	case "least-loaded":
		return &LeastLoaded{}
	case "weighted":
		return &WeightedScoring{cacheWeight: cacheWeight, loadWeight: loadWeight}
	case "prefix-affinity":
		return &PrefixAffinity{prefixMap: make(map[string]string)}
	case "always-busiest":
		return &AlwaysBusiest{}
	default:
		panic(fmt.Sprintf("unhandled routing policy %q", name))
	}
}

