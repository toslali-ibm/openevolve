# BLIS Router Weight Optimization

Evolve adaptive routing weights for BLIS multi-instance cluster using OpenEvolve.

**Goal:** Minimize end-to-end latency by making routing weights adaptive to system state.

---

## Quick Start

```bash
# 1. Build BLIS
cd examples/blis_router/inference-sim
go build -o simulation_worker main.go
cd ../../..

# 2. Test evaluator
cd examples/blis_router
python evaluator.py

# 3. Run evolution (outputs to terminal AND saves to file)
cd ../..
python openevolve-run.py \
  examples/blis_router/initial_program.py \
  examples/blis_router/evaluator.py \
  --config examples/blis_router/config.yaml \
  --iterations 100 2>&1 | tee examples/blis_router/run_output.log

# 4. Visualize evolution tree (auto-finds latest checkpoint)
python scripts/visualizer.py --path examples/blis_router/openevolve_output/
```

**Expected Duration:** ~1-2 hours for 50 iterations

---

## What Gets Evolved

**Baseline (Static Weights):**
```go
cacheScore := (1.0 - snap.KVUtilization) * 0.6  // Fixed
loadScore := (1.0 - normalizedLoad) * 0.4       // Fixed
score := cacheScore + loadScore
```

**Evolved (Adaptive Weights):**
```go
// Example: Adapt based on system state
if snap.KVUtilization < 0.3 {
    cacheWeight, loadWeight = 0.8, 0.2  // Prioritize cache
} else if normalizedLoad > 0.7 {
    cacheWeight, loadWeight = 0.3, 0.7  // Prioritize balance
}
cacheScore := (1.0 - snap.KVUtilization) * cacheWeight
loadScore := (1.0 - normalizedLoad) * loadWeight
score := cacheScore + loadScore
```

**Available State Variables:**
- `snap.KVUtilization` (float64): Cache fullness [0-1]
- `normalizedLoad` (float64): Relative load [0-1]
- `snap.QueueDepth` (int): Waiting requests
- `snap.BatchSize` (int): Running requests
- `snap.FreeKVBlocks` (int64): Available cache blocks
- `state.Clock` (int64): Simulation time (μs)

---

## Configuration

### Routing Policy (`routing_policy.yaml`)
```yaml
routing:
  policy: weighted
  cache_weight: 0.6  # Baseline
  load_weight: 0.4   # Baseline
```

### Workloads (ServeGen-based)
- **Light** (`workload_light.yaml`): 10 req/s, gamma arrivals (CV=2.0), 2 min horizon (~1200 requests)
- **Heavy** (`workload_heavy.yaml`): 50 req/s, gamma arrivals (CV=3.5), 2 min horizon (~6000 requests)
- **Mixed** (`workload_mixed.yaml`): 20 req/s, 70% batch + 30% realtime, 2 min horizon (~2400 requests)

Uses realistic Pareto-LogNormal input distributions and bursty arrival patterns.

### Evolution Settings (`config.yaml`)
```yaml
max_iterations: 50
checkpoint_interval: 5
llm:
  primary_model: Azure/gpt-4o (60%)
  secondary_model: GCP/gemini-2.5-flash (40%)
  temperature: 1.0
database:
  population_size: 50
  num_islands: 3
```

---

## Scoring

**Formula:** `score = -avg_latency`

**Interpretation:**
- Higher score (less negative) = Better
- Lower latency = Higher score

**Example:**
- Baseline: 5270ms → score = **-5270**
- 5% better: 5007ms → score = **-5007** ✓
- 10% better: 4743ms → score = **-4743** ✓✓

**Target:** 5-10% latency reduction (score > -5000)

**Averaging:** By default, workloads are weighted equally. Set `WEIGHTED_LATENCY=true` to weight by `completed_requests`.

---

## Simulation Output Format

Each workload run outputs cluster-wide metrics as JSON. The evaluator parses the `cluster` entry:

```json
{
  "instance_id": "cluster",
  "completed_requests": 1189,
  "total_input_tokens": 425847,
  "total_output_tokens": 237364,
  "e2e_mean_ms": 4523.17,
  "e2e_p99_ms": 12847.32,
  "ttft_mean_ms": 1892.45,
  "tokens_per_sec": 1978.03
}
```

**Key fields used by evaluator:**
- `e2e_mean_ms`: End-to-end latency (used for scoring)
- `completed_requests`: Request count (used for weighted averaging)

**Example run:**
```bash
cd examples/blis_router/inference-sim
./simulation_worker run \
  --model Qwen/Qwen2.5-7B-Instruct \
  --hardware H100 --tp 1 --num-instances 4 \
  --policy-config ../routing_policy.yaml \
  --workload-spec ../workload_light.yaml \
  --alpha-coeffs "4680.303204056608,0.0,0.0" \
  --beta-coeffs "7051.796874715078,19.538416565504026,25.431830886933543" \
  --log info
```

---

## Viewing Results

```bash
# Best program
cat examples/blis_router/openevolve_output/best_program.py

# Evolution log
tail -f examples/blis_router/openevolve_output/logs/openevolve_*.log

# Checkpoints (saved every 5 iterations)
ls examples/blis_router/openevolve_output/checkpoints/
```

### Resume Evolution
```bash
python openevolve-run.py \
  examples/blis_router/initial_program.py \
  examples/blis_router/evaluator.py \
  --config examples/blis_router/config.yaml \
  --checkpoint examples/blis_router/openevolve_output/checkpoints/checkpoint_25 \
  --iterations 100
```

---

## Testing Evolved Algorithm

```bash
cd examples/blis_router

# Extract best routing.go
python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'openevolve_output')
from best_program import GO_ROUTING_CODE
with open('inference-sim/sim/routing.go', 'w') as f:
    f.write(GO_ROUTING_CODE)
"

# Rebuild and test
cd inference-sim
go build -o simulation_worker main.go
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --hardware H100 --tp 1 --num-instances 4 \
  --policy-config ../routing_policy.yaml \
  --workload-spec ../workload_mixed.yaml \
  --log info
```

---

## Troubleshooting

### Build Failed
```bash
cd examples/blis_router/inference-sim
go build -o simulation_worker main.go
# Check for Go syntax errors in routing.go
```

### Evaluator Test Failed
```bash
cd examples/blis_router
python evaluator.py
# Check error type: FileWriteError, BuildError, or ParseError
```

### No Improvement After 20+ Iterations
- Check logs for LLM generation errors
- Verify baseline score ~-5270
- Increase temperature in config.yaml (e.g., 1.2)
- Check that evolved code actually changes routing logic

### View Configuration Parameters
```bash
cd examples/blis_router/inference-sim
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --hardware H100 --tp 1 --num-instances 4 \
  --workload-spec ../workload_light.yaml \
  --log info | head -5
# Shows: KV blocks, horizon, alpha/beta coefficients
```

---

## Files

| File | Purpose |
|------|---------|
| `initial_program.py` | Full routing.go with EVOLVE-BLOCK markers |
| `evaluator.py` | Builds BLIS, runs workloads, computes score |
| `config.yaml` | OpenEvolve settings |
| `routing_policy.yaml` | BLIS routing policy (cache=0.6, load=0.4) |
| `workload_light.yaml` | Light workload (10 req/s) |
| `workload_heavy.yaml` | Heavy workload (50 req/s) |
| `workload_mixed.yaml` | Mixed workload (batch + realtime) |
| `inference-sim/` | BLIS simulator (submodule) |

---

## Notes

- Score is negative: `-5270` is worse than `-5000`
- Evolution maximizes score (pushes toward 0)
- Workloads use realistic ServeGen patterns (not simple Poisson)
- Config timeout is per evaluation (~7 minutes each)
- See `BLIS_experiment1.md` for detailed explanation

**Known Issues:**
- Workload YAML `horizon` field is ignored ([inference-sim#172](https://github.com/inference-sim/inference-sim/issues/172))
- Duration controlled by CLI flag or workload generation, not YAML field
