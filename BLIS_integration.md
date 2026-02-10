# BLIS + OpenEvolve Integration Plan

## Overview

Use OpenEvolve to automatically optimize BLIS (vLLM simulator) router module by evolving dynamic weighting strategies.

**Problem**: Router currently requires manual weight tuning for combining scores
**Solution**: Evolve adaptive weighting logic that automatically adjusts based on system state

---

## Experiment 1: Dynamic Router Weighting

### Current State

```go
// router.go - Current manual approach
type Router struct {
    kvCacheScorer   Scorer  // KV cache hit probability
    loadScorer      Scorer  // Load-aware scoring

    // User must set these manually ❌
    kvWeight   float64  // e.g., 0.6
    loadWeight float64  // e.g., 0.4
}

func (r *Router) SelectServer(request Request) Server {
    kvScore := r.kvCacheScorer.Score(request)
    loadScore := r.loadScorer.Score(request)

    // Static weights
    finalScore := r.kvWeight * kvScore + r.loadWeight * loadScore
    return selectBestServer(finalScore)
}
```

### Goal State

```go
// router.go - Dynamic weighting (EVOLVED by OpenEvolve)
type Router struct {
    kvCacheScorer Scorer
    loadScorer    Scorer
}

func (r *Router) SelectServer(request Request, state SystemState) Server {
    kvScore := r.kvCacheScorer.Score(request)
    loadScore := r.loadScorer.Score(request)

    // EVOLVE-BLOCK-START
    // Dynamic weighting logic (evolved by OpenEvolve)
    kvWeight := 0.6
    loadWeight := 0.4
    // Could evolve to be adaptive based on:
    // - state.CacheHitRate
    // - state.AverageLoad
    // - request characteristics
    // EVOLVE-BLOCK-END

    finalScore := kvWeight * kvScore + loadWeight * loadScore
    return selectBestServer(finalScore)
}
```

### Experiment Design

**Objective**: Find optimal dynamic weighting strategy that minimizes average e2e latency

**Input Variables** (available to evolved code):
- `kvScore` - KV cache hit probability [0-1]
- `loadScore` - Load-aware score [0-1]
- `state.CacheHitRate` - System-wide cache hit rate
- `state.AverageLoad` - Current system load
- `request.InputLen` - Request input length
- `request.OutputLen` - Expected output length

**Output**: `kvWeight` and `loadWeight` that sum to 1.0

**Metric**: Average end-to-end latency across all requests

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

### Current State

```go
// admission.go - Current static approach
type AdmissionController struct {
    maxConcurrency int     // Fixed limit ❌
    maxQueueSize   int     // Static queue ❌
}

func (ac *AdmissionController) ShouldAdmit(req Request, state SystemState) Decision {
    // Simple static rules
    if state.ActiveRequests >= ac.maxConcurrency {
        if state.QueueSize >= ac.maxQueueSize {
            return REJECT
        }
        return DELAY
    }
    return ADMIT
}
```

### Goal State

```go
// admission.go - Adaptive policy (EVOLVED by OpenEvolve)
type AdmissionController struct {
    // System monitors
    utilizationMonitor  Monitor
    fairnessMonitor     Monitor
}

func (ac *AdmissionController) ShouldAdmit(req Request, state SystemState) Decision {
    // EVOLVE-BLOCK-START
    // Adaptive admission logic (evolved by OpenEvolve)

    // Input signals available:
    // - req.TenantID, req.InputLen, req.OutputLen
    // - state.Utilization (0-1)
    // - state.TenantLoad[tenantID] (per-tenant active requests)
    // - state.QueueDepth
    // - state.P99Latency (recent tail latency)

    // Simple baseline (to be evolved)
    if state.Utilization > 0.9 {
        return REJECT
    }
    if state.QueueDepth > 100 {
        return DELAY
    }
    return ADMIT

    // Could evolve to:
    // - Per-tenant quotas based on fairness
    // - Traffic shaping for bursty tenants
    // - Priority-based admission
    // - Load-aware admission thresholds
    // EVOLVE-BLOCK-END
}
```

### Experiment Design

**Objective**: Maximize system throughput while:
- Bounding P99 latency for well-behaved tenants
- Isolating misbehaving traffic (bursty, long prompts)
- Enforcing fairness across tenants

**Input Variables** (available to evolved code):
- `req.TenantID` - Tenant identifier
- `req.InputLen` - Prompt length
- `req.OutputLen` - Expected output length
- `state.Utilization` - Current system utilization [0-1]
- `state.TenantLoad` - Per-tenant active request counts
- `state.QueueDepth` - Current queue size
- `state.P99Latency` - Recent P99 latency
- `state.TenantBehavior` - Tenant behavior metrics (burstiness, avg length)

**Output**: Decision ∈ {ADMIT, DELAY, REJECT}

**Metrics**:
- **Primary**: Throughput (requests/second)
- **Constraint 1**: P99 latency < 500ms for well-behaved tenants
- **Constraint 2**: Fairness score > 0.8 (Jain's fairness index)
- **Constraint 3**: Utilization > 0.75

**Scoring Function**:
```python
score = throughput * utilization * fairness_score
if p99_latency > 500:  # Hard constraint
    score *= 0.1  # Heavy penalty
```

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

### Trace Files

```
traces/admission/
├── baseline.json           # All well-behaved tenants
├── with_bursty.json        # 1 bursty tenant + 4 well-behaved
├── with_long_prompts.json  # 1 long-prompt + 4 well-behaved
└── mixed_pathological.json # Both bursty + long-prompt
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

### Current State

```go
// Global flow control (simplified)
type GlobalScheduler struct {
    priorityQueue PriorityQueue  // Simple priority queue ❌
}

func (gs *GlobalScheduler) RouteRequest(req Request) Instance {
    // Route based on priority, but local scheduler may reorder
    return selectInstance(req.Priority)
}

// Local scheduler (per-instance)
type LocalScheduler struct {
    batchSize int  // Fixed batch size ❌
}

func (ls *LocalScheduler) ScheduleBatch() []Request {
    // FCFS batching, ignores global priorities ❌
    return ls.queue.GetNext(ls.batchSize)
}
```

**Problem**: Global scheduler sends high-priority request to instance, but local FCFS scheduler may delay it behind many low-priority requests.

### Goal State

```go
// Global scheduler (EVOLVED)
type GlobalScheduler struct {
    // Evolved priority signaling strategy
}

func (gs *GlobalScheduler) SelectInstance(req Request, instances []Instance) (Instance, PrioritySignal) {
    // EVOLVE-BLOCK-START (Global)
    // Evolved global priority propagation

    // Available signals:
    // - req.Priority (1-10, higher is more urgent)
    // - req.SLO (target latency)
    // - instances[i].Load
    // - instances[i].QueueDepth
    // - instances[i].QueuePriorityProfile

    // Baseline: route to least loaded
    selectedInstance := selectLeastLoaded(instances)
    prioritySignal := req.Priority  // Pass through

    // Could evolve to:
    // - Avoid routing high-priority to instances with deep low-priority queues
    // - Amplify priority signals under congestion
    // - Coordinate with local scheduler expectations
    // EVOLVE-BLOCK-END

    return selectedInstance, prioritySignal
}

// Local scheduler (EVOLVED, per-instance)
type LocalScheduler struct {
    // Evolved batching and scheduling strategy
}

func (ls *LocalScheduler) ScheduleBatch(requests []Request) []Request {
    // EVOLVE-BLOCK-START (Local)
    // Evolved local scheduling and batching

    // Available information:
    // - requests[i].Priority
    // - requests[i].GlobalSignal (from global scheduler)
    // - requests[i].ArrivalTime
    // - requests[i].EstimatedDuration
    // - ls.CurrentBatch (ongoing batch)
    // - ls.SystemLoad

    // Baseline: FCFS with fixed batch size
    batchSize := 16
    batch := requests[:min(batchSize, len(requests))]

    // Could evolve to:
    // - Priority-aware batching (high-priority requests jump queue)
    // - Dynamic batch sizing based on priority distribution
    // - Preemption of low-priority batches
    // - Head-of-line blocking mitigation
    // EVOLVE-BLOCK-END

    return batch
}
```

### Experiment Design

**Objective**: Jointly optimize global and local scheduling to maximize SLO attainment while suppressing failure modes

**Decision Surfaces**:

1. **Global Layer**:
   - Instance selection considering queue priority profiles
   - Priority signal propagation (amplification/damping)
   - Load balancing vs priority preservation trade-offs

2. **Local Layer**:
   - Scheduling order (FCFS, priority-based, preemptive)
   - Batch size (fixed vs dynamic)
   - Batch composition (priority mixing strategies)

**Input Variables**:

*Global scheduler:*
- `req.Priority` - Request priority [1-10]
- `req.SLO` - Target latency (ms)
- `instance.Load` - Current utilization
- `instance.QueueDepth` - Number of queued requests
- `instance.QueuePriorityProfile` - Distribution of priorities in queue

*Local scheduler:*
- `req.Priority` - Request priority
- `req.GlobalSignal` - Signal from global scheduler
- `req.ArrivalTime` - When request arrived
- `req.EstimatedDuration` - Expected processing time
- `systemLoad` - Current instance load

**Metrics**:
- **Primary**: SLO attainment rate (% requests meeting latency target)
- **Failure modes**:
  - Priority inversion events (low-priority completes before high-priority that arrived earlier)
  - Head-of-line blocking severity (high-priority delay due to queue position)
- **Secondary**: Throughput, fairness across priority classes

**Scoring Function**:
```python
score = slo_attainment_rate * (1 - priority_inversion_rate) * (1 - hol_blocking_severity)

# Penalties for failure modes
if priority_inversion_rate > 0.05:  # >5% inversions
    score *= 0.5
if hol_blocking_severity > 0.1:     # >100ms avg HOL delay
    score *= 0.5
```

### Workload Characteristics

**Request Priority Distribution**:
```
Priority 1-3 (Low):     60% of requests, SLO = 2000ms
Priority 4-7 (Medium):  30% of requests, SLO = 1000ms
Priority 8-10 (High):   10% of requests, SLO = 500ms
```

**Arrival Patterns**:
- Baseline: Poisson arrivals mixed priorities
- Stress: Bursty high-priority arrivals during high load
- Adversarial: Low-priority flood with occasional high-priority

### Joint Evolution Strategy

**Two-level co-evolution**:

```
┌─────────────────────────────────────────────────────┐
│ JOINT EVOLUTION                                     │
│                                                     │
│ 1. Sample global + local policies from database    │
│ 2. LLM generates mutation:                         │
│    Option A: Mutate global policy only             │
│    Option B: Mutate local policy only              │
│    Option C: Mutate both (coordinated)             │
│ 3. Run BLIS with joint policy                      │
│ 4. Measure system-level outcomes                   │
│ 5. Score based on global metrics                   │
└─────────────────────────────────────────────────────┘
```

**Key insight**: Evaluate policies jointly, not in isolation. A "good" global policy may fail with a "bad" local policy and vice versa.

### Trace Files

```
traces/priority/
├── baseline_mixed.json         # Mixed priorities, uniform arrivals
├── high_priority_burst.json    # Burst of high-priority during load
├── low_priority_flood.json     # Flood of low-priority + some high
└── priority_inversion_stress.json  # Adversarial for inversion
```

### Example Failure Modes to Detect

**Priority Inversion**:
```
Timeline:
T=0:   High-priority req A arrives → routed to Instance 1
T=1:   Instance 1 has 50 low-priority requests in queue
T=2:   Low-priority req B arrives → routed to Instance 2 (empty queue)
T=3:   Req B completes (Instance 2)
T=10:  Req A completes (Instance 1, waited behind 50 requests)
       ❌ Priority inversion: Low-priority B completed before high-priority A
```

**Head-of-Line Blocking**:
```
Timeline:
T=0:   Instance has batch of 16 requests processing
T=1:   High-priority urgent request arrives
T=2:   Must wait for entire batch to complete before processing
       ❌ HOL blocking: High-priority delayed by batch boundary
```

**Evolved Solution Example**:
```go
// Global: Route high-priority to instance with fewest high-priority queued
// Local: Preempt current batch if new high-priority arrives + batch age > threshold
// Result: High-priority requests get fast-tracked without starving low-priority
```

---

## Experiment 4: Autoscaling Evolution

### Problem Context

Modern LLM serving platforms consist of multiple model replicas distributed across GPU accelerators, handling variable request loads with strict SLOs (TTFT, ITL). The autoscaling system must dynamically adjust replica counts to maintain SLOs while optimizing resource utilization.

**Challenges**:
- Non-stationary workloads (time-varying arrival rates)
- Cold start latency when scaling up
- Resource costs (each replica = 1 GPU)
- Oscillation/thrashing (rapid scale up/down)

### Current Approaches & Limitations

**Baseline 1: Reactive Threshold-Based**
```go
if avgLatency > sloThreshold * 1.2 {
    scaleUp()
} else if avgLatency < sloThreshold * 0.8 {
    scaleDown()
}
```
❌ Reacts too late, causes SLO violations during bursts

**Baseline 2: Queueing Model + MILP Optimization**
```
1. Model system as M/M/1 queue
2. Predict required replicas using Little's Law
3. Optimize replica count with MILP solver
```
❌ Modeling errors under non-stationary workloads
❌ Simplistic assumptions (uncorrelated input/output lengths)
❌ Parameter drift over time

### Current State

```go
// autoscaler.go - Current model-based approach
type Autoscaler struct {
    queueingModel *MMOneModel
    optimizer     *MILPSolver
}

func (as *Autoscaler) DecideScaling(metrics Metrics) int {
    // 1. Predict arrivals using queueing model
    predictedLoad := as.queueingModel.Predict(metrics.ArrivalRate)

    // 2. Calculate required replicas
    requiredReplicas := as.optimizer.Solve(predictedLoad, metrics.SLO)

    // 3. Return scaling decision
    return requiredReplicas - metrics.CurrentReplicas
}
```

### Goal State

```go
// autoscaler.go - Evolved data-driven approach
type Autoscaler struct {
    metricsHistory []Metrics  // Recent history
}

func (as *Autoscaler) DecideScaling(currentMetrics Metrics, history []Metrics) int {
    // EVOLVE-BLOCK-START
    // Evolved autoscaling policy

    // Available signals:
    // - currentMetrics.P50_TTFT, P99_TTFT, P50_ITL, P99_ITL
    // - currentMetrics.Throughput, QueueDepth
    // - currentMetrics.CurrentReplicas
    // - currentMetrics.ReplicaUtilization (per-replica GPU util)
    // - history (last 10 decision intervals)
    //   - history[i].ArrivalRate, Latency, QueueDepth

    // Baseline: Simple reactive
    if currentMetrics.P99_TTFT > SLO_TTFT * 1.2 {
        return +1  // Scale up
    } else if currentMetrics.P99_TTFT < SLO_TTFT * 0.7 {
        return -1  // Scale down
    }
    return 0  // No change

    // Could evolve to:
    // - Predictive scaling based on arrival rate trends
    // - Workload-aware scaling (long prompts need more replicas)
    // - Hysteresis to prevent thrashing
    // - Burst detection and preemptive scaling
    // - Cost-aware scaling with SLO budgets
    // - Multi-step scaling (scale by +2, +3 during extreme load)
    // EVOLVE-BLOCK-END
}
```

### Experiment Design

**Objective**: Evolve autoscaling policy that minimizes cost while maintaining SLOs

**Decision Surface**:
- **Frequency**: Every 30-60 seconds (scaling decision interval)
- **Inputs**: Current metrics + recent history (last 5-10 intervals)
- **Output**: Scaling adjustment ∈ {-3, -2, -1, 0, +1, +2, +3}

**Input Variables**:
```go
type Metrics struct {
    // Latency metrics
    P50_TTFT float64  // Median time-to-first-token
    P99_TTFT float64  // 99th percentile TTFT
    P50_ITL  float64  // Median inter-token latency
    P99_ITL  float64  // 99th percentile ITL

    // Load metrics
    ArrivalRate      float64  // Requests per second
    Throughput       float64  // Completed requests per second
    QueueDepth       int      // Current queue size

    // Capacity metrics
    CurrentReplicas       int       // Current replica count
    ReplicaUtilization    []float64 // Per-replica GPU utilization
    AvgReplicaUtilization float64   // Average across replicas
}

type HistoricalMetrics struct {
    Last5Min  []Metrics  // Last 10 intervals (30s each)
    Last30Min []Metrics  // Last 60 intervals (aggregated)
}
```

**Constraints**:
- Max replicas: 20 (cluster capacity)
- Min replicas: 2 (availability)
- Max scaling step: ±3 replicas per decision
- Cooldown: 60s after scale-up, 180s after scale-down

**Metrics**:

**Primary**:
```python
# Cost-SLO trade-off
cost = replica_hours * gpu_cost_per_hour
slo_violations = requests_violating_slo / total_requests

score = (1 - slo_violations) / (cost + epsilon)
# Maximize SLO attainment per dollar spent
```

**Secondary**:
- **Scaling stability**: Number of scaling actions (fewer is better)
- **Over-provisioning**: Average excess capacity
- **Under-provisioning**: Time spent violating SLOs
- **Cold start impact**: Latency during scale-up events

**SLO Definitions**:
```
TTFT SLO: P99 < 500ms
ITL SLO:  P99 < 50ms
```

### Workload Patterns

**Training workloads** (for evolution):

```
1. Steady-state (baseline):
   - Constant arrival rate: 10 req/s
   - Duration: 30 minutes

2. Ramp-up:
   - Start: 5 req/s
   - Linear increase to 30 req/s over 20 minutes
   - Hold at 30 req/s for 10 minutes

3. Burst:
   - Background: 10 req/s
   - Burst: 50 req/s for 2 minutes every 10 minutes
   - Duration: 30 minutes

4. Diurnal pattern:
   - Simulate 24-hour cycle (accelerated to 30 minutes)
   - Peak: 30 req/s (business hours)
   - Valley: 5 req/s (off-hours)

5. Flash crowd:
   - Background: 10 req/s
   - Sudden spike to 100 req/s for 5 minutes
   - Return to 10 req/s
```

### Failure Modes to Avoid

**1. Thrashing**:
```
T=0:   Scale up (+2 replicas)
T=60:  Queue drains, scale down (-2 replicas)
T=120: Queue builds, scale up (+2 replicas)
T=180: Repeat...
❌ Wasteful, adds cold start overhead
```

**2. Late Reaction**:
```
T=0:   Burst starts, queue builds rapidly
T=60:  Autoscaler notices, scales up (+2)
T=90:  Replicas ready, but 30s of SLO violations already occurred
❌ Reactive, not proactive
```

**3. Over-Provisioning**:
```
Workload drops to 5 req/s (needs 2 replicas)
Autoscaler maintains 10 replicas (fear of scale-down)
❌ 8 idle replicas = wasted cost
```

**Evolved Solutions Should**:
- Detect trends (ramp-up) and scale proactively
- Use hysteresis to prevent thrashing
- Balance SLO safety margins with cost efficiency

### Trace Files

```
traces/autoscaling/
├── steady_state.json        # Constant load, test stability
├── ramp_up.json             # Gradual increase, test prediction
├── burst.json               # Periodic bursts, test responsiveness
├── diurnal.json             # Daily pattern, test long-term behavior
├── flash_crowd.json         # Extreme spike, test robustness
└── mixed_pattern.json       # Combination of all patterns
```

### Evaluation Metrics

**Cost Efficiency**:
```
replica_hours = Σ(replicas_at_time_t * duration_t)
cost = replica_hours * $2.50/GPU-hour
```

**SLO Attainment**:
```
slo_violations = count(P99_TTFT > 500ms OR P99_ITL > 50ms)
slo_attainment = 1 - (slo_violations / total_intervals)
```

**Scaling Stability**:
```
scaling_actions = count(scaling_decision != 0)
thrashing_index = count(scale_up followed by scale_down within 5 minutes)
```

**Overall Score**:
```python
score = slo_attainment / (cost * (1 + 0.1 * thrashing_index))
# Penalize both cost and instability
```

### Comparison Baselines

**Baseline 1: Reactive Threshold**
```go
if P99_TTFT > SLO * 1.2:
    scaleUp()
elif P99_TTFT < SLO * 0.7 AND cooldown_elapsed:
    scaleDown()
```

**Baseline 2: Queueing Model + MILP**
```python
# Predict arrivals using exponential smoothing
predicted_arrival = alpha * current_arrival + (1 - alpha) * history

# Compute replicas using Little's Law
required_replicas = predicted_arrival * avg_service_time / utilization_target

# Solve MILP for optimal replica count under cost constraints
```

**Baseline 3: Kubernetes HPA (Horizontal Pod Autoscaler)**
```yaml
target_utilization: 70%
scale_up_policy: 100% increase, max 2 pods per 60s
scale_down_policy: 50% decrease, max 1 pod per 180s
```

### Sim-to-Real Transfer

**Phase 1: BLIS Evolution**
- Evolve policies on simulated workloads
- Measure: cost, SLO attainment, stability

**Phase 2: Shadow Deployment**
- Deploy evolved policy in WVA alongside baseline
- Compare decisions (no actual scaling)
- Measure prediction accuracy

**Phase 3: A/B Testing**
- Route 10% traffic to evolved autoscaler
- Gradually increase to 100%
- Monitor real costs and SLOs

**Phase 4: Comparison**
- Run evolved vs baselines on production workloads
- Measure sim-to-real transfer quality
- Identify aspects where simulation was insufficient

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
