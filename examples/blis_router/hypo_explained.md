# How Hypothesis-Driven Evolution Works

## V3 — Inline RESULT Comments (Zero Infrastructure)

### Core Idea

Hypotheses and their verdicts live **in the code itself**. After evaluation,
the framework injects a `RESULT-N` line after each `EXPECT-N`. When this code
is later shown to the LLM (as parent, top program, or inspiration), the
hypotheses + results are visible in context with the code that produced them.

No ledger. No knowledge base. No artifacts. No prompt-time queries.
OpenEvolve's existing parent/top-program/inspiration mechanisms carry the
hypothesis intelligence automatically.

### Pipeline Flow

#### Step 1: System Prompt — Hypothesis Instructions

When `hypothesis_driven: true` in config, the system message sent to the LLM is
appended with `HYPOTHESIS_INSTRUCTIONS_TEMPLATE` (`openevolve/prompt/templates.py`).

This tells the LLM:
- Write 1-3 hypotheses as comments at the TOP of the EVOLVE-BLOCK
- Each hypothesis needs 3 lines: HYPOTHESIS-N, MECHANISM-N, EXPECT-N
- EXPECT uses `<` for lower-is-better metrics, `>` for higher-is-better
- Look at RESULT-N lines in parent/top programs to see what worked and what failed
- Build on CONFIRMED strategies, avoid REFUTED strategies
- Do NOT write RESULT lines — they are added automatically after evaluation

When `hypothesis_driven: false`, this template is NOT appended.

#### Step 2: LLM Generates Code with Hypothesis Comments

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

#### Step 3: rescue_hypotheses() — Diff Mode Recovery

Some LLMs (especially Gemini) place hypothesis comments OUTSIDE the diff blocks
as a preamble. `rescue_hypotheses()` (`openevolve/hypothesis.py`) recovers them:
1. Check if code already has hypothesis comments → if yes, no-op
2. Extract hypothesis comment lines from the raw LLM response
3. Inject them after the first `EVOLVE-BLOCK-START` marker in the code

Only runs when `hypothesis_driven: true`.

#### Step 4: Evaluator Returns Metrics (Hypothesis-Unaware)

The evaluator runs the evolved program and returns metrics. It has **no
hypothesis code whatsoever** — no parsing, no testing, no ledger, no knowledge
base. Just `EvaluationResult(metrics=..., artifacts=...)`.

#### Step 5: Framework Injects RESULT Lines

After evaluation, `iteration.py` / `process_parallel.py` calls
`inject_result_comments(child_code, child_metrics)`. This function:

1. Scans each line for `EXPECT-N: metric_name < threshold` patterns
2. Looks up `metric_name` in the actual evaluation metrics
3. Determines verdict: CONFIRMED / REFUTED / INCONCLUSIVE
4. Injects a `RESULT-N` comment line immediately after the `EXPECT-N` line
5. Preserves the same indentation and comment prefix (// for Go, # for Python)

The code now looks like:

```go
// EVOLVE-BLOCK-START
// HYPOTHESIS-1: Adaptive weight adjustment based on input length reduces avg latency
// MECHANISM-1: Short requests have minimal cache benefit; routing by load-balance improves throughput
// EXPECT-1: cache_warmup_e2e_ms < 4200
// RESULT-1: CONFIRMED (actual=3850.0)
// HYPOTHESIS-2: Overload penalty prevents hot-spotting under bursty traffic
// MECHANISM-2: Quadratic penalty on high-load instances redistributes requests
// EXPECT-2: load_spikes_e2e_ms < 3350
// RESULT-2: REFUTED (actual=4100.0)

// ... actual evolved code ...
// EVOLVE-BLOCK-END
```

This modified code is stored in the database as the child program.

#### Step 6: OpenEvolve Carries It Forward

When this program is later shown to the LLM, the hypotheses + results are
visible in the code because OpenEvolve already shows:

| What LLM sees | Source | Hypothesis info |
|----------------|--------|-----------------|
| **Parent code** | Selected parent | Parent's HYPOTHESIS + RESULT lines |
| **Top programs** | Best on island | Their HYPOTHESIS + RESULT lines |
| **Inspirations** | Diverse programs | Their HYPOTHESIS + RESULT lines |

The LLM naturally sees:
- What strategies top-scoring programs tried (CONFIRMED)
- What strategies failed (REFUTED)
- The causal reasoning (MECHANISM) in context with the code that implements it

No special handling needed. Island isolation, migration, parent selection — all
work exactly as OpenEvolve already implements them.

### Summary

```
Iteration N:
  LLM sees:  system prompt (hypothesis instructions + RESULT-N documentation)
           + parent code (with HYPOTHESIS/EXPECT/RESULT from parent's eval)
           + top programs (with their HYPOTHESIS/EXPECT/RESULT)
           + inspirations (with their HYPOTHESIS/EXPECT/RESULT)

  LLM writes: evolved code with 1-3 HYPOTHESIS/MECHANISM/EXPECT comments

  Framework: rescue_hypotheses() if diff mode
           → evaluator runs code → returns metrics (hypothesis-unaware)
           → inject_result_comments(child_code, metrics)
                stamps RESULT-N after each EXPECT-N
           → stores modified code in database

Iteration N+1:
  This program may be selected as parent/top/inspiration
  → its code (with RESULT lines) is shown to the LLM → cycle continues
```

### What's NOT Needed

- **No ledger** — verdicts live in the code, not a separate JSON file
- **No knowledge base generation** — the LLM reads results directly from code
- **No artifacts for hypotheses** — evaluators don't touch hypotheses at all
- **No prompt-time queries** — code carries its own hypothesis history
- **No island filtering** — OpenEvolve's existing island isolation handles it
- **No aggregation** — each program has its own hypotheses + results

### Migration Between Islands

When a program migrates from island A to island B, its code (including
HYPOTHESIS/RESULT comments) migrates with it. Programs on island B can now see
the migrant's hypothesis reasoning — both what it tried and whether it worked.
No special handling needed.

### Ancestry

When parent P is selected and its code is shown to the LLM:
- P's code contains P's own HYPOTHESIS/EXPECT/RESULT lines
- P's code itself embodies the successful mutations from all ancestors
- The LLM also sees top programs (which may include P's ancestors if they're still top-scoring)

Grandparent's explicit hypothesis verdicts are visible as long as grandparent
remains in the top programs or inspirations. If grandparent was surpassed, its
successful strategies are already embodied in descendant code.

---

## V1 Design (Previous Implementation)

### How V1 Worked

Each evaluator contained ~50-80 lines of hypothesis boilerplate:
1. Parse HYPOTHESIS/EXPECT from code
2. Test against actual metrics
3. Load/update a persistent JSON ledger file
4. Call `generate_knowledge_base_summary()` to aggregate by exact claim string
5. Store the summary as `artifacts["hypothesis_knowledge_base"]` on the program

When the program was later selected as parent, its stale artifact was shown to the LLM.

### Why V1 Was Replaced

1. **Dead aggregation** — `generate_knowledge_base_summary()` grouped by exact
   `(metric, claim)` string match. LLM-generated claims never repeat verbatim,
   so every hypothesis had `total=1`. The REFUTED bucket (requires `total >= 2`)
   was always empty.

2. **Stale knowledge** — The knowledge base was frozen at eval time. If selected
   as parent 50 iterations later, the LLM saw 50-iteration-old intelligence.

3. **Global scope** — The ledger was global but OpenEvolve uses island-based
   MAP-Elites. Hypothesis intelligence leaked across island boundaries.

4. **Duplicated boilerplate** — Every evaluator had ~50-80 lines of identical
   hypothesis pipeline code.

5. **Over-engineered** — Ledger, knowledge base, artifacts, prompt-time queries
   — all unnecessary when the information can just live in the code.
