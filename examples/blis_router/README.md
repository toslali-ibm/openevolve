# BLIS Router Optimization

Evolve adaptive routing logic for a BLIS multi-instance LLM inference cluster using OpenEvolve.

**Goal:** Minimize end-to-end latency by making the `WeightedScoring.Route()` EVOLVE-BLOCK adaptive to request properties and system state, beating the static-weight baseline.

---

## Quick Start

```bash
# 1. Clean cached data (required when switching models or workloads)
rm -f examples/blis_router/baseline_metrics.json examples/blis_router/hypothesis_ledger.json

# 2. Build BLIS
cd examples/blis_router/inference-sim
go build -o simulation_worker main.go
cd ../../..

# 3. Test evaluator (also computes + caches baseline metrics on first run)
cd examples/blis_router
python evaluator.py

# 4. Run evolution
cd ../..
python openevolve-run.py \
  examples/blis_router/initial_program.py \
  examples/blis_router/evaluator.py \
  --config examples/blis_router/config.yaml \
  --iterations 100 2>&1 | tee examples/blis_router/run_output.log

# 5. Visualize evolution tree
python scripts/visualizer.py --path examples/blis_router/openevolve_output/
```

**Expected Duration:** ~1-2 hours for 50 iterations

---

## What Gets Evolved

The EVOLVE-BLOCK in `initial_program.py` contains the `WeightedScoring.Route()` logic. The LLM modifies this block to improve routing decisions.

**Baseline (Static Weights):**
```go
// Two scorers (prefix-affinity + load-balance) with fixed equal weights [1.0, 1.0]
// Weights NEVER change based on request or system state
for i, scorer := range ws.scorers {
    dimScores := scorer(req, snapshots)
    for _, snap := range snapshots {
        scores[snap.ID] += dimScores[snap.ID] * ws.weights[i]
    }
}
bestIdx := argmax(scores)
```

**Evolved (Adaptive, example):**
```go
// HYPOTHESIS-1: Cache affinity boost helps large-prefix workloads
// MECHANISM-1: Requests with >400 tokens have more KV cache blocks to reuse
// EXPECT-1: prefix_caching_e2e_ms < 235

// ... base scoring loop ...

// Post-scoring: boost cache-warm instances for large requests
if len(req.InputTokens) > 400 {
    for _, snap := range snapshots {
        scores[snap.ID] *= (1.0 + snap.CacheHitRate * 0.5)
    }
}
// Penalize loaded instances for realtime SLO
if req.SLOClass == "realtime" && snap.QueueDepth > 5 {
    scores[snap.ID] *= 0.8
}
```

**Available Signals:**

From request (`req`):
- `len(req.InputTokens)`: request size
- `req.SLOClass`: `"realtime"`, `"interactive"`, or `"batch"`
- `req.SessionID`: non-empty for multi-turn sessions

From instance snapshots (`snap`):
- `snap.CacheHitRate`: historical cache performance (0.0-1.0)
- `snap.QueueDepth`, `snap.BatchSize`, `snap.PendingRequests`: load components
- `snap.EffectiveLoad()`: total load (Queue + Batch + Pending)
- `snap.KVUtilization`: memory pressure (stale at high rates)
- `snap.FreeKVBlocks`: available memory blocks

---

## Hypothesis-Driven Evolution

The LLM writes testable hypotheses alongside code mutations. Each iteration:

1. LLM includes structured `// HYPOTHESIS-N` / `// MECHANISM-N` / `// EXPECT-N` comments in the EVOLVE-BLOCK
2. Evaluator parses hypotheses, runs 3 workloads, tests predictions against a cached baseline
3. Results are appended to a persistent hypothesis ledger
4. A knowledge base summary (confirmed/refuted strategies) is returned as an artifact
5. Next iteration: the LLM sees what worked and what didn't

**Hypothesis persistence:**
- `hypothesis_ledger.json` - cumulative file on disk, grows across all iterations
- OpenEvolve artifact database - `hypothesis_results` and `hypothesis_knowledge_base` stored per program, fed back to the LLM via the artifact pipeline

**Per-iteration logging shows:**
- Diff vs initial program
- Per-workload results: `signal_freshness: e2e_mean=X.XXms, p95=X.XXms`
- Evaluation summary with all workloads + combined score
- Parsed hypotheses: `H1: <claim> (EXPECT: metric < threshold)`
- Hypothesis verdicts: CONFIRMED/REFUTED with deltas vs baseline

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BLIS_MODEL` | `meta-llama/llama-3.1-8b-instruct` | Simulation model. Set to `Qwen/Qwen2.5-7B-Instruct` for Qwen (adds blackbox coefficients automatically) |
| `WEIGHTED_LATENCY` | `false` | Set `true` to weight workloads by `completed_requests` instead of equal weighting |

```bash
# Use Qwen model
BLIS_MODEL="Qwen/Qwen2.5-7B-Instruct" python openevolve-run.py ...

# Use llama (default)
python openevolve-run.py ...
```

### Routing Policy (`routing_policy.yaml`)
```yaml
routing:
  policy: weighted
  scorers:
    - name: prefix-affinity
      weight: 1.0
    - name: load-balance
      weight: 1.0
```

### Workloads (3 routing-sensitive v2)

All validated: sabotaged (always-instance-0) is 242-315% worse than baseline.

| Workload | File | Purpose | Rate | Duration |
|----------|------|---------|------|----------|
| Cache Warmup | `workload_v2_cache_warmup.yaml` | Prefix cache exploitation after warmup | 1000 req/s | 5s |
| Load Spikes | `workload_v2_load_spikes.yaml` | Adaptation to bursty load imbalances | 1500 req/s | 4s |
| Multi-turn | `workload_v2_multiturn.yaml` | Session affinity for multi-turn conversations | 800 req/s | 6.25s |

### Evolution Settings (`config.yaml`)
```yaml
max_iterations: 100
checkpoint_interval: 5
llm:
  primary_model: GCP/gemini-2.5-flash (60%)
  secondary_model: gcp/gemini-2.5-pro (40%)
  temperature: 1.0
database:
  population_size: 100
  num_islands: 3
```

---

## Scoring

**Formula:** `score = -0.5 * avg_e2e_ms - 0.5 * avg_p95_ms`

**Interpretation:**
- Higher score (less negative) = Better
- Lower mean + tail latency = Higher score
- Averaged equally across all 3 workloads

**Averaging:** By default, workloads are weighted equally. Set `WEIGHTED_LATENCY=true` to weight by `completed_requests`.

---

## Simulation Output Format

Each workload run outputs cluster-wide metrics as JSON. The evaluator parses the `cluster` entry:

```json
{
  "instance_id": "cluster",
  "completed_requests": 1189,
  "e2e_mean_ms": 4523.17,
  "e2e_p95_ms": 8234.56,
  "ttft_mean_ms": 1892.45,
  "tokens_per_sec": 1978.03
}
```

**Key fields used by evaluator:**
- `e2e_mean_ms`: Mean end-to-end latency (used for scoring)
- `e2e_p95_ms`: P95 tail latency (used for scoring)
- `completed_requests`: Request count (used for weighted averaging)

---

## Viewing Results

```bash
# Best program
cat examples/blis_router/openevolve_output/best_program.py

# Evolution log
tail -f examples/blis_router/openevolve_output/logs/openevolve_*.log

# Hypothesis ledger
cat examples/blis_router/hypothesis_ledger.json

# Baseline metrics
cat examples/blis_router/baseline_metrics.json

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
  --num-instances 4 \
  --policy-config ../routing_policy.yaml \
  --workload-spec ../workload_v2_load_spikes.yaml \
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

### Stale Baseline
If you switch models or change workloads, delete the cached baseline:
```bash
rm -f examples/blis_router/baseline_metrics.json examples/blis_router/hypothesis_ledger.json
```

### No Improvement After 20+ Iterations
- Check logs for LLM generation errors
- Check hypothesis knowledge base for patterns (are all strategies REFUTED?)
- Increase temperature in config.yaml (e.g., 1.2)
- Check that evolved code actually changes routing logic

---

## Files

| File | Purpose |
|------|---------|
| `initial_program.py` | Full routing.go with EVOLVE-BLOCK markers |
| `evaluator.py` | Builds BLIS, runs workloads, tests hypotheses, computes score |
| `hypothesis.py` | Hypothesis parsing, testing, ledger, and knowledge base summary |
| `config.yaml` | OpenEvolve settings (LLM, evolution, database) |
| `routing_policy.yaml` | BLIS routing policy (prefix-affinity + load-balance, equal weights) |
| `workload_v2_cache_warmup.yaml` | Cache warmup & exploitation (rate=1000, 5s) |
| `workload_v2_load_spikes.yaml` | Bursty load with SLO tension (rate=1500, 4s) |
| `workload_v2_multiturn.yaml` | Multi-turn sessions with context growth (rate=800, 6.25s) |
| `validate_workloads.py` | Routing sensitivity validation script (4 configs x N workloads) |
| `baseline_metrics.json` | Auto-generated: cached baseline metrics from initial program |
| `hypothesis_ledger.json` | Auto-generated: cumulative hypothesis results across iterations |
| `inference-sim/` | BLIS simulator (submodule) |

---

## Notes

- Score is negative: `-300` is better than `-500`
- Evolution maximizes score (pushes toward 0)
- First evaluation auto-computes baseline (adds ~30s one-time cost)
- Hypothesis ledger persists across runs; delete to start fresh
- Workloads use realistic ServeGen patterns (not simple Poisson)
