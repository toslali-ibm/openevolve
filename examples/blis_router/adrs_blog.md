# ADRS Blog Post Analysis: Guidance for BLIS Router OpenEvolve Experiment

Source: [Let the Barbarians In: How AI Can Accelerate Systems Research](https://ucbskyadrs.github.io/blog/let-the-barbarians-in-how-ai-can-accelerate-system/)
Paper: [arXiv:2512.14806](https://arxiv.org/abs/2512.14806)
Repo: [UCB-ADRS/ADRS](https://github.com/UCB-ADRS/ADRS)

---

## Background

The UCB Sky Computing Lab tested 3 evolutionary frameworks (OpenEvolve, GEPA, ShinkaEvolve)
across 10 systems use cases with 2 models (GPT-5, Gemini-3.0). Each run was capped at
100 iterations with 3 repetitions per framework-model combination. Most solutions were
discovered in under 8 hours at <$30 cost.

**OpenEvolve was the most versatile framework** — 9/20 best solutions across both models.
It uses 1 LLM call per iteration (cheapest of the 3 frameworks).

### 10 Use Cases Tested

1. **Can't Be Late (CBL)** — Single-region spot instance scheduling
2. **CBL-Multi-Region** — Multi-region spot scheduling with migration
3. **EPLB** — MoE expert placement load balancing (13x speedup)
4. **LLM-SQL** — Row/column reordering for KV cache hit rate (3.9x faster)
5. **TXN** — Transaction scheduling to minimize conflicts (60% better than greedy)
6. **Telemetry Repair** — Fix buggy network telemetry counters
7. **Cloudcast** — Multi-cloud data transfer cost optimization
8. **Prism** — Model-to-GPU placement cost optimization
9. **MAS** — Multi-agent system collaboration
10. **NS3** — Datacenter TCP congestion control

---

## 1. Models

### What ADRS Found

- **GPT-5**: Longer, modular code with edge-case handling. Better for **multi-technique
  problems** (EPLB, Cloudcast, TXN scheduling). Average 461 LOC.
- **Gemini-3.0**: Shorter, minimal code. Better for **simpler algorithmic tasks**
  (CBL, Telemetry Repair). Average 289 LOC.
- **OpenEvolve**: Most versatile — 4 top results with GPT-5, 5 with Gemini-3.0.
- GEPA favored GPT-5 (4 vs 2). ShinkaEvolve favored Gemini-3.0 (5 vs 3).

### ADRS Configs Seen in Repo

| Use Case | Primary Model (weight) | Secondary Model (weight) |
|---|---|---|
| EPLB | gemini-2.5-flash (0.8) | gemini-2.5-flash-lite (0.2) |
| Can't-Be-Late | gemini-2.5-pro (0.8) | gpt-5 (0.2) |
| LLM-SQL | o3 (0.8) | gemini-2.5-pro (0.2) |
| TXN scheduling | gemini-2.5-pro (0.8) | o3 (0.2) |

**Pattern**: Primary model gets 0.8 weight, secondary gets 0.2.

### Our Current Config
```yaml
primary_model: aws/claude-sonnet-4-5  (0.7)
secondary_model: aws/claude-opus-4-6  (0.3)
```

### Recommendation

- BLIS router is a **multi-technique problem** (SLO awareness, input-length classification,
  session detection, overload penalties) — maps to GPT-5's strength profile.
- Consider **Gemini 2.5 Pro as primary (0.8)** with a secondary model (0.2) — this is the
  most common ADRS pattern and reduces cost.
- If keeping Claude: change weights to **0.8/0.2** to match ADRS patterns.
- Key insight: "Conduct preliminary evolution runs with multiple models to select an
  effective LLM" based on problem characteristics.

---

## 2. Temperature & Sampling

### ADRS Configs

| Use Case | Temperature | Top-p | Max Tokens |
|---|---|---|---|
| EPLB | 0.7 | 0.95 | 131072 |
| Can't-Be-Late | 0.9 | 0.95 | 32000 |
| LLM-SQL | 0.7 | 0.95 | 32000 |
| TXN scheduling | 1.0 | 0.95 | 10000 |

### Our Current Config
```yaml
temperature: 1
top_p: null  # Can't use both on Bedrock/Claude
max_tokens: 32000
```

### Recommendation

- Most ADRS use cases use **temperature 0.7–0.9** with **top_p: 0.95**.
- Temperature 1.0 is the highest they use (only TXN scheduling).
- For Bedrock/Claude (can't combine temp + top_p): our temperature=1 is aggressive but
  within range.
- If switching to Gemini: use **temperature: 0.7, top_p: 0.95**.
- **max_tokens: 32000** matches their configs for similar-sized problems.

---

## 3. Prompt Engineering — "Less is More" (Critical Finding)

### The Core Insight

> "The way a problem is framed dictates the quality of the solution. Rigorously defined
> specifications are a prerequisite for effective search."

> "Less is often more" — excessive hints cause **premature convergence**; insufficient
> guidance reduces search efficiency.

### Three-Part Prompt Structure

Recommended structure:
1. **Problem definition** — what needs to be optimized
2. **Evaluation criteria** — how solutions are scored
3. **Context** — APIs, available signals, constraints

### Two-Phase Hint Injection (Major Finding)

**Phase 1**: Generic, problem-only prompt with no specific algorithmic hints. Let the
framework explore freely.

**Phase 2**: Inject targeted algorithmic hints when the best score plateaus after N
iterations.

**Evidence:**
- **EPLB**: Generic prompt plateaued at iteration 12 → injected "proportional allocation
  strategies" hint → +28% improvement (total +60%)
- **Cloudcast**: Plateaued at iteration 8 → injected "shared-tree multicast routing
  topology" hint → +48% improvement

### Abstraction Level

> "Restricting high-level library APIs encourages algorithmic discovery over trivial
> optimizations. Minimal interfaces with essential helper classes focus search effectively."

### Our Current Prompt

Our `system_message` is **very detailed** — 7 strategy directions, code structure hints,
anti-patterns, workload-specific descriptions with exact parameters. This is essentially
a Phase 2 prompt from the start, which may cause premature convergence.

### Recommendation

**Phase 1 prompt** (use for first ~20-30 iterations): Keep:
- Problem definition (what the EVOLVE-BLOCK does, scorer pipeline)
- Available signals (scorers, request fields, snapshot fields)
- Evaluation criteria (3 workloads, normalized scoring)
- Anti-patterns (compile safety)
- Brief workload descriptions (names + what they stress)

Remove for Phase 1:
- All 7 strategy directions (these become Phase 2 hints)
- Code structure hints (the `if req.SLOClass == "critical"` examples)
- Detailed workload parameter descriptions

**Phase 2 prompt** (inject when score plateaus): Add back:
- Strategy directions 1-7
- Code structure hints
- Workload-specific detailed descriptions

### ADRS Example: Can't-Be-Late Prompt Structure

Their prompt for Can't-Be-Late includes:
- Prohibits specific anti-patterns ("Uniform Progress" pattern)
- Requires specific mechanisms ("adaptive alpha/L", "tail-sealing logic")
- Suggests candidate approaches ("OD Budget", "Pulse Repair", "Regime Switching")

This is a Phase 2 prompt — they only used it after identifying what exploration needed guidance.

---

## 4. Evaluation & Scoring

### ADRS Principles

> "A flawed evaluator is the primary cause of flawed solutions. The AI will exploit
> loopholes to maximize its score."

**Concrete exploit examples:**
| Problem | Exploit | Solution |
|---|---|---|
| MAS | Bypassed evaluation stage | Multi-signal evaluation |
| EPLB | Zero-weighted 97% of experts | Enforce minimum replica requirement |
| Prism | Deleted memory limit variable | Diff-based edits restrict scope |
| Cloudcast | Omitted data partitions | Limit changed lines of code |

### Scoring Best Practices

- **Smooth, deterministic functions** preferred
- **Penalized scores** for invalid programs (don't just score 0 — preserve learning signal)
- **Combined metrics** with clear weighting: `0.95 × PHR + 0.05 × 1/(1+runtime)`
- **Cascade evaluation** with progressive thresholds: `[0.5, 0.75, 0.9]`
- **Diverse test sets** — single patterns lead to overfitting

### Our Current Scoring

```python
# Per-workload normalized improvement
imp = (baseline_mean - actual_mean) / baseline_mean * 100.0
score = mean(improvements)
score -= regression_count * 10.0  # penalty per regressing workload
```

### Recommendation

- Our scoring is smooth and deterministic — good.
- **Regression penalty of 10.0 is very harsh** — one 1.5% regression wipes out 30%
  improvement elsewhere. Consider **2-3 points** or a **continuous penalty** proportional
  to regression magnitude.
- Consider enabling **cascade evaluation** (currently disabled):
  - Stage 1: Compile check (fast, 5s timeout)
  - Stage 2: Run 1 workload (medium, 20s)
  - Stage 3: Run all 3 workloads (full, 60s)
  - This saves evaluation time on programs that don't compile.
- Our EVOLVE-BLOCK restriction already prevents the edit-scope exploits they saw.

---

## 5. Population & Islands

### ADRS Configs

| Use Case | Population | Archive | Islands | Migration Interval | Exploit/Explore |
|---|---|---|---|---|---|
| EPLB | 1000 | 100 | 5 | 50 | 0.7/0.2 |
| Can't-Be-Late | 60 | 30 | 6 | — | 0.2/0.5 |
| LLM-SQL | 50 | 20 | 3 | — | 0.7/0.2 |
| TXN scheduling | 1000 | 100 | 5 | 10 | 0.7/0.2 |

### Our Current Config
```yaml
population_size: 100
archive_size: 15
num_islands: 3
exploitation_ratio: 0.65
exploration_ratio: 0.35
```

### Recommendation

- **archive_size: 15 → 25** (we're below most ADRS configs)
- **exploitation_ratio: 0.65 → 0.7** (matches their most common setting)
- Population of 100 is reasonable for 100 iterations.
- 3 islands is fine (matches LLM-SQL).
- Consider increasing **num_top_programs: 3 → 3** (matches) and
  **num_diverse_programs: 2 → 2** (matches — OpenEvolve shows "parent + top diverse
  archive programs").

---

## 6. Diverse Seeds — Major Missing Feature

### ADRS Finding

> "We recommend seeding evolution with three to five diverse baselines, potentially
> generated using coding assistants."

**Ablation study (LLM-SQL with OpenEvolve):**
- Single seed (all islands with SOTA): combined score capped at **0.74**
- Diverse seeds (ranging from basic designs to stronger heuristics): achieved **0.7755**
- "Only runs that included diverse seeds had final scores higher than 0.74."

### Our Current Setup

Single `initial_program.py` (uniform seed across all islands).

### Recommendation — Biggest Missed Opportunity

Create **3-5 diverse initial programs** for island seeding:

1. **Baseline** (current): scorer loop + argmax, no modifications
2. **Load-balance dominant**: recompute all scores as 85% load-balance + 15% prefix
3. **SLO-aware**: branch on req.SLOClass (critical → load, sheddable → load, else → keep)
4. **Input-length aware**: branch on len(req.InputTokens) threshold
5. **Session-aware**: branch on req.SessionID (session → keep affinity, else → load-balance)

Each island starts with a different seed, encouraging diverse exploration strategies.

Note: This may require OpenEvolve framework changes to support per-island initial programs.

---

## 7. Framework Comparison

### OpenEvolve vs GEPA vs ShinkaEvolve

| Aspect | OpenEvolve | GEPA | ShinkaEvolve |
|---|---|---|---|
| **Best solutions** | 9/20 | 6/20 | 8/20 |
| **Cost per iteration** | 1 LLM call | ~1 LLM + 6-11 evals | 1 LLM + 12 per 10 iters |
| **Parent selection** | Explore/archive/random | Pareto frontier | Weighted Pareto + novelty |
| **Context shown to LLM** | Parent + top diverse archive | Parent + minibatch traces | Parent + 6 archive + meta-recs |
| **Avg program length** | 262 LOC | 406 LOC | 458 LOC |
| **Model versatility** | Best (4 GPT + 5 Gemini) | GPT-biased (4 vs 2) | Gemini-biased (5 vs 3) |

OpenEvolve's simplicity (1 LLM call, shortest programs) makes it the most cost-effective.

---

## 8. General Best Practices

### Specification Axis
- Three-part prompt: problem + evaluation criteria + context
- Choose abstraction matching optimization goal
- Start with diverse, domain-specialized seeds (3-5)
- Two-phase hint injection: generic first, targeted when plateaued

### Evaluation Axis
- Enforce diverse test sets with edge cases
- Multi-signal evaluation prevents gaming
- Diff-based edits over full rewrites initially
- Smooth scoring with penalties for invalids
- Model selection: GPT-5 for multi-technique; Gemini-3 for simple tasks

### Feedback Axis
- Calibrate feedback granularity — actionable guidance without overfitting
- Learn from failure patterns for search direction
- Meta-feedback helps guide search when accurate
- Encode resilience for non-deterministic evaluators

### When ADRS Works Best
- **Isolated changes** within single components (our EVOLVE-BLOCK fits this)
- **Reliable evaluations** with unambiguous ranking (our deterministic simulator fits)
- **Efficient evaluations** — simulator-based preferred (our Go sim is fast, ~5-10s per eval)

### Cross-Domain Discovery

The paper found models identifying techniques from unrelated fields:
- **Hamilton's Apportionment** (political science) for load balancing
- **Social Choice Theory** for transaction scheduling

This suggests our prompt should NOT over-specify strategies — let the LLM explore
cross-domain analogies.

---

## Priority Changes for Our Config

| Priority | Change | Rationale |
|---|---|---|
| **HIGH** | Simplify prompt (Phase 1: problem+context only, no strategy hints) | "Less is more" — avoids premature convergence |
| **HIGH** | Create 3-5 diverse seed programs for island seeding | Ablation: 0.74 → 0.7755 with diverse seeds |
| **MEDIUM** | Soften regression penalty (10.0 → 2-3 or continuous) | Less punitive, smoother scoring |
| **MEDIUM** | Increase archive_size (15 → 25), exploitation_ratio (0.65 → 0.7) | Better exploitation of found solutions |
| **LOW** | Consider Gemini 2.5 Pro as primary (0.8) + secondary (0.2) | Cost reduction, ADRS-tested pattern |
| **LOW** | Enable cascade evaluation (compile check → 1 workload → all 3) | Saves wasted eval time on broken programs |
| **LOW** | Model weights 0.8/0.2 instead of 0.7/0.3 | Matches ADRS patterns |
| **LOW** | Implement two-phase hint injection (plateau detection) | Requires OpenEvolve framework support |
