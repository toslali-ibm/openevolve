# BLIS Experiment 1: Evolving Dynamic Router Weights

This document provides a concise guide for running BLIS and evolving its routing algorithm using OpenEvolve.

---

## Part 1: Running BLIS

### Quick Start

```bash
cd examples/blis_router/inference-sim

# Build BLIS
go build -o simulation_worker main.go

# Run with Llama-3.1-8B on H100 with TP=1
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --hardware H100 \
  --tp 1 \
  --num-instances 4 \
  --max-prompts 100 \
  --rate 10
```

### Key Parameters

- `--model`: Model name (meta-llama/llama-3.1-8b-instruct)
- `--hardware`: GPU type (H100, A100-80)
- `--tp`: Tensor parallelism degree (1, 2, 4, 8)
- `--num-instances`: Number of replicas (4 for routing experiment)
- `--max-prompts`: Total requests to simulate
- `--rate`: Requests per second

### Example: Multi-Instance with Weighted Routing

**Create routing policy config** (`routing_policy.yaml`):
```yaml
admission:
  policy: always-admit
routing:
  policy: weighted
  cache_weight: 0.6
  load_weight: 0.4
priority:
  policy: constant
scheduler: fcfs
```

**Run with policy config:**
```bash
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --hardware H100 --tp 1 \
  --num-instances 4 \
  --policy-config routing_policy.yaml \
  --max-prompts 500 --rate 20
```

**Output:**
```
STATS: throughput=18.5req/s p99_ttft=485ms p50_ttft=320ms mean_e2e=425ms
```

---

## Part 2: Understanding BLIS Router (Simple Explanation)

### What Does the Router Do?

When a request arrives, the router decides **which GPU replica** should handle it. It's like a traffic controller directing cars to different lanes.

### How Does It Work?

The router looks at two things:

1. **Cache Score**: How full is each replica's memory cache?
   - Empty cache = good (score closer to 1.0)
   - Full cache = bad (score closer to 0.0)

2. **Load Score**: How busy is each replica?
   - Light load = good (score closer to 1.0)
   - Heavy load = bad (score closer to 0.0)

### The Weighted Scoring Algorithm

```
For each replica:
  cache_score = (1 - cache_fullness) × cache_weight
  load_score  = (1 - normalized_load) × load_weight

  total_score = cache_score + load_score

Pick replica with highest total_score
```

### Current Problem

The weights are **manually set** (e.g., cache_weight=0.6, load_weight=0.4). But different workloads need different weights:
- High cache hit workload → prioritize cache (0.8, 0.2)
- Heavy traffic → prioritize load balancing (0.3, 0.7)

**We want to evolve adaptive weights that change based on system conditions.**

### Code Location

The routing logic is in `inference-sim/sim/routing.go` lines 85-140 (WeightedScoring struct).

---

## Part 3: OpenEvolve Integration Plan

### Goal

Evolve the router's weight calculation from static to adaptive based on system state.

### What We'll Evolve

**Current (Static):**
```go
cacheScore := (1.0 - snap.KVUtilization) * ws.cacheWeight
loadScore := (1.0 - normalizedLoad) * ws.loadWeight
score := cacheScore + loadScore
```

**Example Evolution (Adaptive):**
```go
// Make weights adaptive based on system conditions
var cacheWeight, loadWeight float64
if snap.KVUtilization < 0.3 {
    // Cache has room → prioritize cache affinity
    cacheWeight = 0.8
    loadWeight = 0.2
} else if normalizedLoad > 0.7 {
    // Heavy load → prioritize balancing
    cacheWeight = 0.3
    loadWeight = 0.7
} else {
    cacheWeight = 0.5
    loadWeight = 0.5
}

cacheScore := (1.0 - snap.KVUtilization) * cacheWeight
loadScore := (1.0 - normalizedLoad) * loadWeight
score := cacheScore + loadScore
```

### Integration Architecture (Simple!)

```
┌──────────────────────────────────────────────────────────┐
│ initial_program.py                                       │
│                                                          │
│ Contains entire routing.go with EVOLVE-BLOCK markers    │
│ around weight calculation (lines 122-125)               │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓ OpenEvolve iteration
┌──────────────────────────────────────────────────────────┐
│ LLM sees full file, mutates only EVOLVE-BLOCK section   │
│ Returns improved routing.go                             │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓ evaluator.py
┌──────────────────────────────────────────────────────────┐
│ 1. Take evolved routing.go                               │
│ 2. Write to inference-sim/sim/routing.go                 │
│ 3. cd inference-sim && go build                          │
│ 4. Run multiple workloads                                │
│ 5. Parse mean_e2e from each                              │
│ 6. Score = 1.0 / avg(mean_e2e)                           │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓ Result
┌──────────────────────────────────────────────────────────┐
│ If score improves → keep mutation                        │
│ Store in database for next iteration                     │
└──────────────────────────────────────────────────────────┘
```

**Key Point**: We DON'T modify BLIS source code at all. The initial_program.py contains a copy of routing.go with helpful comments added to guide evolution.

### File Structure

```
examples/blis_router/
├── initial_program.py    # Full routing.go with EVOLVE-BLOCK markers
├── evaluator.py          # Builds BLIS, runs workloads, scores results
├── config.yaml           # OpenEvolve settings (50 iterations)
├── routing_policy.yaml   # BLIS routing policy configuration
└── inference-sim/        # BLIS simulator (git submodule)
```

That's it! Only 3 files needed.

### Evolution Loop (Same as toygosys!)

```
1. LLM mutates code between EVOLVE-BLOCK markers
   ↓
2. Evaluator writes evolved routing.go to inference-sim/sim/
   ↓
3. Build: cd examples/blis_router/inference-sim && go build -o simulation_worker
   ↓
4. Run 3 workloads:
   - Light:  --rate 10 --max-prompts 100
   - Heavy:  --rate 50 --max-prompts 500
   - Mixed:  --rate 20 --max-prompts 300
   ↓
5. Parse mean_e2e from each (e.g., 420ms, 580ms, 480ms)
   ↓
6. Score = 1.0 / avg(420, 580, 480) = 1.0 / 493 = 0.00203
   ↓
7. If score improves → keep it
   ↓
8. Repeat for 50 iterations
```

### Evaluator Pseudo-Code

```python
def evaluate(program_text: str) -> dict:
    """
    Simple evaluator - just like toygosys!

    Input: Full routing.go file (with evolved EVOLVE-BLOCK)
    Output: Score based on average latency across workloads
    """

    # 1. Write evolved routing.go to BLIS
    write_file(
        "inference-sim/sim/routing.go",
        program_text  # Already the full file!
    )

    # 2. Build BLIS
    run("cd inference-sim && go build -o simulation_worker")

    # 3. Run on 3 workloads
    workloads = [
        ("light", "--rate 10 --max-prompts 100"),
        ("heavy", "--rate 50 --max-prompts 500"),
        ("mixed", "--rate 20 --max-prompts 300")
    ]

    latencies = []
    for name, flags in workloads:
        output = run(
            f"cd inference-sim && "
            f"./simulation_worker run "
            f"--model meta-llama/llama-3.1-8b-instruct "
            f"--hardware H100 --tp 1 --num-instances 4 "
            f"--policy-config ../routing_policy.yaml "
            f"{flags}"
        )

        # Parse: "STATS: ... mean_e2e=385ms ..."
        e2e_ms = extract_number(output, r"mean_e2e=([\d.]+)ms")
        latencies.append(e2e_ms)

    # 4. Score = 1 / average_latency (lower latency = higher score)
    avg_latency = sum(latencies) / len(latencies)
    score = 1.0 / avg_latency

    return {
        "combined_score": score,
        "avg_e2e_ms": avg_latency
    }
```

### Initial Program Template

```python
# examples/blis_router/initial_program.py

# Full routing.go file with EVOLVE-BLOCK markers added
# around the weight calculation (lines 122-125 in original)

GO_ROUTING_CODE = """package sim

import "fmt"

// ... full file content ...

func (ws *WeightedScoring) Route(req *Request, state *RouterState) RoutingDecision {
    snapshots := state.Snapshots

    // ... (lines 100-114: load calculation) ...

    for i, snap := range snapshots {
        normalizedLoad := 0.0
        if maxLoad > 0 {
            normalizedLoad = float64(loads[i]) / float64(maxLoad)
        }

        // EVOLVE-BLOCK-START
        // =================================================================
        // OPTIMIZATION GOAL: Minimize average end-to-end latency
        //
        // CURRENT: Static weights
        // - cacheWeight = 0.6 (favor cache affinity)
        // - loadWeight = 0.4 (favor load balancing)
        //
        // AVAILABLE STATE (you can use these):
        // - snap.KVUtilization: Cache fullness [0.0-1.0]
        //     0.0 = empty cache, 1.0 = full cache
        // - normalizedLoad: Relative load [0.0-1.0]
        //     0.0 = idle instance, 1.0 = busiest instance
        // - snap.QueueDepth: Number of waiting requests
        // - snap.BatchSize: Number of running requests
        // - snap.FreeKVBlocks: Available cache blocks
        // - state.Clock: Simulation time (for temporal patterns)
        //
        // EVOLUTION IDEAS:
        // → Adapt weights based on KVUtilization
        //   (low cache usage → prioritize cache affinity)
        // → Adapt weights based on load levels
        //   (high load → prioritize balancing)
        // → Consider queue depth for congestion awareness
        // → Detect patterns over time using state.Clock
        // =================================================================

        cacheScore := (1.0 - snap.KVUtilization) * ws.cacheWeight
        loadScore := (1.0 - normalizedLoad) * ws.loadWeight
        score := cacheScore + loadScore

        // EVOLVE-BLOCK-END

        scores[snap.ID] = score
        if score > bestScore {
            bestScore = score
            bestIdx = i
        }
    }

    // ... rest of function ...
}

// ... rest of file ...
"""
```

**Note**: The actual implementation will contain the complete routing.go file.

### Expected Evolution Path

```
Iteration 0: Static weights (0.6, 0.4)
  → Workload avg: 425ms
  → Score: 0.00235

Iteration 10: Adaptive based on cache hit rate
  → Workload avg: 395ms ✓
  → Score: 0.00253

Iteration 25: Considers both cache and load
  → Workload avg: 362ms ✓
  → Score: 0.00276

Iteration 40: Complex adaptive logic
  → Workload avg: 340ms ✓
  → Score: 0.00294
```

### Success Metrics

**Primary Goal**: Reduce average end-to-end latency by >5% across all workloads

**Secondary Goals**:
- Consistent improvement across different traffic patterns
- No single workload regresses >2%
- Routing logic remains explainable (not black box)

---

## Part 4: Implementation Steps

### Step 1: Create OpenEvolve Files

```bash
cd examples
mkdir blis_router
cd blis_router
```

Create 4 files:
- [ ] `initial_program.py` - Copy routing.go with EVOLVE-BLOCK markers
- [ ] `evaluator.py` - Build, run, parse metrics
- [ ] `config.yaml` - OpenEvolve settings
- [ ] `routing_policy.yaml` - BLIS routing policy config

### Step 2: Test BLIS Works

```bash
cd inference-sim
go build -o simulation_worker
./simulation_worker run --model meta-llama/llama-3.1-8b-instruct --hardware H100 --tp 1 --num-instances 4 --max-prompts 100
```

Should see: `STATS: ... mean_e2e=XXXms ...`

### Step 3: Test Evaluator

```bash
cd ../examples/blis_router
python evaluator.py  # Should build BLIS and return a score
```

### Step 4: Run Evolution

```bash
cd ../..  # Back to openevolve root
python openevolve-run.py \
  examples/blis_router/initial_program.py \
  examples/blis_router/evaluator.py \
  --config examples/blis_router/config.yaml \
  --iterations 50
```

### Step 5: Check Results

```bash
# View best evolved algorithm
cat examples/blis_router/openevolve_output/best_program.py

# Compare with baseline
cd examples/blis_router/inference-sim
# Copy baseline routing.go back, run test
# Copy evolved routing.go, run test
# Compare metrics
```

**No BLIS modifications needed!** We work with a copy in initial_program.py.

---

## Quick Reference: Key Files

| Component | File | Purpose |
|-----------|------|---------|
| Router Logic | `examples/blis_router/inference-sim/sim/routing.go:85-140` | WeightedScoring algorithm |
| Router State | `examples/blis_router/inference-sim/sim/router_state.go` | System state snapshot |
| CLI Entry | `examples/blis_router/inference-sim/cmd/root.go` | Command-line interface |
| Build | `examples/blis_router/inference-sim/main.go` | Compile entry point |
| Output Parser | Evaluator parses `STATS:` line | Metrics extraction |

---

## Implementation Complete! ✓

All files are ready in `examples/blis_router/`:

✓ **initial_program.py** - Full routing.go with rich EVOLVE-BLOCK comments
✓ **evaluator.py** - Builds BLIS, runs 3 workloads, computes score
✓ **config.yaml** - OpenEvolve settings (50 iterations, gemini model)
✓ **routing_policy.yaml** - BLIS routing policy (weighted, cache=0.6, load=0.4)
✓ **README.md** - Detailed usage instructions

### Run It Now

```bash
# 1. Test evaluator
cd examples/blis_router
python evaluator.py

# 2. Run evolution
cd ../..
python openevolve-run.py \
  examples/blis_router/initial_program.py \
  examples/blis_router/evaluator.py \
  --config examples/blis_router/config.yaml \
  --iterations 50
```

See `examples/blis_router/README.md` for detailed instructions and troubleshooting.
