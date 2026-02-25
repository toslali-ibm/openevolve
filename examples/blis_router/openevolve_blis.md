# Evolving a Smarter LLM Router with OpenEvolve

## The Problem

When you serve an LLM across multiple GPU instances, a **router** decides which instance handles each request. A good router balances two goals:

- **Cache affinity**: Send a request to the instance that already has its prefix cached (faster prefill)
- **Load balance**: Send it to the least-busy instance (shorter queue wait)

The baseline router uses fixed equal weights for both goals. It never adapts. We want to find a router that adjusts its strategy based on the request and system state.

## What is OpenEvolve?

OpenEvolve is an open-source implementation of Google DeepMind's AlphaEvolve. It uses LLMs to **evolve code** through iterative mutation and selection — like biological evolution, but for programs.

Instead of a human writing a better router, we let LLMs generate hundreds of candidate routers, test each one in simulation, keep the best, and repeat.

---

## System Architecture

The diagram below shows every component, what it produces, and how data flows through the system. Components inside the dashed box are OpenEvolve internals; components outside are BLIS-specific.

```
 BLIS-SPECIFIC (you write these)          OPENEVOLVE INTERNALS (framework)
 ────────────────────────────────   ──────────────────────────────────────────────────────────

                                    ┌──────────────────────────────────────────────────────────┐
                                    │                    CONTROLLER                            │
 ┌──────────────┐                   │  Orchestrates the full evolution loop.                   │
 │ config.yaml  │──────────────────▸│  For each iteration:                                    │
 │              │  LLM models,      │    1. Ask Database for parent + inspirations             │
 │ - models     │  population       │    2. Ask Prompt Sampler to build LLM prompt             │
 │ - islands    │  settings,        │    3. Ask LLM Ensemble to generate mutated code          │
 │ - strategy   │  evolution        │    4. Ask Evaluator to score the mutation                │
 │              │  parameters       │    5. Store result back in Database                      │
 └──────────────┘                   │    6. Save checkpoints every N iterations                │
                                    └───────────────────────┬──────────────────────────────────┘
                                                            │
                     ┌──────────────────────────────────────┼──────────────────────────┐
                     │                                      │                          │
                     ▼                                      ▼                          ▼
 ┌──────────────────────────────┐   ┌───────────────────────────────┐  ┌──────────────────────────┐
 │     DATABASE (MAP-Elites)    │   │       PROMPT SAMPLER          │  │      LLM ENSEMBLE        │
 │                              │   │                               │  │                          │
 │ 3 islands × ~33 programs     │   │ Builds context for the LLM:  │  │ Weighted model selection: │
 │ 15-program elite archive     │   │                               │  │  Claude Sonnet 4.5 (70%) │
 │                              │   │ ┌─────────────────────────┐   │  │  Claude Opus 4   (30%) │
 │ Sampling:                    │   │ │ system_prompt            │   │  │                          │
 │  65% exploit (best programs) │   │ │ + parent code & metrics  │   │  │ Temperature: 1.0         │
 │  35% explore (diverse ones)  │   │ │ + top 3 best programs    │   │  │ (high creativity)        │
 │                              │   │ │ + 2 diverse programs     │   │  │                          │
 │ Periodic migration between   │   │ │ + evolution history      │   │  │ Generates diff-based     │
 │ islands spreads breakthroughs│   │ │ + artifacts:             │   │  │ SEARCH/REPLACE blocks    │
 │                              │   │ │   - knowledge_base  ◂───┼───┼──┼─ (from hypothesis.py)    │
 │ Produces:                    │   │ │   - workload_results     │   │  │                          │
 │  → parent program            │   │ └─────────────────────────┘   │  │ Produces:                │
 │  → inspiration programs      │   │                               │  │  → mutated Go code       │
 └──────────────────────────────┘   │ Produces:                     │  │  → embedded hypotheses   │
                                    │  → formatted LLM prompt       │  └──────────────────────────┘
                                    └───────────────────────────────┘
```

---

## Full Iteration Flow

One iteration of the evolution loop, showing every artifact that is produced and consumed:

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  ITERATION N                                                           │
 │                                                                        │
 │  ┌─── SAMPLE ────────────────────────────────────────────────────┐     │
 │  │                                                               │     │
 │  │  Database selects:                                            │     │
 │  │   • Parent program (from one island, biased toward elites)    │     │
 │  │   • 3 top programs (best scores across all islands)           │     │
 │  │   • 2 diverse programs (different feature-space regions)      │     │
 │  │                                                               │     │
 │  │  Produces: parent code, parent metrics, inspiration code      │     │
 │  └──────────────────────────────┬────────────────────────────────┘     │
 │                                 │                                      │
 │                                 ▼                                      │
 │  ┌─── BUILD PROMPT ─────────────────────────────────────────────┐     │
 │  │                                                               │     │
 │  │  Assembles context the LLM needs to generate a good mutation: │     │
 │  │                                                               │     │
 │  │  SYSTEM PROMPT (from config.yaml)                             │     │
 │  │   ├── Problem description & scorer API                        │     │
 │  │   ├── Available signals (request fields, instance snapshots)  │     │
 │  │   ├── Validated winning strategies & anti-patterns            │     │
 │  │   ├── Workload descriptions (what each workload tests)        │     │
 │  │   └── Hypothesis format requirements                          │     │
 │  │                                                               │     │
 │  │  USER PROMPT (assembled by sampler)                           │     │
 │  │   ├── Current parent code with EVOLVE-BLOCK markers           │     │
 │  │   ├── Parent's metrics: score, per-workload latencies         │     │
 │  │   ├── Top 3 programs' code + metrics (for inspiration)        │     │
 │  │   ├── 2 diverse programs' code (for exploration)              │     │
 │  │   ├── Artifact: hypothesis_knowledge_base ◂── accumulated     │     │
 │  │   │   knowledge from ALL prior iterations (confirmed,         │     │
 │  │   │   refuted, inconclusive strategies with deltas)           │     │
 │  │   │   THIS IS THE KEY FEEDBACK: LLM sees what hypotheses      │     │
 │  │   │   worked/failed before and builds on confirmed ones        │     │
 │  │   └── Artifact: workload_results ◂── per-workload latencies   │     │
 │  │                                                               │     │
 │  │  Produces: formatted messages for LLM                         │     │
 │  └──────────────────────────────┬────────────────────────────────┘     │
 │                                 │                                      │
 │                                 ▼                                      │
 │  ┌─── LLM GENERATES ───────────────────────────────────────────┐      │
 │  │                                                               │     │
 │  │  LLM reads the prompt and produces:                           │     │
 │  │   • Mutated Go code for the EVOLVE-BLOCK                     │     │
 │  │   • 1-3 embedded hypotheses (HYPOTHESIS / MECHANISM / EXPECT) │     │
 │  │                                                               │     │
 │  │  Output format (diff-based):                                  │     │
 │  │   SEARCH: <old code lines>                                    │     │
 │  │   REPLACE: <new code lines with hypothesis comments>          │     │
 │  │                                                               │     │
 │  │  Produces: evolved_program.py (Python wrapper with Go inside) │     │
 │  └──────────────────────────────┬────────────────────────────────┘     │
 │                                 │                                      │
 │                                 ▼                                      │
 │  ┌─── EVALUATE (evaluator.py) ──────────────────────────────────┐     │
 │  │                                                               │     │
 │  │  Step 1: EXTRACT Go code from Python wrapper                  │     │
 │  │           └─▸ routing.go (written to inference-sim/sim/)      │     │
 │  │                                                               │     │
 │  │  Step 2: BUILD the Go simulator                               │     │
 │  │           └─▸ go build -o simulation_worker main.go           │     │
 │  │           └─▸ Build failure → score = -100000 (dead end)      │     │
 │  │                                                               │     │
 │  │  Step 3: RUN 3 workloads in sequence                          │     │
 │  │           ┌──────────────┬────────────────┬──────────────┐    │     │
 │  │           │ cache_warmup │  load_spikes   │  multiturn   │    │     │
 │  │           │ 1000 req/s   │  1000 req/s    │  150 req/s   │    │     │
 │  │           │ 5s, 5000 req │  5s, 5000 req  │  10s,1500 req│    │     │
 │  │           └──────┬───────┴───────┬────────┴──────┬───────┘    │     │
 │  │                  │               │               │            │     │
 │  │                  ▼               ▼               ▼            │     │
 │  │            JSON metrics    JSON metrics    JSON metrics       │     │
 │  │            (e2e, p95,      (e2e, p95,      (e2e, p95,        │     │
 │  │             reqs, ttft)     reqs, ttft)     reqs, ttft)      │     │
 │  │                                                               │     │
 │  │  Step 4: SCORE                                                │     │
 │  │           score = -0.5 * avg_e2e_ms - 0.5 * avg_p95_ms       │     │
 │  │           (lower latency → higher score → less negative)      │     │
 │  │                                                               │     │
 │  │  Step 5: TEST HYPOTHESES (hypothesis.py)                      │     │
 │  │           Parse HYPOTHESIS/MECHANISM/EXPECT from Go comments  │     │
 │  │           Compare EXPECT thresholds against actual metrics     │     │
 │  │           Mark each: CONFIRMED or REFUTED                     │     │
 │  │           Update persistent hypothesis_ledger.json             │     │
 │  │           Regenerate knowledge_base summary from ledger        │     │
 │  │                                                               │     │
 │  │  Produces:                                                    │     │
 │  │   → EvaluationResult (metrics + artifacts)                    │     │
 │  │   → Artifact: workload_results (per-workload breakdown)       │     │
 │  │   → Artifact: hypothesis_results (verdicts for this iteration)│     │
 │  │   → Artifact: hypothesis_knowledge_base (cumulative summary)  │     │
 │  └──────────────────────────────┬────────────────────────────────┘     │
 │                                 │                                      │
 │                                 ▼                                      │
 │  ┌─── STORE ────────────────────────────────────────────────────┐     │
 │  │                                                               │     │
 │  │  Database receives the scored program:                        │     │
 │  │   • Code, metrics, artifacts, parent_id, generation           │     │
 │  │   • Placed into parent's island in MAP-Elites grid            │     │
 │  │   • If best overall → saved to best_program.py                │     │
 │  │   • Artifacts stored: small (<10KB) in DB, large on disk      │     │
 │  │                                                               │     │
 │  │  The knowledge_base artifact is now available for the         │     │
 │  │  NEXT iteration's prompt ──▸ closes the learning loop         │     │
 │  └──────────────────────────────────────────────────────────────┘     │
 │                                                                        │
 └────────────────────────────────────────────────────────────────────────┘
                    │
                    │ next iteration
                    ▼
              back to SAMPLE
```

---

## The Hypothesis-Driven Discovery Loop

This is the key innovation that turns black-box evolution into interpretable, directed research. The diagram below shows how hypotheses flow through the system:

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                    HYPOTHESIS LIFECYCLE                                  │
 │                                                                         │
 │                                                                         │
 │   ┌────────────────┐        ┌─────────────────────────────────────┐     │
 │   │                │        │  LLM GENERATES hypothesis in code   │     │
 │   │  KNOWLEDGE     │        │                                     │     │
 │   │  BASE          │───────▸│  // HYPOTHESIS-1: Input-length      │     │
 │   │  (artifact)    │ guides │  //   routing reduces cache_warmup  │     │
 │   │                │ next   │  // MECHANISM-1: Small inputs don't │     │
 │   │  Confirmed:    │ hypo-  │  //   benefit from prefix cache     │     │
 │   │   "input-len   │ thesis │  // EXPECT-1: cache_warmup_e2e_ms   │     │
 │   │    routing"    │        │  //   < 5000                        │     │
 │   │  Refuted:      │        │                                     │     │
 │   │   "load-only   │        │  inputLen := len(req.InputTokens)   │     │
 │   │    for all"    │        │  if inputLen > 1000 { ... }         │     │
 │   │                │        └──────────────────┬──────────────────┘     │
 │   └───────▲────────┘                           │                        │
 │           │                                    │ code is evaluated       │
 │           │                                    ▼                        │
 │           │                 ┌─────────────────────────────────────┐     │
 │           │                 │  EVALUATOR runs 3 workloads         │     │
 │           │                 │                                     │     │
 │           │                 │  Actual results:                    │     │
 │           │                 │   cache_warmup_e2e_ms = 4923        │     │
 │           │                 │   load_spikes_e2e_ms  = 4950        │     │
 │           │                 │   multiturn_e2e_ms    = 2103        │     │
 │           │                 └──────────────────┬──────────────────┘     │
 │           │                                    │                        │
 │           │                                    ▼                        │
 │           │                 ┌─────────────────────────────────────┐     │
 │           │                 │  HYPOTHESIS TESTING                  │     │
 │           │                 │  (hypothesis.py)                     │     │
 │           │                 │                                     │     │
 │           │                 │  EXPECT: cache_warmup < 5000        │     │
 │           │                 │  ACTUAL: 4923                       │     │
 │           │                 │  VERDICT: CONFIRMED                  │     │
 │           │                 │  DELTA vs BASELINE: -5.9%            │     │
 │           │                 └──────────────────┬──────────────────┘     │
 │           │                                    │                        │
 │           │                                    ▼                        │
 │           │                 ┌─────────────────────────────────────┐     │
 │           │                 │  HYPOTHESIS LEDGER                   │     │
 │           │                 │  (hypothesis_ledger.json)            │     │
 │           │                 │                                     │     │
 │           │                 │  Persistent JSON file that           │     │
 │           │                 │  accumulates ALL hypothesis          │     │
 │           │                 │  results across ALL iterations.      │     │
 │           │                 │                                     │     │
 │           │                 │  Entry: {                            │     │
 │           │                 │    iteration: 15,                    │     │
 │           │                 │    score: -2350.45,                  │     │
 │           │                 │    hypotheses: [{                    │     │
 │           │                 │      claim: "Input-length routing",  │     │
 │           │                 │      verdict: "CONFIRMED",           │     │
 │           │                 │      delta: -5.9%                    │     │
 │           │                 │    }]                                │     │
 │           │                 │  }                                   │     │
 │           │                 └──────────────────┬──────────────────┘     │
 │           │                                    │                        │
 │           │                                    ▼                        │
 │           │                 ┌─────────────────────────────────────┐     │
 │           │                 │  KNOWLEDGE BASE REGENERATION         │     │
 │           │                 │                                     │     │
 │           │                 │  Aggregates all ledger entries by    │     │
 │           │                 │  (metric, claim) pair:               │     │
 │           │                 │                                     │     │
 │           │                 │  === CONFIRMED STRATEGIES ===        │     │
 │           │    returned     │  [cache_warmup] Input-length routing │     │
 │           └─────────────────│    confirmed 3/3, avg_delta=-5.2%   │     │
 │             as artifact     │                                     │     │
 │             for next        │  === REFUTED STRATEGIES ===          │     │
 │             iteration       │  [multiturn] Load-only for all      │     │
 │                             │    confirmed 0/2, avg_delta=+5.5%   │     │
 │                             └─────────────────────────────────────┘     │
 │                                                                         │
 └──────────────────────────────────────────────────────────────────────────┘
```

**Why this matters:** Standard evolutionary search is a black box — code mutates, score changes, but nobody knows *why*. With hypothesis-driven evolution, the LLM embeds causal claims, the evaluator tests them, and the accumulated knowledge base guides future mutations. The LLM can reason: "input-length routing is confirmed 3 out of 3 times, so I'll build on it; load-only was refuted, so I'll avoid it."

---

## What Lives Where: OpenEvolve vs. BLIS-Specific

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │  BLIS-SPECIFIC COMPONENTS (you write these for your problem)        │
 │                                                                     │
 │  initial_program.py    Python wrapper containing the Go EVOLVE-BLOCK│
 │  evaluator.py          Build Go, run 3 workloads, parse metrics     │
 │  hypothesis.py         Parse/test/ledger hypothesis comments        │
 │  config.yaml           Models, population size, system prompt       │
 │  system_prompt          Domain knowledge: scorers, signals, hints   │
 │  inference-sim/         The Go simulator binary + workload YAMLs    │
 │  validate_workloads.py  One-time: prove workloads are sensitive     │
 │  oracle_program.py      One-time: prove search space has solutions  │
 └───────────────────────────────────┬─────────────────────────────────┘
                                     │ plugs into
                                     ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │  OPENEVOLVE FRAMEWORK (reusable across problems)                    │
 │                                                                     │
 │  controller.py     Main loop: sample → prompt → generate → eval    │
 │  database.py       MAP-Elites grid + 3 islands + elite archive      │
 │  iteration.py      Single worker: runs one mutation cycle           │
 │  llm/ensemble.py   Weighted multi-model selection + async gen       │
 │  prompt/sampler.py Template-based prompt assembly with artifacts    │
 │  evaluator.py      Loads your evaluator.py, runs it, stores results│
 │  checkpoint/       Saves full state for resume                      │
 └──────────────────────────────────────────────────────────────────────┘

 ┌──────────────────────────────────────────────────────────────────────┐
 │  OUTSIDE THE LOOP (run once, before evolution)                      │
 │                                                                     │
 │  validate_workloads.py   Tests 5 routing configs × 3 workloads     │
 │                          Proves no single static strategy wins all  │
 │                          Establishes baseline metrics               │
 │                                                                     │
 │  oracle_program.py       Hand-crafted adaptive router               │
 │                          Proves 28% improvement is achievable       │
 │                          Sets the ceiling for what evolution targets │
 │                                                                     │
 │  baseline_metrics.json   Cached on first eval, reused thereafter    │
 │                          Baseline for hypothesis delta comparisons  │
 └──────────────────────────────────────────────────────────────────────┘
```

---

## How Hypotheses are Generated

The LLM doesn't randomly mutate code. It follows a structured scientific process, guided by the system prompt and accumulated knowledge:

**1. The LLM reads the knowledge base** — a summary of what worked and what didn't across all prior iterations. Example:

```
=== CONFIRMED STRATEGIES ===
  [cache_warmup_e2e_ms] Input-length routing (confirmed 3/3, avg_delta=-5.2%)
    mechanism: Small inputs use load-balance, large use prefix-affinity

=== REFUTED STRATEGIES ===
  [multiturn_e2e_ms] Load-only for all inputs (confirmed 0/2, avg_delta=+5.5%)
    mechanism: Sessions bounce between instances, losing KV cache
```

**2. The LLM formulates a hypothesis** based on confirmed strategies, avoiding refuted ones:

```go
// HYPOTHESIS-1: Combining input-length routing with CacheHitRate
//   awareness improves cache_warmup beyond simple threshold
// MECHANISM-1: For small inputs, route to instances with warm caches
//   (CacheHitRate > 0.3) even if load is slightly higher, since cache
//   hit avoids full prefill cost
// EXPECT-1: cache_warmup_e2e_ms < 4800
```

**3. The LLM writes code that implements the hypothesis**, modifying only the EVOLVE-BLOCK.

**4. After evaluation**, the hypothesis is tested: actual `cache_warmup_e2e_ms` compared against the `< 4800` threshold. Verdict: CONFIRMED or REFUTED.

**5. The ledger accumulates** this result. Next iteration, the LLM sees the updated knowledge base and refines further.

---

## How Experiments are Conducted

Each candidate router is tested identically on 3 workloads that stress different routing tradeoffs:

```
              ┌─────────────────────────────────────────────────┐
              │          BLIS CLUSTER SIMULATOR                  │
              │          (4 GPU instances, Go binary)            │
              │                                                  │
              │   ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
              │   │ Inst 0 │ │ Inst 1 │ │ Inst 2 │ │ Inst 3 │  │
              │   │ KV=$   │ │ KV=$   │ │ KV=$   │ │ KV=$   │  │
              │   └────────┘ └────────┘ └────────┘ └────────┘  │
              │          ▲                                       │
              │          │ evolved routing logic decides         │
              │          │ which instance gets each request      │
              │                                                  │
              └─────────────────────────────────────────────────┘

 Workload 1: CACHE WARMUP                Workload 2: LOAD SPIKES
 ─────────────────────────                ─────────────────────────
 1000 req/s, 5s, 5000 reqs               1000 req/s, 5s, 5000 reqs

 3 prefix groups (~30% each)              50% heavy-hitter (prefix=512,
 + 15% no-prefix batch traffic               bursty gamma CV=3)
 All inputs < 1000 tokens                 25% realtime (no prefix)
                                          25% different prefix group
 TRAP: prefix-affinity maps
 3 groups → 3 instances,                  TRAP: prefix-affinity puts
 leaving instance 4 idle                  50% traffic on ONE instance

 SOLUTION: load-balance for               SOLUTION: avoid heavy-hitter
 small inputs (26% improvement)           concentration

 Workload 3: MULTI-TURN SESSIONS
 ─────────────────────────────────
 150 req/s, 10s, 1500 reqs

 40% coding (prefix=4096, 5 rounds)
 25% chat (prefix=2048, 4 rounds)
 15% QA (prefix=1024, 3 rounds)
 20% single-turn realtime

 TRAP: load-balance bounces sessions
 between instances, losing KV cache
 (72ms miss cost per coding request)

 SOLUTION: session stickiness via
 prefix-affinity (5.5% better than load-only)
```

**Scoring**: `score = -0.5 * avg_e2e_ms - 0.5 * avg_p95_ms` averaged equally across all 3 workloads. Lower latency = higher (less negative) score.

**No single static strategy wins all three.** The router must be adaptive — use load-balance for small requests but prefix-affinity for large cached sessions.

---

## Island-Based Evolution

The population is split into 3 **islands** — independent sub-populations that evolve separately. Periodically, the best programs migrate between islands.

```
  Island 0                Island 1                Island 2
  ┌──────────────┐        ┌──────────────┐        ┌──────────────┐
  │ ~33 programs │        │ ~33 programs │        │ ~33 programs │
  │              │        │              │        │              │
  │ Exploring:   │        │ Exploring:   │        │ Exploring:   │
  │ input-length │        │ CacheHitRate │        │ SLO-aware    │
  │ thresholds   │        │ weighting    │        │ adjustments  │
  │              │        │              │        │              │
  └──────┬───────┘        └──────┬───────┘        └──────┬───────┘
         │                       │                       │
         └───────── migration ───┴─── migration ─────────┘
                  (spreads breakthroughs)

  Elite Archive (15 programs) — best across all islands, always available
```

Why? Without islands, the population converges to one local optimum. Islands explore different regions of the solution space. When a breakthrough happens on one island, migration spreads it to others.

Settings: 100 programs total, 15 in the elite archive, 65% exploitation (refine best) / 35% exploration (try new things).

## Models and Ensemble

We use two LLMs in an ensemble:
- **Claude Sonnet 4.5** (70% weight): Fast, generates most mutations
- **Claude Opus 4** (30% weight): Higher quality, provides diversity

Each iteration randomly selects one model based on weights. This balances speed with quality and reduces the chance of getting stuck.

---

## What Gets Evolved

Only a small block of Go code inside the router's scoring function (marked with `EVOLVE-BLOCK-START` / `EVOLVE-BLOCK-END`). The LLM can add conditional logic, change how scores are combined, or use signals the baseline ignores.

```go
// EVOLVE-BLOCK-START
// <hypotheses go here>
// <adaptive routing logic goes here>
// EVOLVE-BLOCK-END
```

The surrounding Go code (scorer functions, request parsing, instance snapshots) is fixed. The LLM only mutates the decision logic.

---

## Artifact Pipeline

Artifacts are the side-channel through which the evaluator passes structured data back to the LLM on the next iteration:

```
 Evaluator produces                    Sampler consumes
 ─────────────────                     ─────────────────

 workload_results ──────────────────▸  Shown to LLM: per-workload
   {cache_warmup: {e2e: 4923,           latency breakdown so it
    p95: 7145, reqs: 5000}, ...}        knows which workload to target

 hypothesis_results ────────────────▸  Shown to LLM: verdicts for
   "H1 [CONFIRMED]: cache_warmup        THIS iteration's hypotheses
    < 5000, actual 4923 (-5.9%)"

 hypothesis_knowledge_base ─────────▸  Shown to LLM: CUMULATIVE
   "=== CONFIRMED STRATEGIES ===         summary across ALL iterations.
    Input-length routing (3/3)..."       This is the primary learning
                                         mechanism.
```

Small artifacts (<10KB) are stored inline in the database. Large artifacts are written to disk and referenced by path.

---

## Output Directory Structure

```
examples/blis_router/openevolve_output/
├── baseline_metrics.json            Cached baseline (computed once, reused)
├── hypothesis_ledger.json           All hypothesis results across all iterations
├── best_program.py                  Best program found so far
├── run_output.log                   Full evolution log
├── blis_router_evolution/           MAP-Elites database
│   └── programs/
│       └── {uuid}.json              Individual program records
└── checkpoints/
    ├── checkpoint_5/
    │   ├── metadata.json
    │   ├── best_program_info.json
    │   └── programs/
    └── checkpoint_10/
        └── ...
```

---

## Concrete Example: Iteration 15

To make the flow tangible, here is what happens in a single iteration:

**Sample**: Database picks Program-42 (score=-2280) from Island 0 as parent. Also selects Program-5 (top 1, score=-2250, uses input-length routing) and Program-18 (top 2, score=-2260, uses CacheHitRate) as inspiration.

**Prompt**: The sampler assembles:
- System prompt with scorer API, signals, and strategy hints
- Parent code and its metrics (cache_warmup=5120, load_spikes=4950, multiturn=2105)
- Top programs' code for inspiration
- Knowledge base: "input-length routing confirmed 3/3, avg_delta=-5.2%"

**Generate**: Claude Sonnet 4.5 reads the prompt and produces a SEARCH/REPLACE diff that:
- Adds a hypothesis: "Combining input-length + CacheHitRate reduces latency"
- Writes code: `if inputLen > 1200 && snap.CacheHitRate > 0.3 { keep prefix } else { load-balance }`

**Evaluate**: The evaluator extracts the Go code, builds the simulator, and runs 3 workloads. Results: cache_warmup=4950ms, load_spikes=4820ms, multiturn=2080ms. Score=-5075 (improvement of +85 over parent).

**Test Hypotheses**: EXPECT `avg_e2e_ms < 2850` → actual was 3950 → REFUTED. But the delta vs baseline is -1.5%, so the code is still kept because the *score* improved.

**Store**: Program-71 enters the database with its metrics and artifacts. The hypothesis ledger gains one entry. The regenerated knowledge base now includes: "CacheHitRate + input-length: 1 attempt, 0 confirmed (INCONCLUSIVE)". Next iteration sees this and adjusts.

---

## What We Expect to Find

Our hand-crafted "oracle" router proves the search space contains a solution **28% better** than baseline on cache_warmup. It uses a simple rule: if the request has >1000 input tokens, keep prefix-affinity; otherwise, use load-balance.

We expect OpenEvolve to discover this pattern — or something better — within 50-100 iterations.
