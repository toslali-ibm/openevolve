# BLIS + OpenEvolve Integration Plan

## Overview

Use OpenEvolve to automatically optimize BLIS (vLLM simulator) router module by evolving dynamic weighting strategies.

**Problem**: Router currently requires manual weight tuning for combining scores
**Solution**: Evolve adaptive weighting logic that automatically adjusts based on system state

---

## Experiment 1: Dynamic Router Weighting

### Problem

Router combines two scores (KV cache hit probability + load awareness) using **manual weights** (e.g., 0.6 + 0.4). Users must tune these, which is suboptimal across workloads.

### Solution: Evolve Dynamic Weighting

```go
// router.go
func (r *Router) SelectServer(request Request, state SystemState) Server {
    kvScore := r.kvCacheScorer.Score(request)
    loadScore := r.loadScorer.Score(request)

    // EVOLVE-BLOCK-START
    // Baseline: Static weights
    kvWeight := 0.6
    loadWeight := 0.4

    // Evolution directions:
    // → Adapt based on state.CacheHitRate (high hit rate → prioritize cache)
    // → Adapt based on state.AverageLoad (high load → balance more)
    // → Adapt based on request.InputLen (long prompts → different strategy)
    // → Time-of-day patterns, workload-specific heuristics
    // EVOLVE-BLOCK-END

    finalScore := kvWeight * kvScore + loadWeight * loadScore
    return selectBestServer(finalScore)
}
```

### Objective & Metrics

**Goal**: Minimize average e2e latency
**Input**: kvScore, loadScore, system state (cache hit rate, load), request characteristics
**Output**: Dynamic kvWeight, loadWeight
**Score**: `1.0 / avg_e2e_latency` (lower latency = higher score)

---

## Contract: BLIS Requirements

### 1. Runnable Mode

BLIS must support running from command line with trace file:

```bash
./blis --trace traces/workload1.json --config llm_config.yaml
```

**Output format** (stdout):
```
STATS: e2e=125.3ms ttft=45.2ms itl=8.1ms throughput=150req/s
```

### 2. Router Module Structure

```go
// router.go - Must have this signature
package router

type SystemState struct {
    CacheHitRate float64
    AverageLoad  float64
    NumServers   int
}

type Request struct {
    InputLen  int
    OutputLen int
}

// EVOLVE-BLOCK-START and EVOLVE-BLOCK-END markers
func ComputeWeights(kvScore, loadScore float64, state SystemState, req Request) (float64, float64) {
    // EVOLVE-BLOCK-START
    kvWeight := 0.6
    loadWeight := 0.4
    // EVOLVE-BLOCK-END

    return kvWeight, loadWeight
}
```

### 3. Trace Files

Provide sample traces for evaluation:

```
traces/
├── light_load.json      # Low traffic, test cache sensitivity
├── heavy_load.json      # High traffic, test load balancing
└── mixed_workload.json  # Realistic mix
```

### 4. Build System

```bash
# Must support clean rebuild
cd blis
go build -o blis
```

---

## OpenEvolve Pipeline

### File Structure

```
examples/blis_router/
├── initial_program.py    # Initial router weighting logic
├── evaluator.py          # Runs BLIS, parses stats
├── config.yaml           # Evolution parameters
└── traces/               # Workload traces (symlink to BLIS)
```

### Pipeline Flow

```
┌─────────────────────────────────────────────────────┐
│ 1. INITIAL STATE                                    │
│                                                     │
│ router.go has manual weights:                      │
│   kvWeight := 0.6                                   │
│   loadWeight := 0.4                                 │
│                                                     │
│ Performance: e2e=125.3ms                           │
└─────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────┐
│ 2. OPENEVOLVE ITERATION                             │
│                                                     │
│ LLM suggests improvement:                           │
│   // Adapt based on cache hit rate                 │
│   if state.CacheHitRate > 0.8 {                    │
│       kvWeight = 0.8  // Prioritize cache          │
│       loadWeight = 0.2                              │
│   } else {                                          │
│       kvWeight = 0.3  // Balance load              │
│       loadWeight = 0.7                              │
│   }                                                 │
└─────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────┐
│ 3. EVALUATOR (evaluator.py)                        │
│                                                     │
│ a) Extract evolved Go code                         │
│ b) Write to router.go                              │
│ c) go build -o blis                                │
│ d) Run on multiple traces:                         │
│    ./blis --trace traces/light_load.json           │
│    ./blis --trace traces/heavy_load.json           │
│    ./blis --trace traces/mixed_workload.json       │
│ e) Parse outputs:                                   │
│    Trace 1: e2e=118.5ms                            │
│    Trace 2: e2e=132.1ms                            │
│    Trace 3: e2e=121.8ms                            │
│ f) Compute score:                                   │
│    avg_e2e = (118.5 + 132.1 + 121.8) / 3 = 124.1ms│
│    score = 1.0 / avg_e2e = 0.00805                │
└─────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────┐
│ 4. DECISION                                         │
│                                                     │
│ New score (0.00805) > Old score (0.00798)?         │
│ YES → Keep new strategy                            │
│                                                     │
│ Store in database for future iterations            │
└─────────────────────────────────────────────────────┘
            ↓
            Repeat for 50-100 iterations
```

### Pseudo Evaluator Code

```python
def evaluate(program_text: str) -> dict:
    # 1. Extract Go code
    go_code = extract_go_code(program_text)

    # 2. Write to BLIS router module
    write_file("blis/router/weights.go", go_code)

    # 3. Build BLIS
    run("cd blis && go build -o blis")

    # 4. Run on multiple traces
    traces = ["light_load", "heavy_load", "mixed_workload"]
    latencies = []

    for trace in traces:
        output = run(f"./blis --trace traces/{trace}.json")
        e2e = parse_e2e_latency(output)  # Extract "e2e=125.3ms"
        latencies.append(e2e)

    # 5. Compute score (lower latency = better)
    avg_latency = mean(latencies)
    score = 1.0 / avg_latency  # Inverse so higher is better

    return {
        "combined_score": score,
        "avg_e2e_ms": avg_latency,
        "breakdown": {trace: lat for trace, lat in zip(traces, latencies)}
    }
```

---

## Expected Evolution Path

```
Iteration 0: Static weights (0.6, 0.4)
  → e2e: 125.3ms

Iteration 5: Adaptive based on cache hit rate
  → e2e: 121.8ms ✓ Improvement

Iteration 15: Considers both cache and load dynamically
  → e2e: 118.5ms ✓ Better

Iteration 30: Complex logic with request characteristics
  → e2e: 115.2ms ✓ Optimal
```

---

## Success Metrics

**Primary**: Average e2e latency reduction > 5%

**Secondary**:
- TTFT improvement
- Throughput increase
- Consistent performance across different workload types

---

## Next Steps

1. **BLIS Side**:
   - [ ] Add command-line interface for trace execution
   - [ ] Standardize stats output format
   - [ ] Extract router weighting into evolvable function
   - [ ] Provide 3 representative trace files

2. **OpenEvolve Side**:
   - [ ] Create `examples/blis_router/` directory
   - [ ] Write initial_program.py with baseline weights
   - [ ] Write evaluator.py that runs BLIS and parses output
   - [ ] Configure evolution parameters (50 iterations, Gemini model)

3. **Integration Test**:
   - [ ] Run 1 iteration end-to-end
   - [ ] Verify score calculation
   - [ ] Start full evolution

---

## Experiment 2: Adaptive Admission Control

### Problem Statement

In multi-tenant LLM deployments, admission control determines how external demand translates into internal load. The system must simultaneously:
- Maintain high utilization
- Enforce fairness across tenants
- Protect well-behaved traffic from pathological workloads (bursty arrivals, extremely long prompts)

**Challenge**: Static admission rules or quotas are insufficient with heterogeneous tenants and dynamic traffic patterns.

### Problem

Static admission rules (fixed concurrency limits, queue sizes) fail with heterogeneous tenants and dynamic traffic. Can't simultaneously maintain utilization, enforce fairness, and isolate bad actors.

### Solution: Evolve Adaptive Admission Policy

```go
// admission.go
func (ac *AdmissionController) ShouldAdmit(req Request, state SystemState) Decision {
    // EVOLVE-BLOCK-START
    // Baseline: Simple thresholds
    if state.Utilization > 0.9 {
        return REJECT
    }
    if state.QueueDepth > 100 {
        return DELAY
    }
    return ADMIT

    // Evolution directions:
    // → Per-tenant quotas (state.TenantLoad[req.TenantID])
    // → Detect bursty tenants (state.TenantBehavior.Burstiness)
    // → Penalize long prompts during high load (req.InputLen)
    // → Adaptive thresholds based on P99 latency
    // → Priority-based admission (high-value tenants bypass queue)
    // EVOLVE-BLOCK-END
}
```

### Objective & Metrics

**Goal**: Max throughput while maintaining fairness and P99 SLOs
**Inputs**: Tenant ID, request size, system utilization, per-tenant load, queue depth, P99 latency
**Output**: ADMIT | DELAY | REJECT
**Score**: `throughput * utilization * fairness * (1 if P99<500ms else 0.1)`

### Workload Characteristics

**Tenant Types** (for evaluation):

```
Well-behaved tenants (80%):
  - Poisson arrivals (λ = 10 req/s)
  - Input length: Normal(512, 128)
  - Output length: Normal(256, 64)

Bursty tenant (10%):
  - Bursty arrivals (bursts of 50 requests every 30s)
  - Input length: Normal(512, 128)
  - Output length: Normal(256, 64)

Long-prompt tenant (10%):
  - Poisson arrivals (λ = 5 req/s)
  - Input length: Normal(2048, 512)  ← Very long
  - Output length: Normal(1024, 256)  ← Very long
```


---

## Experiment 3: Joint Evolution of Priority Scheduling

### Problem Context

Priority scheduling in LLM-d spans multiple layers:
- **Global layer**: Flow control across distributed components
- **Local layer**: Instance-local scheduling and batching within vLLM backends

**Current Issue**: These layers are designed independently, leading to:
- Priority inversion (low-priority requests block high-priority)
- Head-of-line blocking
- Misalignment between global intent and local execution

The resulting behavior emerges from **coupled, non-linear interactions** across layers.

### Problem

Priority scheduling spans two layers (global routing + local batching), designed independently. Results in **priority inversion** (low-priority completes before high-priority) and **head-of-line blocking** (urgent requests stuck behind batches).

### Solution: Joint Evolution of Both Layers

```go
// Combined policy (evolved jointly)
type JointSchedulingPolicy struct{}

func (jsp *JointSchedulingPolicy) Execute(req Request, instances []Instance, localQueues map[string][]Request) (Instance, []Request) {
    // EVOLVE-BLOCK-START
    // Baseline: Simple load balancing + FCFS batching

    // Global: Route to least loaded instance
    selectedInstance := selectLeastLoaded(instances)

    // Local: FCFS batch of size 16
    localQueue := localQueues[selectedInstance.ID]
    batch := localQueue[:min(16, len(localQueue))]

    // Evolution directions:
    // → Global: Avoid instances with deep low-priority queues (check QueuePriorityProfile)
    // → Global: Amplify priority signals under congestion
    // → Local: Priority-aware batching (high-priority jumps queue)
    // → Local: Dynamic batch size based on priority distribution
    // → Local: Preemptive scheduling (interrupt low-priority batch for urgent request)
    // → Coordination: Pass priority context from global to local
    // EVOLVE-BLOCK-END

    return selectedInstance, batch
}
```

### Objective & Metrics

**Goal**: Max SLO attainment, suppress priority inversion & head-of-line blocking
**Inputs**: Request priority, SLO, instance loads, queue profiles, system state
**Output**: Instance selection + batch scheduling decisions
**Score**: `slo_attainment * (1 - inversion_rate) * (1 - hol_blocking)`
**Workloads**: 60% low-priority (SLO=2s), 30% medium (SLO=1s), 10% high (SLO=500ms)

**Joint Evolution**: LLM can mutate global layer, local layer, or both together. Evaluate system-level outcomes, not individual layers.


---

## Experiment 4: Autoscaling Evolution

### Problem Context

Modern LLM serving platforms consist of multiple model replicas distributed across GPU accelerators, handling variable request loads with strict SLOs (TTFT, ITL). The autoscaling system must dynamically adjust replica counts to maintain SLOs while optimizing resource utilization.

**Challenges**:
- Non-stationary workloads (time-varying arrival rates)
- Cold start latency when scaling up
- Resource costs (each replica = 1 GPU)
- Oscillation/thrashing (rapid scale up/down)

### Problem

**Baseline approaches fail**:
- Reactive thresholds: Too slow, causes SLO violations ❌
- Queueing models (M/M/1) + MILP: Modeling errors, parameter drift ❌

**Challenges**: Non-stationary workloads, cold start latency, thrashing, cost optimization

### Solution: Evolve Data-Driven Autoscaling

```go
// autoscaler.go
func (as *Autoscaler) DecideScaling(current Metrics, history []Metrics) int {
    // EVOLVE-BLOCK-START
    // Baseline: Reactive threshold
    if current.P99_TTFT > SLO_TTFT * 1.2 {
        return +1  // Scale up
    } else if current.P99_TTFT < SLO_TTFT * 0.7 {
        return -1  // Scale down
    }
    return 0

    // Evolution directions:
    // → Predictive: Detect arrival rate trends in history, scale proactively
    // → Workload-aware: Scale more for long prompts (current.AvgInputLen)
    // → Hysteresis: Track recent decisions, prevent rapid up/down thrashing
    // → Burst detection: Identify spikes early, scale aggressively (+2, +3)
    // → Cost-aware: Balance SLO margins with replica costs
    // → Time-of-day: Learn diurnal patterns from history
    // EVOLVE-BLOCK-END
}
```

### Objective & Metrics

**Goal**: Minimize cost while maintaining SLOs (P99 TTFT < 500ms, ITL < 50ms)
**Decision Frequency**: Every 30-60s
**Inputs**: Current metrics (TTFT, ITL, throughput, queue, replicas, utilization) + history (last 5-30 min)
**Output**: Scaling adjustment ∈ {-3, -2, -1, 0, +1, +2, +3}
**Constraints**: Min 2 replicas, max 20, cooldowns (60s up, 180s down)
**Score**: `slo_attainment / (cost * (1 + thrashing_penalty))`

### Workload Patterns

1. **Steady-state**: 10 req/s constant
2. **Ramp-up**: 5→30 req/s gradual increase
3. **Burst**: 10 req/s background, 50 req/s periodic spikes
4. **Diurnal**: 24-hour cycle (peak 30, valley 5)
5. **Flash crowd**: 10 req/s → 100 req/s sudden spike

**Baselines**: Reactive threshold, Queueing+MILP, K8s HPA
**Sim-to-Real**: Evolve in BLIS → Shadow deployment in WVA → A/B test → Production comparison

---

## Contract Update: BLIS Requirements

### For Experiments 1-4 (Router + Admission + Priority + Autoscaling)

#### 1. Multi-Experiment Support

BLIS must support specifying which module to evolve:

```bash
# Experiment 1: Router
./blis --trace traces/workload.json --config config.yaml

# Experiment 2: Admission Control
./blis --trace traces/admission/mixed.json --config config_admission.yaml
```

#### 2. Admission Control Module Structure

```go
// admission/policy.go
package admission

type SystemState struct {
    Utilization    float64              // Current system utilization [0-1]
    TenantLoad     map[string]int       // Active requests per tenant
    QueueDepth     int                  // Current queue size
    P99Latency     float64              // Recent P99 latency (ms)
    TenantBehavior map[string]Behavior  // Per-tenant behavior metrics
}

type Behavior struct {
    Burstiness     float64  // Coefficient of variation
    AvgInputLen    float64  // Average input length
    AvgOutputLen   float64  // Average output length
}

type Request struct {
    TenantID  string
    InputLen  int
    OutputLen int
}

type Decision int
const (
    ADMIT Decision = iota
    DELAY
    REJECT
)

// EVOLVE-BLOCK-START and EVOLVE-BLOCK-END markers
func AdmissionPolicy(req Request, state SystemState) Decision {
    // EVOLVE-BLOCK-START
    if state.Utilization > 0.9 {
        return REJECT
    }
    return ADMIT
    // EVOLVE-BLOCK-END
}
```

#### 3. Output Format (Extended)

```
STATS: throughput=150req/s utilization=0.82 p99_latency=385ms fairness=0.85
TENANT_STATS: tenant1_p99=350ms tenant2_p99=380ms tenant3_p99=420ms
ADMISSION_STATS: admitted=1500 delayed=200 rejected=50
```

**Parsing**:
- `throughput`: Overall system throughput
- `utilization`: System utilization
- `p99_latency`: P99 latency across all admitted requests
- `fairness`: Jain's fairness index across tenants
- Per-tenant P99 latencies for constraint checking

#### 4. Trace Format (Admission)

```json
{
  "requests": [
    {
      "arrival_time": 0.0,
      "tenant_id": "tenant1",
      "input_len": 512,
      "output_len": 256
    },
    {
      "arrival_time": 0.1,
      "tenant_id": "tenant2",
      "input_len": 2048,
      "output_len": 1024
    }
  ],
  "tenant_profiles": {
    "tenant1": {"type": "well_behaved"},
    "tenant2": {"type": "long_prompt"},
    "tenant3": {"type": "bursty"}
  }
}
```

#### 5. Priority Scheduling Module Structure

```go
// scheduler/global.go
package scheduler

type GlobalScheduler struct {
    instances []Instance
}

type Instance struct {
    ID                   string
    Load                 float64
    QueueDepth           int
    QueuePriorityProfile map[int]int  // priority -> count
}

type PrioritySignal struct {
    Priority  int
    Amplified bool
}

// EVOLVE-BLOCK-START
func (gs *GlobalScheduler) SelectInstance(req Request, instances []Instance) (Instance, PrioritySignal) {
    // Evolved global routing + priority propagation
    return instances[0], PrioritySignal{Priority: req.Priority}
}
// EVOLVE-BLOCK-END

// scheduler/local.go
type LocalScheduler struct {
    queue []Request
}

// EVOLVE-BLOCK-START
func (ls *LocalScheduler) ScheduleBatch(requests []Request) []Request {
    // Evolved local scheduling + batching
    batchSize := 16
    return requests[:min(batchSize, len(requests))]
}
// EVOLVE-BLOCK-END
```

#### 6. Output Format (Extended for Priority)

```
STATS: throughput=150req/s slo_attainment=0.92 priority_inversions=0.03 hol_blocking=0.08
PRIORITY_STATS: p1-3_latency=1200ms p4-7_latency=650ms p8-10_latency=320ms
FAILURE_MODES: inversions=15 hol_events=42 hol_avg_delay=85ms
```

**Parsing**:
- `slo_attainment`: Fraction of requests meeting their SLO
- `priority_inversions`: Rate of priority inversion events
- `hol_blocking`: Head-of-line blocking severity (normalized)
- Per-priority-class latencies
- Failure mode counts and severity

#### 7. Trace Format (Priority)

```json
{
  "requests": [
    {
      "arrival_time": 0.0,
      "priority": 8,
      "slo_ms": 500,
      "input_len": 512,
      "output_len": 256
    },
    {
      "arrival_time": 0.1,
      "priority": 2,
      "slo_ms": 2000,
      "input_len": 512,
      "output_len": 256
    }
  ],
  "instances": [
    {"id": "inst1", "capacity": 1000},
    {"id": "inst2", "capacity": 1000}
  ]
}
```

#### 8. Autoscaling Module Structure

```go
// autoscaler/policy.go
package autoscaler

type Metrics struct {
    // Latency
    P50_TTFT float64
    P99_TTFT float64
    P50_ITL  float64
    P99_ITL  float64

    // Load
    ArrivalRate      float64
    Throughput       float64
    QueueDepth       int

    // Capacity
    CurrentReplicas       int
    ReplicaUtilization    []float64
    AvgReplicaUtilization float64

    // Time
    Timestamp float64
}

type HistoricalMetrics struct {
    Last5Min  []Metrics  // Recent history (10 intervals @ 30s)
    Last30Min []Metrics  // Longer-term history
}

// EVOLVE-BLOCK-START
func AutoscalingPolicy(current Metrics, history HistoricalMetrics) int {
    // Evolved autoscaling logic
    // Returns: scaling adjustment (-3 to +3)

    if current.P99_TTFT > 500 * 1.2 {
        return +1
    } else if current.P99_TTFT < 500 * 0.7 {
        return -1
    }
    return 0
}
// EVOLVE-BLOCK-END
```

#### 9. Output Format (Extended for Autoscaling)

```
STATS: throughput=150req/s p50_ttft=250ms p99_ttft=480ms p50_itl=25ms p99_itl=45ms
CAPACITY: replicas=5 avg_utilization=0.78 replica_hours=2.5
SCALING: decisions=12 scale_ups=5 scale_downs=3 thrashing_events=1
COST: total_cost=$6.25 slo_violations=0.02 cost_per_request=$0.042
```

**Parsing**:
- `p99_ttft`, `p99_itl`: Tail latencies for SLO checking
- `replicas`: Current replica count
- `replica_hours`: Cumulative resource usage
- `scaling` stats: Autoscaler behavior
- `cost`: Total cost and per-request cost
- `slo_violations`: Fraction of time violating SLOs

#### 10. Trace Format (Autoscaling)

```json
{
  "duration_seconds": 1800,
  "decision_interval_seconds": 30,
  "workload_pattern": "burst",
  "time_series": [
    {
      "time": 0.0,
      "arrival_rate": 10.0,
      "requests": [
        {"input_len": 512, "output_len": 256},
        ...
      ]
    },
    {
      "time": 30.0,
      "arrival_rate": 15.0,
      "requests": [...]
    }
  ],
  "slo": {
    "p99_ttft_ms": 500,
    "p99_itl_ms": 50
  },
  "constraints": {
    "min_replicas": 2,
    "max_replicas": 20,
    "max_scaling_step": 3,
    "gpu_cost_per_hour": 2.50
  }
}
```

---

## Validation & Migration Pipeline

### Phase 1: Evolution (Training Phase)

```
Training Traces (used during evolution):
├── light_load.json       # 1000 requests, low concurrency
├── heavy_load.json       # 5000 requests, high concurrency
└── mixed_workload.json   # 3000 requests, varied patterns
```

**Output**: Best evolved algorithm after 50 iterations

### Phase 2: Validation (Hold-out Testing)

Test on **unseen** traces to verify generalization:

```bash
# Create hold-out test set (not used during evolution)
validation_traces/
├── burst_traffic.json        # Sudden load spikes
├── long_context.json         # Large input/output lengths
├── production_replay.json    # Real production traces
└── adversarial.json          # Stress test patterns
```

**Validation Script**:
```python
def validate_algorithm(evolved_router, baseline_router):
    """Compare evolved vs manual baseline on unseen data"""

    results = {
        "evolved": {},
        "baseline": {}
    }

    test_traces = [
        "burst_traffic",
        "long_context",
        "production_replay",
        "adversarial"
    ]

    # Test both algorithms
    for trace in test_traces:
        # Test evolved algorithm
        # 1. Write evolved router code
        write_file("blis/router/weights.go", evolved_router_code)
        # 2. Rebuild BLIS
        run("cd blis && go build -o blis")
        # 3. Run on trace
        evolved_output = run(f"./blis --trace validation_traces/{trace}.json")
        evolved_stats = parse_stats(evolved_output)

        # Test manual baseline
        # 1. Write baseline router code (kvWeight=0.6, loadWeight=0.4)
        write_file("blis/router/weights.go", baseline_router_code)
        # 2. Rebuild BLIS
        run("cd blis && go build -o blis")
        # 3. Run on trace
        baseline_output = run(f"./blis --trace validation_traces/{trace}.json")
        baseline_stats = parse_stats(baseline_output)

        results["evolved"][trace] = evolved_stats
        results["baseline"][trace] = baseline_stats

    return results
```

**Success Criteria**:
- Evolved algorithm must beat baseline on **all** validation traces
- No single trace can have >3% regression
- Average improvement across all traces >5%

### Phase 3: Statistical Justification

Generate comparison report:

```
┌─────────────────────────────────────────────────────────────┐
│ VALIDATION REPORT: Evolved vs Manual Baseline              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Test Trace          │ Baseline  │ Evolved   │ Improvement │
│─────────────────────┼───────────┼───────────┼─────────────│
│ burst_traffic       │ 135.2ms   │ 125.8ms   │  +6.9%  ✓  │
│ long_context        │ 248.5ms   │ 231.2ms   │  +7.0%  ✓  │
│ production_replay   │ 142.8ms   │ 138.1ms   │  +3.3%  ✓  │
│ adversarial         │ 198.3ms   │ 189.5ms   │  +4.4%  ✓  │
│─────────────────────┼───────────┼───────────┼─────────────│
│ AVERAGE             │ 181.2ms   │ 171.2ms   │  +5.5%  ✓  │
│                                                             │
│ Consistency: 4/4 traces improved                           │
│ Max regression: 0% (all improved)                          │
│                                                             │
│ ✅ VALIDATION PASSED - Ready for migration                 │
└─────────────────────────────────────────────────────────────┘
```

**Statistical Tests**:
```python
# Paired t-test to verify improvement is significant
from scipy import stats

baseline_latencies = [135.2, 248.5, 142.8, 198.3]
evolved_latencies = [125.8, 231.2, 138.1, 189.5]

t_stat, p_value = stats.ttest_rel(baseline_latencies, evolved_latencies)

if p_value < 0.05:
    print("✓ Improvement is statistically significant")
```

### Phase 4: Migration to Production LLMD

**Step 1: Extract Evolved Logic**

```go
// From BLIS simulator (evolved)
func ComputeWeights(kvScore, loadScore float64, state SystemState, req Request) (float64, float64) {
    // EVOLVED LOGIC (found by OpenEvolve)
    if state.CacheHitRate > 0.75 {
        kvWeight := 0.8
        loadWeight := 0.2
    } else if state.AverageLoad > 0.6 {
        kvWeight := 0.3
        loadWeight := 0.7
    } else {
        kvWeight := 0.5
        loadWeight := 0.5
    }

    return kvWeight, loadWeight
}
```

**Step 2: Port to LLMD**

```go
// llmd/router/adaptive_weights.go
package router

// Direct port from validated BLIS algorithm
func (r *Router) computeAdaptiveWeights() (float64, float64) {
    // Get current system state
    state := r.systemMonitor.GetState()

    kvScore := r.kvCacheScorer.Score(r.currentRequest)
    loadScore := r.loadScorer.Score(r.currentRequest)

    // EVOLVED LOGIC (copied from BLIS)
    var kvWeight, loadWeight float64

    if state.CacheHitRate > 0.75 {
        kvWeight = 0.8
        loadWeight = 0.2
    } else if state.AverageLoad > 0.6 {
        kvWeight = 0.3
        loadWeight = 0.7
    } else {
        kvWeight = 0.5
        loadWeight = 0.5
    }

    return kvWeight, loadWeight
}
```

**Step 3: A/B Testing in Production**

```
Production Deployment Strategy:

Week 1: Shadow Mode
  - Run evolved algorithm alongside baseline
  - Log decisions from both (don't affect routing)
  - Compare offline

Week 2: 10% Traffic
  - Route 10% of traffic with evolved algorithm
  - Monitor metrics closely
  - Compare with 90% baseline traffic

Week 3: 50% Traffic
  - Gradual ramp-up if metrics look good
  - A/B test: 50% evolved, 50% baseline

Week 4: 100% Rollout
  - Full deployment if all metrics improved
  - Keep baseline as fallback
```

**Monitoring Dashboard**:
```
┌─────────────────────────────────────────────────────┐
│ Production A/B Test: Evolved vs Baseline           │
│                                                     │
│ Metric        │ Baseline  │ Evolved   │ Delta     │
│───────────────┼───────────┼───────────┼───────────│
│ Avg Latency   │ 145ms     │ 138ms     │ -4.8% ✓  │
│ P99 Latency   │ 320ms     │ 305ms     │ -4.7% ✓  │
│ Throughput    │ 1200 rps  │ 1235 rps  │ +2.9% ✓  │
│ Error Rate    │ 0.12%     │ 0.11%     │ -8.3% ✓  │
│───────────────┼───────────┼───────────┼───────────│
│ Traffic Split │ 50%       │ 50%       │           │
│                                                     │
│ ✅ All metrics improved - proceed to 100%          │
└─────────────────────────────────────────────────────┘
```

### Phase 5: Justification Documentation

Create final report for stakeholders:

```markdown
# Router Optimization via OpenEvolve - Results Summary

## Problem Statement
Manual weight tuning (kvWeight=0.6, loadWeight=0.4) required expert knowledge
and didn't adapt to changing system conditions.

## Solution
Evolved dynamic weighting strategy using OpenEvolve that adapts based on:
- Cache hit rate
- System load
- Request characteristics

## Validation Results

### Simulator Testing (BLIS)
- Training: 3 traces, 50 iterations
- Validation: 4 unseen traces
- **Result**: 5.5% average latency improvement, 100% consistency

### Production A/B Test
- Duration: 4 weeks
- Traffic: Ramped 10% → 50% → 100%
- **Results**:
  - Latency: -4.8% (145ms → 138ms)
  - P99: -4.7% (320ms → 305ms)
  - Throughput: +2.9% (1200 → 1235 rps)

### Cost Savings
- 4.8% latency reduction = 4.8% more requests per GPU
- Annual savings: ~$X per cluster

## Conclusion
✅ Evolved algorithm outperforms manual baseline in simulation and production
✅ Zero regressions across all test scenarios
✅ Successfully deployed to 100% of production traffic
```

### Rollback Plan

**If validation fails or production degrades**:

```bash
# Immediate rollback
kubectl set env deployment/llmd ROUTER_MODE=baseline

# Or gradual rollback
# Reduce evolved traffic: 100% → 50% → 10% → 0%
```

**Failure Criteria**:
- Any metric regresses >2% in production
- Error rate increases
- User complaints spike

---

## Validation Checklist

Before migration to LLMD:

- [ ] Evolved algorithm passes all validation traces
- [ ] Statistical significance confirmed (p < 0.05)
- [ ] Code review of evolved logic (no obvious bugs)
- [ ] Performance improvement >5% on average
- [ ] No single trace has >3% regression
- [ ] Algorithm is explainable (not black box)
- [ ] Migration plan approved
- [ ] Rollback procedure tested
- [ ] Monitoring dashboards ready
- [ ] A/B test framework configured

---

## Future Experiments

- **Experiment 5**: KV Cache Eviction Policy
- **Experiment 6**: Scheduler Batch Size Optimization
- **Experiment 7**: Multi-objective Optimization (latency + throughput + cost)
- **Experiment 8**: Cross-layer Co-optimization (admission + routing + scheduling + autoscaling jointly)
