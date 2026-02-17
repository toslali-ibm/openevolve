# BLIS Router Weight Optimization

Evolve adaptive routing weights for BLIS multi-instance cluster using OpenEvolve.

**Goal:** Minimize end-to-end latency by making routing weights adaptive to system state.

---

## Quick Start

### Prerequisites

```bash
# Check Go is installed (1.21+)
go version

# Check Python is installed (3.10+)
python --version

# Make sure you're in openevolve directory
pwd  # Should show .../openevolve
```

### Step 1: Build BLIS

```bash
cd inference-sim
go build -o simulation_worker main.go
cd ../../..  # Back to openevolve root
```

### Step 2: Test Evaluator

```bash
cd examples/blis_router
python evaluator.py
```

**Expected output (~30 seconds):**
```
✓ Build successful
✓ light: e2e_mean_ms=4961.57ms
✓ heavy: e2e_mean_ms=5337.12ms
✓ mixed: e2e_mean_ms=5513.13ms

Score: -5270.60
Avg E2E: 5270.60ms
Success rate: 100%
```

### Step 3: Run Evolution

```bash
# Back to openevolve root and run openevolve pipeline
cd ../..  
python openevolve-run.py \
  examples/blis_router/initial_program.py \
  examples/blis_router/evaluator.py \
  --config examples/blis_router/config.yaml \
  --iterations 50
```

**Duration:** 1-2 hours

---

## Routing Policy Configuration

BLIS routing is configured via `routing_policy.yaml`:

```yaml
admission:
  policy: always-admit

routing:
  policy: weighted
  cache_weight: 0.6  # Prioritize cache affinity
  load_weight: 0.4   # Prioritize load balancing

priority:
  policy: constant

scheduler: fcfs
```

**Usage:**
```bash
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --hardware H100 --tp 1 --num-instances 4 \
  --policy-config routing_policy.yaml \
  --max-prompts 100
```

---

## What Gets Evolved

The routing weight calculation in `WeightedScoring.Route()`:

**Before (Static):**
```go
cacheScore := (1.0 - snap.KVUtilization) * ws.cacheWeight  // Fixed 0.6
loadScore := (1.0 - normalizedLoad) * ws.loadWeight         // Fixed 0.4
score := cacheScore + loadScore
```

**After (Adaptive - Example):**
```go
// Evolved: Adapt weights based on system state
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

---

## Available State

The LLM can use these variables to make routing adaptive:

| Variable | Type | Description |
|----------|------|-------------|
| `snap.KVUtilization` | float64 [0-1] | Cache fullness (0=empty, 1=full) |
| `normalizedLoad` | float64 [0-1] | Relative load (0=idle, 1=busiest) |
| `snap.QueueDepth` | int | Waiting requests |
| `snap.BatchSize` | int | Running requests |
| `snap.FreeKVBlocks` | int64 | Available cache blocks |
| `state.Clock` | int64 | Simulation time (μs) |

---

## Scoring

**Metric:** Average end-to-end latency across 3 workloads

**Formula:** `score = -avg_latency` (negative because we're minimizing)

**Example:**
- Baseline: 5270ms → score = **-5270**
- 5% better: 5007ms → score = **-5007** (higher/better!)
- 10% better: 4743ms → score = **-4743** (even better!)

**Failed runs:** score = -100000 (very bad)

**Workloads:**
- Light: 10 req/s, 100 requests
- Heavy: 50 req/s, 500 requests
- Mixed: 20 req/s, 300 requests

---

## Expected Results

### Baseline Performance

```
Score:           -5270.60
Average latency: 5270.60ms

Light workload:  4961.57ms
Heavy workload:  5337.12ms
Mixed workload:  5513.13ms
```

### Target (5-10% improvement)

```
Score:           -4750 to -5000
Average latency: 4750-5000ms

Improvements across all workloads
```

### Evolution Progress

**Typical pattern:**
```
Iteration 0:  Score -5270 (baseline)
Iteration 10: Score -5150 (2% improvement)
Iteration 20: Score -5050 (4% improvement)
Iteration 30: Score -4920 (7% improvement)
Iteration 50: Score -4850 (8% improvement) ✓
```

---

## Viewing Results

### Best Program

```bash
# View best evolved algorithm
cat examples/blis_router/openevolve_output/best_program.py
```

### Evolution Log

```bash
# See iteration-by-iteration progress
tail -100 examples/blis_router/openevolve_output/evolution.log
```

### Checkpoints

```bash
# List saved checkpoints (every 10 iterations)
ls examples/blis_router/openevolve_output/checkpoints/
```

---

## Resuming Evolution

If evolution stops or you want to continue:

```bash
python openevolve-run.py \
  examples/blis_router/initial_program.py \
  examples/blis_router/evaluator.py \
  --config examples/blis_router/config.yaml \
  --checkpoint examples/blis_router/openevolve_output/checkpoints/checkpoint_40 \
  --iterations 100  # Continue to 100 total iterations
```

---

## Testing Best Algorithm

After evolution completes, test the best algorithm:

```bash
cd examples/blis_router

# Extract best evolved routing.go
python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'openevolve_output')
from best_program import GO_ROUTING_CODE

with open('inference-sim/sim/routing.go', 'w') as f:
    f.write(GO_ROUTING_CODE)
print('✓ Wrote best routing.go to BLIS')
"

# Rebuild BLIS
cd inference-sim
go build -o simulation_worker main.go

# Test it with routing policy
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --hardware H100 --tp 1 --num-instances 4 \
  --policy-config ../routing_policy.yaml \
  --max-prompts 500 --rate 20
```

Compare results with baseline!

---

## Configuration

### Main Settings (`config.yaml`)

```yaml
max_iterations: 50              # Total iterations
checkpoint_interval: 10         # Save every 10 iterations

llm:
  primary_model: aws/claude-opus-4-5    # Main model (60%)
  secondary_model: GCP/gemini-2.5-flash # Secondary (40%)
  temperature: 0.7              # Creativity level
  max_tokens: 16000             # Response size

database:
  population_size: 50           # Programs in population
  num_islands: 3                # Islands for diversity

evaluator:
  timeout: 300                  # 5 min per evaluation
  parallel_evaluations: 1       # Sequential (Go build)
```

### Adjusting Settings

**More iterations:**
```yaml
max_iterations: 100  # For more thorough exploration
```

**More creative:**
```yaml
temperature: 0.9  # Higher = more diverse mutations
```

**Faster evaluation:**
```yaml
# Reduce workload sizes in evaluator.py:
("light", "--rate 10 --max-prompts 50"),   # Was 100
("heavy", "--rate 50 --max-prompts 250"),  # Was 500
```

---

## Troubleshooting

### Build Failed

```bash
# Test BLIS build manually
cd examples/blis_router/inference-sim
go build -o simulation_worker main.go

# Should complete with no errors
# If errors, check Go syntax in routing.go
```

### All Workloads Failed

```bash
# Test BLIS simulation manually
cd examples/blis_router/inference-sim
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --hardware H100 --tp 1 --num-instances 4 \
  --policy-config ../routing_policy.yaml \
  --max-prompts 10

# Should output JSON metrics
```

### Evaluator Test Fails

Check the error message:
- **FileWriteError**: Permission issue, check file paths
- **BuildError**: Go syntax error in evolved code
- **ParseError**: BLIS output format changed

### No Improvement After Many Iterations

**This is normal early on!** Evolution explores the space first.

**By iteration 20-30** you should see improvements. If not:
- Check evolution.log for errors
- Verify baseline score is reasonable (~-5270)
- Ensure LLM is generating valid mutations
- Try adjusting temperature (0.8-0.9 for more creativity)

### API Timeouts

Increase timeout in config.yaml:
```yaml
llm:
  timeout: 180  # 3 minutes instead of 2
```

### "Score is negative, is this right?"

**Yes!** Score = -latency (lower latency = higher/better score)
- -5270 is worse than -4500 ✓
- Evolution maximizes score (pushes toward 0 from negative)

---

## Files in This Directory

| File | Purpose |
|------|---------|
| `initial_program.py` | Full routing.go with EVOLVE-BLOCK markers and guidance comments |
| `evaluator.py` | Builds BLIS, runs 3 workloads, computes score |
| `config.yaml` | OpenEvolve settings (models, iterations, parameters) |
| `routing_policy.yaml` | BLIS routing policy configuration (cache/load weights) |
| `inference-sim/` | BLIS simulator (git submodule) |
| `README.md` | This file |

---

## Next Steps

1. **Run evolution** (Steps 1-3 above)
2. **Analyze results** - What strategies did the LLM discover?
3. **Validate on hold-out workloads** - Test on different traffic patterns
4. **Compare with baselines** - Static weights, round-robin, least-loaded
5. **Try other experiments** - Admission control, priority scheduling, autoscaling

See `BLIS_integration.md` for more experiments (Experiments 2-4).

---

## Questions?

- Check `BLIS_experiment1.md` for detailed explanation
- Review `config.yaml` for all parameters and comments
- Look at `examples/function_minimization` for another example
- Read OpenEvolve `CLAUDE.md` for system overview
