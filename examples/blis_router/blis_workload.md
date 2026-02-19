# BLIS Workload Analysis & Optimization

## Problem Statement

After 100 iterations of OpenEvolve with powerful LLMs generating sophisticated routing algorithms (incorporating CacheHitRate, adaptive weights, etc.), the improvement is only **~1ms** (2177ms → 2175ms). This suggests the workloads don't create meaningful tradeoffs where routing optimization matters.

## Current Workload Analysis

### What We Have (4 workloads, 1000 requests each)

| Workload | Rate | Clients | Prefix Groups | Issue |
|----------|------|---------|---------------|-------|
| high_load | 300 req/s | 2 | None | High load but no prefix sharing |
| high_prefix | 80 req/s | 3 | 2 groups | Low load, prefix benefit invisible |
| mixed | 150 req/s | 4 | 1 group | Moderate, not enough contention |
| servegen | 200 req/s | 2 | 1 group | Standard workload |

### Why Routing Optimization Shows No Benefit

1. **Insufficient Contention**: 4 instances handling 80-300 req/s easily → no queuing pressure
2. **Prefix Sharing Too Simple**: Only 1-2 prefix groups → affinity routing trivially optimal
3. **No Multi-Turn Context Growth**: Static requests → no KV pressure buildup
4. **Homogeneous Request Sizes**: Similar input/output distributions → no scheduling opportunities
5. **Short Simulation Horizon**: 1000 requests complete in seconds → no long-term dynamics

## Inference-Sim Workload Capabilities

### Available Features (Currently Underutilized)

| Feature | Description | Routing Impact |
|---------|-------------|----------------|
| **Multi-Turn Reasoning** | `reasoning.multi_turn.max_rounds` with `context_growth: "accumulate"` | Creates growing KV pressure over time |
| **Prefix Groups** | `prefix_group: "name"` assigns shared prefix tokens | Affinity routing affects cache hit rates |
| **Lifecycle Windows** | `lifecycle.windows` for client activity periods | Dynamic load patterns |
| **Network Latency** | `network.rtt_ms` and `bandwidth_mbps` | Different client sensitivity |
| **SLO Classes** | `slo_class: realtime/interactive/batch` | Priority-based routing |
| **Gamma Arrivals** | `arrival.process: gamma` with `cv: 3.5` | Bursty traffic creates queues |

### Request Structure

```yaml
clients:
  - id: "chat-session"
    prefix_group: "system-prompt-A"    # Shared prefix for cache affinity
    reasoning:
      multi_turn:
        max_rounds: 5                   # 5 conversation turns
        think_time_us: 100000           # 100ms between turns
        context_growth: "accumulate"    # Context grows each turn
```

## Proposed Workload Expansion

### Design Principles

1. **Create Real Tradeoffs**: Load vs cache affinity, latency vs throughput
2. **Force Non-Trivial Routing**: Many clients, many prefix groups, varying sizes
3. **Build KV Pressure**: Multi-turn conversations that grow context
4. **Mix Request Types**: Small realtime + large batch = scheduling matters

---

### Workload 1: Multi-Tenant Chat Platform

**Goal**: Simulate production chat with many tenants sharing system prompts

```yaml
# workload_multi_tenant_chat.yaml
version: "1"
seed: 42
category: reasoning
aggregate_rate: 200.0
num_requests: 5000

clients:
  # Tenant A - Customer Support (shared prompt)
  - id: "tenant-a-support"
    tenant_id: "tenant-a"
    slo_class: "realtime"
    rate_fraction: 0.15
    streaming: true
    arrival:
      process: poisson
    input_distribution:
      type: gaussian
      params: { mean: 150, std_dev: 50, min: 20, max: 500 }
    output_distribution:
      type: exponential
      params: { mean: 100 }
    prefix_group: "tenant-a-system"
    reasoning:
      multi_turn:
        max_rounds: 4
        think_time_us: 200000
        context_growth: "accumulate"

  # Tenant A - Analytics (same prefix, different pattern)
  - id: "tenant-a-analytics"
    tenant_id: "tenant-a"
    slo_class: "batch"
    rate_fraction: 0.10
    streaming: false
    arrival:
      process: gamma
      cv: 3.0
    input_distribution:
      type: pareto_lognormal
      params: { alpha: 1.5, xm: 100, mu: 6.0, sigma: 1.0, mix_weight: 0.3 }
    output_distribution:
      type: exponential
      params: { mean: 500 }
    prefix_group: "tenant-a-system"

  # Tenant B - Coding Assistant (different prefix)
  - id: "tenant-b-coding"
    tenant_id: "tenant-b"
    slo_class: "interactive"
    rate_fraction: 0.20
    streaming: true
    arrival:
      process: gamma
      cv: 2.0
    input_distribution:
      type: gaussian
      params: { mean: 300, std_dev: 150, min: 50, max: 2000 }
    output_distribution:
      type: exponential
      params: { mean: 200 }
    prefix_group: "tenant-b-coding-system"
    reasoning:
      multi_turn:
        max_rounds: 3
        think_time_us: 500000
        context_growth: "accumulate"

  # Tenant C - Document Processing (large batch)
  - id: "tenant-c-docs"
    tenant_id: "tenant-c"
    slo_class: "batch"
    rate_fraction: 0.25
    streaming: false
    arrival:
      process: gamma
      cv: 4.0
    input_distribution:
      type: pareto_lognormal
      params: { alpha: 1.2, xm: 200, mu: 7.0, sigma: 1.5, mix_weight: 0.4 }
    output_distribution:
      type: exponential
      params: { mean: 800 }
    prefix_group: "tenant-c-doc-system"

  # Global shared prompt users (cross-tenant)
  - id: "shared-api-users"
    tenant_id: "shared"
    slo_class: "interactive"
    rate_fraction: 0.30
    streaming: false
    arrival:
      process: poisson
    input_distribution:
      type: gaussian
      params: { mean: 100, std_dev: 40, min: 10, max: 300 }
    output_distribution:
      type: exponential
      params: { mean: 80 }
    prefix_group: "global-api-prompt"
```

**Why This Creates Tradeoffs**:
- 5 prefix groups → affinity routing must balance across 4 instances
- Multi-turn with context growth → KV blocks fill up over time
- Mix of realtime (low latency) + batch (high throughput) → priority routing matters
- 5000 requests → longer simulation shows cache dynamics

---

### Workload 2: Prefix Cache Pressure Test

**Goal**: Force routing to choose between load balancing and cache affinity

```yaml
# workload_prefix_pressure.yaml
version: "1"
seed: 42
category: language
aggregate_rate: 400.0
num_requests: 8000

clients:
  # 8 prefix groups, each wants affinity to one instance
  # But only 4 instances → must share, creating conflicts

  - id: "prefix-group-1"
    slo_class: "interactive"
    rate_fraction: 0.125
    arrival: { process: gamma, cv: 2.5 }
    input_distribution:
      type: gaussian
      params: { mean: 400, std_dev: 100, min: 100, max: 1000 }
    output_distribution:
      type: exponential
      params: { mean: 150 }
    prefix_group: "system-prompt-1"

  - id: "prefix-group-2"
    slo_class: "interactive"
    rate_fraction: 0.125
    arrival: { process: gamma, cv: 2.5 }
    input_distribution:
      type: gaussian
      params: { mean: 400, std_dev: 100, min: 100, max: 1000 }
    output_distribution:
      type: exponential
      params: { mean: 150 }
    prefix_group: "system-prompt-2"

  # ... repeat for groups 3-8 with different prefix_group names

  - id: "prefix-group-3"
    slo_class: "interactive"
    rate_fraction: 0.125
    arrival: { process: gamma, cv: 2.5 }
    input_distribution:
      type: gaussian
      params: { mean: 400, std_dev: 100, min: 100, max: 1000 }
    output_distribution:
      type: exponential
      params: { mean: 150 }
    prefix_group: "system-prompt-3"

  - id: "prefix-group-4"
    slo_class: "interactive"
    rate_fraction: 0.125
    arrival: { process: gamma, cv: 2.5 }
    input_distribution:
      type: gaussian
      params: { mean: 400, std_dev: 100, min: 100, max: 1000 }
    output_distribution:
      type: exponential
      params: { mean: 150 }
    prefix_group: "system-prompt-4"

  - id: "prefix-group-5"
    slo_class: "batch"
    rate_fraction: 0.125
    arrival: { process: gamma, cv: 3.0 }
    input_distribution:
      type: gaussian
      params: { mean: 600, std_dev: 200, min: 100, max: 1500 }
    output_distribution:
      type: exponential
      params: { mean: 300 }
    prefix_group: "system-prompt-5"

  - id: "prefix-group-6"
    slo_class: "batch"
    rate_fraction: 0.125
    arrival: { process: gamma, cv: 3.0 }
    input_distribution:
      type: gaussian
      params: { mean: 600, std_dev: 200, min: 100, max: 1500 }
    output_distribution:
      type: exponential
      params: { mean: 300 }
    prefix_group: "system-prompt-6"

  - id: "prefix-group-7"
    slo_class: "realtime"
    rate_fraction: 0.125
    arrival: { process: poisson }
    input_distribution:
      type: gaussian
      params: { mean: 200, std_dev: 50, min: 50, max: 400 }
    output_distribution:
      type: exponential
      params: { mean: 50 }
    prefix_group: "system-prompt-7"

  - id: "prefix-group-8"
    slo_class: "realtime"
    rate_fraction: 0.125
    arrival: { process: poisson }
    input_distribution:
      type: gaussian
      params: { mean: 200, std_dev: 50, min: 50, max: 400 }
    output_distribution:
      type: exponential
      params: { mean: 50 }
    prefix_group: "system-prompt-8"
```

**Why This Creates Tradeoffs**:
- 8 prefix groups vs 4 instances → cannot give each group its own instance
- Router must decide: group similar prefixes? balance load? prioritize realtime?
- High rate (400 req/s) creates queue pressure
- CacheHitRate becomes meaningful signal

---

### Workload 3: Context Growth Stress Test

**Goal**: Multi-turn conversations that build KV pressure over time

```yaml
# workload_context_growth.yaml
version: "1"
seed: 42
category: reasoning
aggregate_rate: 150.0
num_requests: 3000

clients:
  # Long coding sessions with growing context
  - id: "long-coding-session"
    tenant_id: "developers"
    slo_class: "interactive"
    rate_fraction: 0.40
    streaming: true
    arrival:
      process: gamma
      cv: 2.0
    input_distribution:
      type: gaussian
      params: { mean: 200, std_dev: 100, min: 50, max: 1000 }
    output_distribution:
      type: exponential
      params: { mean: 300 }
    prefix_group: "coding-assistant"
    reasoning:
      multi_turn:
        max_rounds: 8          # 8 turns = significant context
        think_time_us: 300000  # 300ms think time
        context_growth: "accumulate"

  # Document Q&A with context accumulation
  - id: "document-qa"
    tenant_id: "analysts"
    slo_class: "interactive"
    rate_fraction: 0.30
    streaming: false
    arrival:
      process: poisson
    input_distribution:
      type: gaussian
      params: { mean: 500, std_dev: 200, min: 100, max: 2000 }
    output_distribution:
      type: exponential
      params: { mean: 200 }
    prefix_group: "doc-qa-system"
    reasoning:
      multi_turn:
        max_rounds: 5
        think_time_us: 500000
        context_growth: "accumulate"

  # Short burst requests (no multi-turn)
  - id: "quick-queries"
    tenant_id: "api-users"
    slo_class: "realtime"
    rate_fraction: 0.30
    streaming: false
    arrival:
      process: gamma
      cv: 4.0
    input_distribution:
      type: gaussian
      params: { mean: 80, std_dev: 30, min: 10, max: 200 }
    output_distribution:
      type: exponential
      params: { mean: 40 }
    prefix_group: "api-system"
```

**Why This Creates Tradeoffs**:
- Multi-turn with up to 8 rounds → context can grow to thousands of tokens
- Router must consider: route back to same instance (context cached) vs balance load
- KVUtilization becomes critical signal as contexts grow
- Mix of long sessions + short bursts creates scheduling pressure

---

### Workload 4: Burst + Steady State Mix

**Goal**: Bursty batch jobs competing with steady realtime traffic

```yaml
# workload_burst_steady.yaml
version: "1"
seed: 42
category: language
aggregate_rate: 250.0
num_requests: 6000

clients:
  # Steady realtime traffic (must maintain SLO)
  - id: "realtime-chat-1"
    slo_class: "realtime"
    rate_fraction: 0.15
    streaming: true
    arrival:
      process: poisson
    input_distribution:
      type: gaussian
      params: { mean: 100, std_dev: 40, min: 20, max: 300 }
    output_distribution:
      type: exponential
      params: { mean: 60 }
    prefix_group: "chat-system"

  - id: "realtime-chat-2"
    slo_class: "realtime"
    rate_fraction: 0.15
    streaming: true
    arrival:
      process: poisson
    input_distribution:
      type: gaussian
      params: { mean: 120, std_dev: 50, min: 20, max: 350 }
    output_distribution:
      type: exponential
      params: { mean: 80 }
    prefix_group: "chat-system"

  # Extremely bursty batch (storms)
  - id: "batch-storm-1"
    slo_class: "batch"
    rate_fraction: 0.25
    streaming: false
    arrival:
      process: gamma
      cv: 5.0              # Very bursty!
    input_distribution:
      type: pareto_lognormal
      params: { alpha: 1.3, xm: 200, mu: 6.5, sigma: 1.2, mix_weight: 0.35 }
    output_distribution:
      type: exponential
      params: { mean: 400 }
    prefix_group: "batch-system-1"

  - id: "batch-storm-2"
    slo_class: "batch"
    rate_fraction: 0.25
    streaming: false
    arrival:
      process: gamma
      cv: 5.0
    input_distribution:
      type: pareto_lognormal
      params: { alpha: 1.3, xm: 200, mu: 6.5, sigma: 1.2, mix_weight: 0.35 }
    output_distribution:
      type: exponential
      params: { mean: 400 }
    prefix_group: "batch-system-2"

  # Interactive API (moderate)
  - id: "api-interactive"
    slo_class: "interactive"
    rate_fraction: 0.20
    streaming: false
    arrival:
      process: gamma
      cv: 2.0
    input_distribution:
      type: gaussian
      params: { mean: 150, std_dev: 60, min: 30, max: 500 }
    output_distribution:
      type: exponential
      params: { mean: 120 }
    prefix_group: "api-system"
```

**Why This Creates Tradeoffs**:
- CV=5.0 gamma creates severe bursts → queues spike
- Realtime traffic needs protection from batch storms
- Router must: isolate realtime? absorb bursts? balance across instances?
- Adaptive weights based on cluster state become valuable

---

## Expected Improvements with New Workloads

| Scenario | Naive Router | Optimized Router | Why |
|----------|--------------|------------------|-----|
| Multi-tenant chat | High tail latency | Lower p95 | Multi-turn affinity + SLO prioritization |
| Prefix pressure | Cache thrashing | Better hit rates | Smart prefix→instance mapping |
| Context growth | KV eviction delays | Stable performance | Route to same instance when context cached |
| Burst + steady | Realtime SLO violation | Protected realtime | Load-aware burst absorption |

## Implementation Checklist

- [ ] Create `workload_multi_tenant_chat.yaml`
- [ ] Create `workload_prefix_pressure.yaml`
- [ ] Create `workload_context_growth.yaml`
- [ ] Create `workload_burst_steady.yaml`
- [ ] Update evaluator to use new workloads
- [ ] Run baseline with current routing
- [ ] Run OpenEvolve with new workloads
- [ ] Compare improvement percentages

## Summary

Current workloads are too simple to stress routing decisions. The proposed workloads create real tradeoffs:

1. **Many prefix groups (8) vs few instances (4)** → routing must choose wisely
2. **Multi-turn with context growth** → affinity to cached context matters
3. **Mixed SLO classes with bursts** → prioritization and isolation matter
4. **Higher request counts (3000-8000)** → long-term dynamics visible

With these workloads, a routing algorithm that uses CacheHitRate, adapts weights dynamically, and considers KVUtilization should show **5-15% latency improvement** over static baselines.
