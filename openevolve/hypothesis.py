"""
Generic hypothesis parsing, testing, and ledger management for OpenEvolve.

Evaluators use this module to:
1. Parse HYPOTHESIS/MECHANISM/EXPECT comments from evolved code (any language)
2. Test hypotheses against actual vs baseline metrics
3. Maintain a persistent ledger of outcomes
4. Generate a knowledge base summary for LLM feedback

The comment format works with any language's comment syntax:
    # HYPOTHESIS-1: <claim>          (Python, Ruby, Shell)
    // HYPOTHESIS-1: <claim>         (Go, C, Rust, JS)
    -- HYPOTHESIS-1: <claim>         (SQL, Lua, Haskell)
"""

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Regex that matches any single-line comment prefix: //, #, or --
_COMMENT_PREFIX = r"(?://|#|--)\s*"


def count_hypothesis_comments(text: str) -> int:
    """Count the number of HYPOTHESIS-N comment lines in text."""
    return len(re.findall(rf"(?://|#|--)\s*HYPOTHESIS-\d+:", text))


def count_expect_comments(text: str) -> int:
    """Count the number of EXPECT-N comment lines in text."""
    return len(re.findall(rf"(?://|#|--)\s*EXPECT-\d+:", text))


def count_result_comments(text: str) -> int:
    """Count the number of RESULT-N comment lines in text."""
    return len(re.findall(rf"(?://|#|--)\s*RESULT-\d+:", text))


@dataclass
class IterationHypothesisStats:
    """Per-iteration hypothesis pipeline statistics."""
    iteration: int = 0
    # LLM generated hypotheses in its response
    hypotheses_in_llm_response: int = 0
    expects_in_llm_response: int = 0
    # Hypotheses present in final child code (after rescue)
    hypotheses_in_child_code: int = 0
    expects_in_child_code: int = 0
    # RESULT comments injected after evaluation
    results_injected: int = 0
    # Hypotheses visible in the parent program shown to LLM
    hypotheses_in_parent: int = 0
    results_in_parent: int = 0
    # Hypotheses visible in top programs shown to LLM
    top_programs_with_hypotheses: int = 0
    top_programs_total: int = 0


@dataclass
class HypothesisTracker:
    """Aggregates hypothesis pipeline statistics across iterations."""
    iterations: list = field(default_factory=list)
    # Running totals
    total_iterations: int = 0
    total_hypotheses_generated: int = 0
    total_hypotheses_persisted: int = 0
    total_results_injected: int = 0
    total_iterations_with_parent_hypotheses: int = 0

    def record(self, stats: IterationHypothesisStats) -> None:
        """Record stats for one iteration and update totals."""
        self.iterations.append(asdict(stats))
        self.total_iterations += 1
        self.total_hypotheses_generated += stats.hypotheses_in_llm_response
        self.total_hypotheses_persisted += stats.hypotheses_in_child_code
        self.total_results_injected += stats.results_injected
        if stats.hypotheses_in_parent > 0:
            self.total_iterations_with_parent_hypotheses += 1

        # Log per-iteration summary
        gen_ok = "OK" if stats.hypotheses_in_llm_response > 0 else "MISS"
        persist_ok = "OK" if stats.hypotheses_in_child_code > 0 else "MISS"
        inject_ok = "OK" if stats.results_injected > 0 else "MISS"
        inherit_ok = "OK" if stats.hypotheses_in_parent > 0 else "N/A"

        logger.info(
            f"[HYPO-TRACK] iter={stats.iteration} | "
            f"generated={stats.hypotheses_in_llm_response}({gen_ok}) "
            f"persisted={stats.hypotheses_in_child_code}({persist_ok}) "
            f"results_injected={stats.results_injected}({inject_ok}) "
            f"parent_hypos={stats.hypotheses_in_parent}({inherit_ok}) "
            f"top_w_hypos={stats.top_programs_with_hypotheses}/{stats.top_programs_total}"
        )

    def summary(self) -> dict:
        """Return a summary dict for persistence."""
        gen_rate = (
            self.total_hypotheses_generated / self.total_iterations
            if self.total_iterations > 0 else 0
        )
        persist_rate = (
            self.total_hypotheses_persisted / self.total_hypotheses_generated
            if self.total_hypotheses_generated > 0 else 0
        )
        inject_rate = (
            self.total_results_injected / self.total_hypotheses_persisted
            if self.total_hypotheses_persisted > 0 else 0
        )
        inherit_rate = (
            self.total_iterations_with_parent_hypotheses / self.total_iterations
            if self.total_iterations > 0 else 0
        )
        return {
            "total_iterations_tracked": self.total_iterations,
            "total_hypotheses_generated": self.total_hypotheses_generated,
            "total_hypotheses_persisted": self.total_hypotheses_persisted,
            "total_results_injected": self.total_results_injected,
            "total_iterations_with_parent_hypotheses": self.total_iterations_with_parent_hypotheses,
            "avg_hypotheses_per_iteration": round(gen_rate, 2),
            "persist_rate": round(persist_rate, 3),
            "inject_rate": round(inject_rate, 3),
            "inherit_rate": round(inherit_rate, 3),
            "per_iteration": self.iterations,
        }

    def save(self, path: Path) -> None:
        """Save tracker state to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.summary(), f, indent=2)
        logger.info(f"[HYPO-TRACK] Saved hypothesis tracker to {path}")


def extract_hypothesis_comment_block(text: str) -> list[str]:
    """Extract raw HYPOTHESIS/MECHANISM/EXPECT comment lines from text.

    Scans *all* lines (not just code) for hypothesis comment blocks.
    Used to recover hypotheses from LLM responses when diff application
    strips them from the final code.

    Returns:
        List of comment-line strings (stripped of leading whitespace).
    """
    hyp_pattern = re.compile(rf"^{_COMMENT_PREFIX}(HYPOTHESIS-\d+|EXPECT-\d+):\s*.+$")
    mech_pattern = re.compile(rf"^{_COMMENT_PREFIX}MECHANISM-\d+:\s*.+$")
    cont_pattern = re.compile(r"^(?://|#|--)\s{3,}.+$")

    lines = text.splitlines()
    result: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if hyp_pattern.match(stripped):
            result.append(stripped)
            i += 1
            continue
        if mech_pattern.match(stripped):
            result.append(stripped)
            # Consume continuation lines
            while i + 1 < len(lines):
                next_stripped = lines[i + 1].strip()
                if cont_pattern.match(next_stripped):
                    result.append(next_stripped)
                    i += 1
                else:
                    break
            i += 1
            continue
        i += 1
    return result


def rescue_hypotheses(code: str, llm_response: str) -> str:
    """Inject hypothesis comments into code if they exist only in the LLM response.

    When diff-based evolution is used, some LLMs place hypothesis comments
    outside the SEARCH/REPLACE blocks.  ``apply_diff`` only keeps the
    REPLACE content, so the hypotheses are lost.  This function recovers
    them from the raw LLM response and injects them right after the first
    ``EVOLVE-BLOCK-START`` marker.

    No-op when:
      - code already contains hypothesis comments (e.g. Claude path)
      - llm_response has no hypothesis comments
      - code has no EVOLVE-BLOCK-START marker
    """
    # Already present in code? Nothing to do.
    if re.search(r"(?://|#|--)\s*HYPOTHESIS-\d+:", code):
        return code

    hyp_lines = extract_hypothesis_comment_block(llm_response)
    if not hyp_lines:
        return code

    # Find first EVOLVE-BLOCK-START
    marker = "EVOLVE-BLOCK-START"
    code_lines = code.split("\n")
    insert_idx = None
    indent = ""
    for idx, line in enumerate(code_lines):
        if marker in line:
            insert_idx = idx
            # Detect indentation: everything before the comment prefix
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]
            break

    if insert_idx is None:
        return code

    # Indent hypothesis lines to match the EVOLVE-BLOCK-START line
    indented = [indent + hl for hl in hyp_lines]

    code_lines[insert_idx + 1 : insert_idx + 1] = indented
    logger.debug("Rescued %d hypothesis comment lines into evolved code", len(hyp_lines))
    return "\n".join(code_lines)


def inject_result_comments(code: str, actual_metrics: dict) -> str:
    """Inject RESULT-N comment lines after each EXPECT-N in the code.

    After evaluation, the framework calls this to stamp hypothesis verdicts
    directly into the child's code.  When this code is later shown to the LLM
    (as parent, top program, or inspiration), the verdicts are visible in
    context with the code that produced them.

    No-op when:
      - code has no EXPECT-N lines
      - RESULT-N lines already exist (idempotent)

    Args:
        code: Source code with HYPOTHESIS/MECHANISM/EXPECT comments.
        actual_metrics: Dict of metric_name -> value from evaluation.

    Returns:
        Code with RESULT-N lines injected after each EXPECT-N.
    """
    # Already has results? Don't double-stamp.
    if re.search(r"(?://|#|--)\s*RESULT-\d+:", code):
        return code

    # No EXPECT lines? Nothing to inject — return code unchanged.
    if not re.search(r"(?://|#|--)\s*EXPECT-\d+:", code):
        return code

    expect_pattern = re.compile(
        r"^(\s*)((?://|#|--)\s*)EXPECT-(\d+):\s*(\S+)\s*([<>])\s*([0-9]+(?:\.[0-9]+)?)\s*$"
    )

    lines = code.splitlines()
    new_lines = []
    for line in lines:
        new_lines.append(line)
        m = expect_pattern.match(line)
        if m:
            indent = m.group(1)       # leading whitespace
            prefix = m.group(2)       # comment prefix (e.g. "// " or "# ")
            hid = m.group(3)          # hypothesis number
            metric = m.group(4)       # metric name
            operator = m.group(5)     # < or >
            threshold = float(m.group(6))
            actual = actual_metrics.get(metric)

            if actual is None:
                verdict = "INCONCLUSIVE"
                result_text = f"{indent}{prefix}RESULT-{hid}: {verdict} (metric not available)"
            else:
                if operator == ">":
                    verdict = "CONFIRMED" if actual > threshold else "REFUTED"
                else:
                    verdict = "CONFIRMED" if actual < threshold else "REFUTED"
                result_text = f"{indent}{prefix}RESULT-{hid}: {verdict} (actual={actual})"

            new_lines.append(result_text)

    return "\n".join(new_lines)


def parse_hypotheses(code: str, valid_metrics: set[str]) -> list:
    """Parse HYPOTHESIS-N, MECHANISM-N, EXPECT-N comment blocks from code.

    Supports //, #, and -- comment styles. Returns only complete hypotheses
    (all three fields present) with valid metric names.

    Args:
        code: Source code string containing hypothesis comments.
        valid_metrics: Set of metric names that EXPECT lines may reference.

    Returns:
        List of dicts with keys: id, claim, mechanism, metric, threshold.
    """
    fields: dict[int, dict] = {}
    lines = code.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # HYPOTHESIS-N: <claim>
        m = re.match(rf"^{_COMMENT_PREFIX}HYPOTHESIS-(\d+):\s*(.+)$", line)
        if m:
            hid = int(m.group(1))
            fields.setdefault(hid, {})["claim"] = m.group(2).strip()
            i += 1
            continue

        # MECHANISM-N: <mechanism> (possibly multi-line)
        m = re.match(rf"^{_COMMENT_PREFIX}MECHANISM-(\d+):\s*(.+)$", line)
        if m:
            hid = int(m.group(1))
            parts = [m.group(2).strip()]
            # Consume continuation lines: comment prefix followed by 3+ spaces
            while i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                cont = re.match(r"^(?://|#|--)\s{3,}(.+)$", next_line)
                if cont:
                    parts.append(cont.group(1).strip())
                    i += 1
                else:
                    break
            fields.setdefault(hid, {})["mechanism"] = " ".join(parts)
            i += 1
            continue

        # EXPECT-N: <metric> < <threshold>  OR  <metric> > <threshold>
        m = re.match(
            rf"^{_COMMENT_PREFIX}EXPECT-(\d+):\s*(\S+)\s*([<>])\s*([0-9]+(?:\.[0-9]+)?)\s*$",
            line,
        )
        if m:
            hid = int(m.group(1))
            entry = fields.setdefault(hid, {})
            entry["metric"] = m.group(2).strip()
            entry["operator"] = m.group(3)
            entry["threshold"] = float(m.group(4))
            i += 1
            continue

        i += 1

    results = []
    for hid in sorted(fields):
        f = fields[hid]
        if all(k in f for k in ("claim", "mechanism", "metric", "threshold")):
            if f["metric"] not in valid_metrics:
                logger.warning(
                    "Hypothesis %d references unknown metric %r; skipping", hid, f["metric"]
                )
                continue
            results.append(
                {
                    "id": hid,
                    "claim": f["claim"],
                    "mechanism": f["mechanism"],
                    "metric": f["metric"],
                    "operator": f.get("operator", "<"),
                    "threshold": f["threshold"],
                }
            )
    return results


def test_hypotheses(hypotheses: list, actual_metrics: dict, baseline_metrics: dict) -> list:
    """Test each hypothesis against actual evaluation results and baseline.

    Verdicts:
      - CONFIRMED: actual satisfies the operator/threshold (< or >)
      - REFUTED: actual does not satisfy
      - INCONCLUSIVE: metric missing from actual_metrics
    """
    results = []
    for h in hypotheses:
        metric = h["metric"]
        threshold = h["threshold"]
        operator = h.get("operator", "<")
        actual = actual_metrics.get(metric)
        baseline_value = baseline_metrics.get(metric)

        if actual is None:
            verdict = "INCONCLUSIVE"
            delta_pct = None
        else:
            if operator == ">":
                verdict = "CONFIRMED" if actual > threshold else "REFUTED"
            else:
                verdict = "CONFIRMED" if actual < threshold else "REFUTED"
            if baseline_value is not None and baseline_value != 0:
                delta_pct = ((actual - baseline_value) / baseline_value) * 100.0
            else:
                delta_pct = None

        results.append(
            {
                "id": h["id"],
                "claim": h["claim"],
                "mechanism": h["mechanism"],
                "metric": metric,
                "operator": operator,
                "threshold": threshold,
                "actual": actual,
                "baseline_value": baseline_value,
                "delta_vs_baseline_pct": delta_pct,
                "verdict": verdict,
            }
        )
    return results


def load_ledger(ledger_path: Path) -> dict:
    """[DEPRECATED] Load hypothesis ledger from disk, or return empty structure.

    V3 hypothesis pipeline uses inline RESULT comments instead of a ledger.
    Kept for backward compatibility.
    """
    import warnings
    warnings.warn(
        "load_ledger() is deprecated. V3 uses inline RESULT comments in code.",
        DeprecationWarning,
        stacklevel=2,
    )
    ledger_path = Path(ledger_path)
    if ledger_path.exists():
        with open(ledger_path, "r") as f:
            return json.load(f)
    return {"baseline": {}, "entries": []}


def update_ledger(
    ledger: dict, hypothesis_results: list, overall_combined_score: float, ledger_path: Path
) -> dict:
    """[DEPRECATED] Append hypothesis results to ledger and persist to disk.

    V3 hypothesis pipeline uses inline RESULT comments instead of a ledger.
    Kept for backward compatibility.
    """
    import warnings
    warnings.warn(
        "update_ledger() is deprecated. V3 uses inline RESULT comments in code.",
        DeprecationWarning,
        stacklevel=2,
    )
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_combined_score": overall_combined_score,
        "hypotheses": hypothesis_results,
    }
    ledger["entries"].append(entry)

    ledger_path = Path(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "w") as f:
        json.dump(ledger, f, indent=2)
    return ledger


def generate_knowledge_base_summary(ledger: dict, top_n: int = 5) -> str:
    """[DEPRECATED] Generate text summary of hypothesis outcomes.

    V3 hypothesis pipeline uses inline RESULT comments instead of a knowledge base.
    Kept for backward compatibility.
    """
    import warnings
    warnings.warn(
        "generate_knowledge_base_summary() is deprecated. V3 uses inline RESULT comments in code.",
        DeprecationWarning,
        stacklevel=2,
    )
    entries = ledger.get("entries", [])
    if not entries:
        lines = ["HYPOTHESIS KNOWLEDGE BASE:", "", "No hypothesis data yet."]
        baseline = ledger.get("baseline", {})
        if baseline:
            lines.append("")
            lines.append("BASELINE VALUES (initial program):")
            for k, v in sorted(baseline.items()):
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    agg: dict[tuple[str, str], list[dict]] = {}
    for entry in entries:
        for h in entry.get("hypotheses", []):
            key = (h["metric"], h["claim"])
            agg.setdefault(key, []).append(
                {
                    "verdict": h["verdict"],
                    "delta_pct": h.get("delta_vs_baseline_pct"),
                    "mechanism": h.get("mechanism", ""),
                }
            )

    stats = []
    for (metric, claim), records in agg.items():
        total = len(records)
        confirmed = sum(1 for r in records if r["verdict"] == "CONFIRMED")
        confirm_rate = confirmed / total if total > 0 else 0.0
        deltas = [r["delta_pct"] for r in records if r["delta_pct"] is not None]
        avg_delta = sum(deltas) / len(deltas) if deltas else 0.0
        mechanism = records[0]["mechanism"]
        stats.append(
            {
                "metric": metric,
                "claim": claim,
                "mechanism": mechanism,
                "total": total,
                "confirmed": confirmed,
                "confirm_rate": confirm_rate,
                "avg_delta": avg_delta,
            }
        )

    confirmed_strategies = [s for s in stats if s["confirm_rate"] >= 0.5]
    refuted_strategies = [s for s in stats if s["confirm_rate"] < 0.5 and s["total"] >= 2]
    inconclusive = [s for s in stats if s["total"] < 2 and s["confirm_rate"] < 0.5]

    confirmed_strategies.sort(key=lambda s: s["avg_delta"])
    refuted_strategies.sort(key=lambda s: -s["avg_delta"])
    confirmed_strategies = confirmed_strategies[:top_n]
    refuted_strategies = refuted_strategies[:top_n]
    inconclusive = inconclusive[:top_n]

    lines = []
    if confirmed_strategies:
        lines.append("=== CONFIRMED STRATEGIES ===")
        for s in confirmed_strategies:
            lines.append(
                f"  [{s['metric']}] {s['claim']} "
                f"(confirmed {s['confirmed']}/{s['total']}, avg_delta={s['avg_delta']:+.1f}%)"
            )
            if s["mechanism"]:
                lines.append(f"    mechanism: {s['mechanism']}")
        lines.append("")

    if refuted_strategies:
        lines.append("=== REFUTED STRATEGIES ===")
        for s in refuted_strategies:
            lines.append(
                f"  [{s['metric']}] {s['claim']} "
                f"(confirmed {s['confirmed']}/{s['total']}, avg_delta={s['avg_delta']:+.1f}%)"
            )
            if s["mechanism"]:
                lines.append(f"    mechanism: {s['mechanism']}")
        lines.append("")

    if inconclusive:
        lines.append("=== INCONCLUSIVE ===")
        for s in inconclusive:
            lines.append(f"  [{s['metric']}] {s['claim']} (total={s['total']})")
        lines.append("")

    baseline = ledger.get("baseline", {})
    if baseline:
        lines.append("=== BASELINE VALUES ===")
        for k, v in sorted(baseline.items()):
            lines.append(f"  {k}: {v}")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_hypothesis_results(
    hypothesis_results: list, overall_score: float, baseline_score: float
) -> str:
    """[DEPRECATED] Format hypothesis verdicts as human-readable text.

    V3 hypothesis pipeline uses inline RESULT comments instead.
    Kept for backward compatibility.
    """
    import warnings
    warnings.warn(
        "format_hypothesis_results() is deprecated. V3 uses inline RESULT comments in code.",
        DeprecationWarning,
        stacklevel=2,
    )
    lines = ["--- Hypothesis Verdicts ---"]
    for h in hypothesis_results:
        actual_str = f"{h['actual']:.1f}" if h["actual"] is not None else "N/A"
        delta_str = ""
        if h["delta_vs_baseline_pct"] is not None:
            delta_str = f" (delta={h['delta_vs_baseline_pct']:+.1f}% vs baseline)"
        op = h.get("operator", "<")
        lines.append(
            f"  H{h['id']} [{h['verdict']}]: "
            f"EXPECT {h['metric']} {op} {h['threshold']:.1f}, "
            f"ACTUAL {actual_str}{delta_str}"
        )
        lines.append(f"    claim: {h['claim']}")

    score_delta = overall_score - baseline_score
    score_delta_pct = (score_delta / abs(baseline_score) * 100.0) if baseline_score != 0 else 0.0
    lines.append(
        f"  OVERALL: combined_score={overall_score:.2f} "
        f"(delta={score_delta:+.2f}, {score_delta_pct:+.1f}% vs baseline={baseline_score:.2f})"
    )
    return "\n".join(lines)
