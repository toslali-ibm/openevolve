# Evolving a Smarter LLM Router with OpenEvolve

## The Problem

When you serve an LLM across multiple GPU instances, a **router** decides which instance handles each request. A good router balances two goals:

- **Cache affinity**: Send a request to the instance that already has its prefix cached (faster prefill)
- **Load balance**: Send it to the least-busy instance (shorter queue wait)

The baseline router uses fixed equal weights for both goals. It never adapts. We want to find a router that adjusts its strategy based on the request and system state.

## What is OpenEvolve?

OpenEvolve is an open-source implementation of Google DeepMind's AlphaEvolve. It uses LLMs to **evolve code** through iterative mutation and selection — like biological evolution, but for programs.

Instead of a human writing a better router, we let LLMs generate hundreds of candidate routers, test each one in simulation, keep the best, and repeat.

## The Pipeline

```
                    ┌─────────────┐
                    │  LLM sees   │
                    │ best programs│
                    │ + system    │
                    │   prompt    │
                    └──────┬──────┘
                           │ generates mutated code
                           ▼
                    ┌─────────────┐
                    │  Write new  │
                    │ routing.go  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Build BLIS │
                    │  simulator  │
                    └──────┬──────┘
                           │
                           ▼
               ┌───────────┴───────────┐
               │  Run 3 workloads      │
               │  (cache_warmup,       │
               │   load_spikes,        │
               │   multiturn)          │
               └───────────┬───────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Compute     │
                    │ score +     │
                    │ test        │
                    │ hypotheses  │
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ Store in    │
                    │ population  │
                    │ database    │
                    └──────┬──────┘
                           │ next iteration
                           └──────→ back to top
```

Each iteration takes about 30 seconds of simulation plus LLM generation time. We run 100 iterations.

## What Gets Evolved

Only a small block of Go code inside the router's scoring function (marked with `EVOLVE-BLOCK-START` / `EVOLVE-BLOCK-END`). The LLM can add conditional logic, change how scores are combined, or use signals the baseline ignores.

## The System Prompt

The LLM gets a detailed system prompt explaining:
- What scorers are available (prefix-affinity, load-balance, queue-depth, etc.)
- What signals it can read from each request (input size, SLO class, session ID)
- What signals it can read from each instance (queue depth, cache hit rate, load)
- Validated strategy hints (e.g., "large inputs benefit from cache, small inputs benefit from load-balance")
- Anti-patterns to avoid (don't zero out scores, guard divisions)

This guides the LLM toward productive mutations rather than random changes.

## Hypothesis-Driven Evolution

Each mutation must include a **hypothesis** — a testable prediction:

```go
// HYPOTHESIS-1: Input-length routing reduces cache_warmup latency
// MECHANISM-1: Small inputs don't benefit from prefix cache; load-balance avoids imbalance
// EXPECT-1: cache_warmup_e2e_ms < 5000
```

After evaluation, each hypothesis is marked CONFIRMED or REFUTED. Results accumulate in a **knowledge base** that the LLM sees in future iterations. This creates a feedback loop: the LLM learns what works and what doesn't, building on confirmed strategies and avoiding refuted ones.

## Models and Ensemble

We use two LLMs in an ensemble:
- **Gemini 2.5 Flash** (60% weight): Fast, generates most mutations
- **Gemini 2.5 Pro** (40% weight): Higher quality, provides diversity

The ensemble votes on which mutations to try. This balances speed with quality and reduces the chance of getting stuck.

## Island-Based Evolution

The population is split into 3 **islands** — independent sub-populations that evolve separately. Periodically, the best programs migrate between islands.

Why? Without islands, the population converges to one local optimum. Islands explore different regions of the solution space. When a breakthrough happens on one island, migration spreads it to others.

Settings: 100 programs total, 15 in the elite archive, 65% exploitation (refine best) / 35% exploration (try new things).

## The 3 Workloads

Each candidate router is tested on 3 workloads that stress different aspects:

| Workload | What it tests | Key tension |
|----------|--------------|-------------|
| **cache_warmup** | Can the router use load-balance when prefix-affinity creates imbalance? | 3 prefix groups across 4 instances. Prefix-affinity leaves one instance idle. |
| **load_spikes** | Can the router avoid the prefix-affinity trap during traffic bursts? | 50% of traffic shares one prefix. Prefix-affinity concentrates it on one instance (+113% latency). |
| **multiturn** | Can the router keep sessions pinned for cache hits? | Multi-turn sessions with large prefixes (4096 tokens). Bouncing sessions costs 72ms per cache miss. |

No single static strategy wins all three. The router must be **adaptive** — use load-balance for small requests but prefix-affinity for large cached sessions.

## Scoring

```
score = -0.5 * avg_mean_latency - 0.5 * avg_p95_latency
```

Lower latency = higher score (less negative). Averaged equally across all 3 workloads.

## What We Expect to Find

Our hand-crafted "oracle" router proves the search space contains a solution **28% better** than baseline on cache_warmup. It uses a simple rule: if the request has >1000 input tokens, keep prefix-affinity; otherwise, use load-balance.

We expect OpenEvolve to discover this pattern — or something better — within 50-100 iterations.
