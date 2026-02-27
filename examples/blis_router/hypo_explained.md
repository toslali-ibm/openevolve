# How Hypothesis-Driven Evolution Works

## Pipeline Flow (V2 — Score-Ranked, Island-Local)

> **Status**: V2 is the target design. See [V1 Design](#v1-design-current-implementation)
> at the bottom for the current implementation and its known issues.

### Step 1: System Prompt — Hypothesis Instructions

When `hypothesis_driven: true` in config, the system message sent to the LLM is
appended with `HYPOTHESIS_INSTRUCTIONS_TEMPLATE` (`openevolve/prompt/templates.py`).

This tells the LLM:
- Write 1-3 hypotheses as comments at the TOP of the EVOLVE-BLOCK
- Each hypothesis needs 3 lines: HYPOTHESIS-N, MECHANISM-N, EXPECT-N
- EXPECT uses `<` for lower-is-better metrics, `>` for higher-is-better
- Learn from CONFIRMED hypotheses in top-scoring programs on the island
- Avoid patterns from REFUTED hypotheses in worst-scoring programs
- Set thresholds informed by baseline values

When `hypothesis_driven: false`, this template is NOT appended — the LLM gets
no instructions about hypotheses whatsoever.

### Step 2: LLM Generates Code with Hypothesis Comments

The LLM writes structured comments before the evolved code:

```go
// EVOLVE-BLOCK-START
// HYPOTHESIS-1: Adaptive weight adjustment based on input length reduces avg latency
// MECHANISM-1: Short requests have minimal cache benefit; routing by load-balance improves throughput
// EXPECT-1: cache_warmup_e2e_ms < 4200
// HYPOTHESIS-2: Overload penalty prevents hot-spotting under bursty traffic
// MECHANISM-2: Quadratic penalty on high-load instances redistributes requests
// EXPECT-2: load_spikes_e2e_ms < 3350

// ... actual evolved code ...
// EVOLVE-BLOCK-END
```

Typical count: **2-3 hypotheses per program** (prompt says "at least 1, max 3").

### Step 3: rescue_hypotheses() — Diff Mode Recovery

In diff-based evolution, the LLM responds with SEARCH/REPLACE blocks.
Some LLMs (especially Gemini) place hypothesis comments OUTSIDE the diff blocks
as a preamble. `apply_diff()` only keeps REPLACE content, so hypotheses are lost.

`rescue_hypotheses()` (`openevolve/hypothesis.py:68`) recovers them:
1. Check if code already has hypothesis comments → if yes, no-op
2. Extract hypothesis comment lines from the raw LLM response
3. Inject them after the first `EVOLVE-BLOCK-START` marker in the code

Only runs when `hypothesis_driven: true` (gated in `iteration.py` and
`process_parallel.py`).

### Step 4: Evaluator — Parse, Test, Update Ledger (V2)

The evaluator runs the evolved program, gets actual metrics, then:

**a) Parse** — `parse_hypotheses(code, valid_metrics)` extracts structured data:
  - Matches `// HYPOTHESIS-N:`, `// MECHANISM-N:`, `// EXPECT-N: metric > threshold`
  - Only returns complete hypotheses (all 3 fields present)
  - Skips hypotheses referencing unknown metric names

**b) Test** — `test_hypotheses(hypotheses, actual_metrics, baseline_metrics)`:
  - For each hypothesis, compares actual metric value against EXPECT threshold
  - `EXPECT metric > threshold` → CONFIRMED if actual > threshold, else REFUTED
  - `EXPECT metric < threshold` → CONFIRMED if actual < threshold, else REFUTED
  - Missing metric → INCONCLUSIVE
  - Also computes delta vs baseline as a percentage

**c) Update Ledger** — `update_ledger(ledger, results, score, ledger_path, program_id, island)`:
  - Appends a new entry to the persistent JSON ledger file
  - Each entry contains: timestamp, overall score, **program_id**, **island**, list of hypothesis verdicts
  - Ledger file is per-run (stored in `OPENEVOLVE_OUTPUT_DIR`)
  - Ledger grows monotonically — entries are never removed
  - `program_id` and `island` enable filtering by island at prompt time

**d) Store artifact** — evaluator stores **only its own verdicts**:
  - `artifacts["hypothesis_results"]` = formatted text of this program's hypothesis verdicts
  - The evaluator does **NOT** generate or store a knowledge base summary (that's done at prompt time now)

The entire hypothesis pipeline only runs when `HYPOTHESIS_DRIVEN=true` env var
is set (propagated from `config.hypothesis_driven` by the controller).

### Step 5: Fresh Island-Local Knowledge at Prompt Time (V2)

When a program is selected as a **parent** for a new iteration, the worker
computes a **fresh** knowledge base from the ledger — not a stale artifact.

`generate_island_knowledge_summary(ledger, top_program_ids, worst_program_ids)`
in `openevolve/hypothesis.py` works as follows:

1. **Filter** ledger entries to only those matching the provided program IDs
   (top-scoring and worst-scoring programs from the current island).

2. **Sort** top entries by score descending (best first), worst by score ascending.

3. **Display individual verdicts** — no aggregation by claim string. Each
   hypothesis is shown with its verdict, actual value, threshold, and delta.
   The LLM does pattern recognition across these examples.

4. **Cap at top_n per section** (default 5) to bound prompt size.

5. **Append baseline values** (metrics from the initial program).

The result is a plain text summary like:
```
=== STRATEGIES FROM TOP-SCORING PROGRAMS ===
  [CONFIRMED] Adaptive weight by input length reduces avg latency
  (EXPECT cache_warmup_e2e_ms < 4200, ACTUAL 3850.0, delta=-7.2% vs baseline)
    mechanism: Short requests routed by load-balance, long by prefix affinity

=== STRATEGIES FROM WORST-SCORING PROGRAMS ===
  [REFUTED] Aggressive quadratic penalty on overloaded instances
  (EXPECT load_spikes_e2e_ms < 3350, ACTUAL 4100.0, delta=+22.1% vs baseline)
    mechanism: Quadratic penalties cause routing oscillation

=== BASELINE VALUES ===
  avg_e2e_ms: 2610.5
  combined_score: -3860.2
```

This is computed in `iteration.py` / `process_parallel.py` and injected as a
synthetic `hypothesis_knowledge_base` artifact alongside the parent's own artifacts.

### Step 6: Prompt Assembly — Two-Channel Knowledge (V2)

When a program is selected as a **parent** for a new iteration:

1. Worker fetches parent's artifacts from the database snapshot
   (`process_parallel.py:157`) — this contains the parent's **own** hypothesis
   verdicts (from Step 4d)
2. Worker computes **fresh island-local knowledge** from the ledger (Step 5)
   and injects it as `parent_artifacts["hypothesis_knowledge_base"]`
3. Artifacts are passed to `build_prompt(program_artifacts=parent_artifacts)`
4. `_render_artifacts()` renders ALL artifacts as markdown code blocks
   in the `{artifacts}` section of the user message template

So the LLM sees **two channels**:
- **`hypothesis_results`** — the parent's own hypothesis verdicts (what it tried, what happened)
- **`hypothesis_knowledge_base`** — fresh island-local summary of what worked/failed
  across the best and worst programs on this island

Plus:
- **System message**: hypothesis format instructions
- **User message**: parent code, metrics, evolution history

The LLM is expected to use this feedback to:
- **Build on** confirmed strategies from top-scoring island programs
- **Avoid** patterns from worst-scoring island programs
- **Set thresholds** informed by baseline values
- **Refine** the parent's own approach based on its specific verdicts

## Summary (V2)

```
Iteration N:
  LLM sees:  system prompt (hypothesis instructions)
           + user prompt (parent code, metrics, history)
           + parent's artifact: hypothesis_results (its own verdicts)
           + FRESH artifact: hypothesis_knowledge_base
                (top 5 from best island programs,
                 top 5 from worst island programs,
                 baseline values)

  LLM writes: evolved code with 1-3 HYPOTHESIS/MECHANISM/EXPECT comments

  Evaluator:  runs code → gets actual metrics
           → parse_hypotheses() extracts hypotheses from code
           → test_hypotheses() checks each EXPECT against actual
           → update_ledger() appends verdicts with program_id + island
           → stores ONLY own verdicts as artifact["hypothesis_results"]

  Worker (prompt time):
           → loads ledger from disk (always fresh)
           → gets top 5 + worst 5 program IDs from current island
           → generate_island_knowledge_summary() produces ranked display
           → injects as synthetic artifact["hypothesis_knowledge_base"]

Iteration N+1:
  Parent selected → worker computes fresh knowledge → LLM sees
  latest island-wide intelligence + parent's own history → cycle continues
```

At most **10 hypothesis verdicts + baseline values** are shown to the LLM at any time
(5 from top programs + 5 from worst programs), regardless of how large the ledger grows.

---

## V1 Design (Current Implementation)

> This section documents the V1 design for reference. V2 above fixes the
> issues described here.

### How V1 Works

In V1, the evaluator calls `generate_knowledge_base_summary(ledger)` after
testing hypotheses and stores the result as `artifacts["hypothesis_knowledge_base"]`
on the child program. When that program is later selected as a parent, its
artifact is passed verbatim to the LLM.

### Known Issues with V1

**1. Dead aggregation** — `generate_knowledge_base_summary()` aggregates
hypotheses by exact `(metric, claim)` string match. Since LLM-generated
claims almost never repeat verbatim across iterations, every hypothesis
has `total=1`. This means:
  - The REFUTED bucket (requires `total >= 2`) is **always empty**
  - All failed hypotheses fall into INCONCLUSIVE instead
  - Multi-trial aggregation is effectively a dead feature

**2. Stale knowledge** — The knowledge base is frozen at the time the parent
was evaluated. If the parent was evaluated at iteration 5 but selected as
parent at iteration 50, the LLM sees 45-iteration-old intelligence.

**3. Global scope breaks island isolation** — OpenEvolve uses island-based
MAP-Elites where programs, metrics, and inspirations are all island-local.
But V1's knowledge base is computed from the **global** ledger, leaking
strategies across island boundaries.

**4. No lineage attribution** — V1 shows "what strategies exist" but not
"which programs used them and how well they scored". The LLM can't
distinguish between a strategy from the best program and one from the worst.
