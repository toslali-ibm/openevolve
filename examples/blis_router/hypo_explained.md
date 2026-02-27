# How Hypothesis-Driven Evolution Works

## Pipeline Flow

### Step 1: System Prompt — Hypothesis Instructions

When `hypothesis_driven: true` in config, the system message sent to the LLM is
appended with `HYPOTHESIS_INSTRUCTIONS_TEMPLATE` (`openevolve/prompt/templates.py`).

This tells the LLM:
- Write 1-3 hypotheses as comments at the TOP of the EVOLVE-BLOCK
- Each hypothesis needs 3 lines: HYPOTHESIS-N, MECHANISM-N, EXPECT-N
- EXPECT uses `<` for lower-is-better metrics, `>` for higher-is-better
- Build on CONFIRMED strategies from the knowledge base
- Avoid or differentiate from REFUTED strategies

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

### Step 4: Evaluator — Parse, Test, Update Ledger

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

**c) Update Ledger** — `update_ledger(ledger, results, score, ledger_path)`:
  - Appends a new entry to the persistent JSON ledger file
  - Each entry contains: timestamp, overall score, list of hypothesis verdicts
  - Ledger file is per-run (stored in `OPENEVOLVE_OUTPUT_DIR`)
  - Ledger grows monotonically — entries are never removed

The entire hypothesis pipeline only runs when `HYPOTHESIS_DRIVEN=true` env var
is set (propagated from `config.hypothesis_driven` by the controller).

### Step 5: Knowledge Base — Feedback to Next Iteration

After updating the ledger, the evaluator generates a knowledge base summary and
stores it as an **artifact** on the current program.

**`generate_knowledge_base_summary(ledger, top_n=5)`** works as follows:

1. **Aggregate** all ledger entries by unique `(metric, claim)` pairs.
   If the same claim was tested 5 times across different iterations, those
   5 verdicts are grouped together.

2. **Classify** each unique strategy:
   - **Confirmed**: confirm_rate >= 50% (majority of tests passed)
   - **Refuted**: confirm_rate < 50% AND tested >= 2 times
   - **Inconclusive**: tested only once AND not confirmed

3. **Select top 5** from each category:
   - Confirmed: sorted by avg_delta (best improvement first)
   - Refuted: sorted by worst avg_delta first
   - Inconclusive: up to 5

4. **Append baseline values** (metrics from the initial program)

The result is a plain text summary like:
```
=== CONFIRMED STRATEGIES ===
  [combined_score] Hybrid of global exploration and local Gaussian mutation
  (confirmed 11/11, avg_delta=-1.2%)
    mechanism: Global uniform sampling finds basins, Gaussian steps converge within

=== REFUTED STRATEGIES ===
  [load_spikes_e2e_ms] Aggressive quadratic penalty on overloaded instances
  (confirmed 0/3, avg_delta=+2.1%)
    mechanism: Quadratic penalties cause routing oscillation between instances

=== BASELINE VALUES ===
  avg_e2e_ms: 2610.5
  combined_score: -3860.2
```

This text is stored as `artifacts["hypothesis_knowledge_base"]` on the
**current program** — the one just evaluated.

### Step 6: Prompt Assembly — How It Reaches the LLM

When this program is later selected as a **parent** for a new iteration:

1. Worker fetches parent's artifacts from the database snapshot
   (`process_parallel.py:157`)
2. Artifacts are passed to `build_prompt(program_artifacts=parent_artifacts)`
   (`process_parallel.py:190`)
3. `_render_artifacts()` renders ALL artifacts as markdown code blocks
   in the `{artifacts}` section of the user message template
4. No further filtering — the knowledge base text is included verbatim

So the LLM sees:
- **System message**: hypothesis format instructions (HYPOTHESIS-N / MECHANISM-N / EXPECT-N)
- **User message**: parent code, metrics, evolution history, AND the knowledge base
  artifact showing which strategies worked (confirmed) and which failed (refuted)

The LLM is expected to use this feedback to:
- **Build on** confirmed strategies (combine proven techniques)
- **Avoid** refuted strategies (or explain why a new approach differs)
- **Set thresholds** informed by baseline values

## Summary

```
Iteration N:
  LLM sees:  system prompt (hypothesis instructions)
           + user prompt (parent code, metrics, history)
           + parent's artifact: knowledge base (top 5 confirmed, top 5 refuted,
                                                top 5 inconclusive, baseline values)
  LLM writes: evolved code with 1-3 HYPOTHESIS/MECHANISM/EXPECT comments

  Evaluator:  runs code → gets actual metrics
           → parse_hypotheses() extracts hypotheses from code
           → test_hypotheses() checks each EXPECT against actual
           → update_ledger() appends verdicts to persistent ledger
           → generate_knowledge_base_summary() selects top 5 per category
                from ENTIRE ledger history
           → stores summary as artifact["hypothesis_knowledge_base"]
                on THIS program (the child)

Iteration N+1:
  If this child is selected as parent → its knowledge base artifact
  is shown to the LLM → cycle continues
```

At most **15 strategies + baseline values** are shown to the LLM at any time
(5 confirmed + 5 refuted + 5 inconclusive), regardless of how large the ledger grows.
