"""
Structured threshold tuning v2 for OpenEvolve.

Parses @TUNE annotations from LLM-generated code, runs Optuna to find
optimal threshold values, and rewrites code with optimized values.

v2 changes from v1:
- Tiered trial budgets (rescue/checkpoint/final) instead of flat budget
- tune_program() returns best trial metrics to eliminate redundant evals
- Warm hint via enqueue_trial() using current @TUNE values
- strip_tuned_for_db() ensures @TUNED never reaches the database or LLM
- Auto-strips insensitive @TUNE annotations (|gain| < threshold)
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Regex for: varname = value  # @TUNE [low, high] [int|float]
# Supports both Python (#) and Go/C++ (//) comment styles, and := assignment
_TUNE_RANGE_RE = re.compile(
    r"^(\s*(\w+)\s*:?=\s*(.+?)\s*)(?:#|//)\s*@TUNE\s+\[([^,\]]+),\s*([^\]]+)\](\s+(?:int|float))?"
)

# Regex to strip existing @TUNED(...) annotations
_TUNED_RE = re.compile(r"\s*@TUNED\([^)]*\)")

# Regex to extract gain from @TUNED annotation
_TUNED_GAIN_RE = re.compile(r"@TUNED\([^)]*gain=([+-]?[\d.]+)")

# Regex to strip @TUNE annotation (and any trailing @TUNED) from a line
_TUNE_ANNOTATION_RE = re.compile(
    r"\s*(?:#|//)\s*@TUNE\s+\[[^\]]+\](?:\s+(?:int|float))?(?:\s*@TUNED\([^)]*\))?"
)


@dataclass
class TuneParam:
    """A single tunable parameter parsed from code."""

    name: str
    value: object  # original value (float or int)
    line_number: int  # 0-indexed line in code
    full_line: str  # the full original line text
    param_type: str = "float"  # "float" or "int"
    low: Optional[float] = None
    high: Optional[float] = None


def parse_tune_annotations(code: str, max_params: int = 3) -> List[TuneParam]:
    """Parse @TUNE annotations from code, returning up to max_params."""
    params: List[TuneParam] = []
    lines = code.split("\n")

    for i, line in enumerate(lines):
        if len(params) >= max_params:
            break
        if "@TUNE" not in line:
            continue

        # Try range pattern: [low, high]
        m = _TUNE_RANGE_RE.match(line)
        if m:
            name = m.group(2)
            raw_value = m.group(3).strip().strip('"').strip("'")
            low = float(m.group(4).strip())
            high = float(m.group(5).strip())
            type_hint = (m.group(6) or "").strip()

            if type_hint == "int":
                param_type = "int"
                value = int(float(raw_value))
                low, high = int(low), int(high)
            else:
                param_type = "float"
                value = float(raw_value)

            params.append(
                TuneParam(
                    name=name,
                    value=value,
                    line_number=i,
                    full_line=line,
                    param_type=param_type,
                    low=low,
                    high=high,
                )
            )
            continue

    return params


def has_tune_annotations(code: str) -> bool:
    """Quick check whether code contains any @TUNE annotations."""
    if "@TUNE" not in code:
        return False
    for line in code.split("\n"):
        if _TUNE_RANGE_RE.match(line):
            return True
    return False


def strip_tuned_annotations(code: str) -> str:
    """Remove all @TUNED(...) annotations from code, preserving @TUNE."""
    return _TUNED_RE.sub("", code)


def extract_current_tune_values(code: str) -> dict:
    """Extract current values from lines that have @TUNE annotations.

    Since @TUNED is stripped before DB storage, the current value on a
    @TUNE line IS the best value from any prior tuning run (or the LLM's
    original guess if never tuned). Either way, it's a good seed.
    """
    values = {}
    for line in code.split("\n"):
        m = _TUNE_RANGE_RE.match(line)
        if m:
            name = m.group(2)
            raw_value = m.group(3).strip().strip('"').strip("'")
            type_hint = (m.group(6) or "").strip()
            try:
                if type_hint == "int":
                    values[name] = int(float(raw_value))
                else:
                    values[name] = float(raw_value)
            except (ValueError, TypeError):
                pass
    return values


def strip_tuned_for_db(code: str, gain_threshold: float = 0.01) -> str:
    """Strip @TUNED annotations before code enters the database.

    - All @TUNED(...) annotations are removed
    - If |gain| < gain_threshold, also strip @TUNE (parameter is insensitive)
    - The optimized VALUE remains in the code (the LLM sees the number)
    """
    lines = []
    for line in code.split("\n"):
        if "@TUNED" in line:
            gain = _extract_gain(line)
            if gain is not None and abs(gain) < gain_threshold:
                # Insensitive param: strip both @TUNE and @TUNED
                line = _strip_tune_annotation(line)
                logger.info(
                    f"[TUNE-STRIP] Stripped @TUNE (gain={gain:+.4f}, "
                    f"below threshold {gain_threshold})"
                )
            else:
                # Sensitive param: keep @TUNE, strip only @TUNED
                line = _TUNED_RE.sub("", line)
        lines.append(line)
    return "\n".join(lines)


def _extract_gain(line: str) -> Optional[float]:
    """Parse gain value from @TUNED annotation on a line."""
    m = _TUNED_GAIN_RE.search(line)
    if m:
        try:
            return float(m.group(1))
        except (ValueError, TypeError):
            return None
    return None


def _strip_tune_annotation(line: str) -> str:
    """Strip @TUNE (and any @TUNED) annotation from a line, keeping the assignment."""
    return _TUNE_ANNOTATION_RE.sub("", line).rstrip()


def _compute_best_impact(original_metrics: dict, best_metrics: dict) -> str:
    """Find the single metric with the largest absolute delta."""
    best_metric = None
    best_delta = 0.0
    for key in best_metrics:
        if key in original_metrics:
            orig = original_metrics[key]
            best = best_metrics[key]
            if isinstance(orig, (int, float)) and isinstance(best, (int, float)):
                delta = best - orig
                if abs(delta) > abs(best_delta):
                    best_delta = delta
                    best_metric = key
    if best_metric is None:
        return ""
    sign = "+" if best_delta >= 0 else ""
    # Format: round to reasonable precision
    if abs(best_delta) >= 1:
        delta_str = f"{sign}{best_delta:.1f}"
    else:
        delta_str = f"{sign}{best_delta:.4f}"
    return f"{best_metric}:{delta_str}"


def rewrite_tune_values(
    code: str,
    params: List[TuneParam],
    new_values: dict,
    original_score: float,
    best_score: float,
    original_metrics: dict,
    best_metrics: dict,
) -> str:
    """Rewrite @TUNE lines with optimized values and @TUNED annotations."""
    gain = best_score - original_score
    gain_str = f"{'+' if gain >= 0 else ''}{gain:.2f}"
    impact_str = _compute_best_impact(original_metrics, best_metrics)

    lines = code.split("\n")
    param_by_line = {p.line_number: p for p in params}

    for line_num, param in param_by_line.items():
        if line_num >= len(lines):
            continue
        new_val = new_values.get(param.name)
        if new_val is None:
            continue

        old_line = lines[line_num]
        # Preserve indentation
        indent = old_line[: len(old_line) - len(old_line.lstrip())]

        # Detect assignment operator (:= for Go, = for Python/etc)
        assign_op = ":=" if ":=" in old_line.split("#")[0].split("//")[0] else "="

        # Build the assignment part
        if param.param_type == "int":
            assign = f"{indent}{param.name} {assign_op} {int(new_val)}"
        else:
            assign = f"{indent}{param.name} {assign_op} {round(new_val, 4)}"

        # Preserve the @TUNE annotation from the original line (supports # and // comments)
        tune_match = re.search(r"(?:#|//)\s*@TUNE\s+\[[^\]]+\](?:\s+(?:int|float))?", old_line)
        tune_part = tune_match.group(0) if tune_match else ""

        # Build @TUNED annotation
        was_val = param.value
        tuned_parts = [f"was={was_val}", f"gain={gain_str}"]
        if impact_str:
            tuned_parts.append(f"best_impact={impact_str}")
        tuned_annotation = f"@TUNED({', '.join(tuned_parts)})"

        lines[line_num] = f"{assign}  {tune_part} {tuned_annotation}"

    return "\n".join(lines)


@dataclass
class IterationTuningStats:
    """Per-iteration tuning pipeline statistics (v2: extended)."""

    iteration: int = 0
    mode: str = ""  # "rescue", "checkpoint", "final", or "skipped"
    tune_annotations_found: int = 0
    tune_annotations_honored: int = 0
    tuning_ran: bool = False
    tuning_duration_s: Optional[float] = None
    original_score: Optional[float] = None
    tuned_score: Optional[float] = None
    gain: Optional[float] = None
    trials_completed: int = 0
    trials_failed: int = 0
    param_changes: dict = field(default_factory=dict)
    warm_hint_used: bool = False
    selection_reason: str = ""  # "novel_low_score", "very_poor", "checkpoint_elite", "final_elite"
    annotations_stripped: int = 0  # @TUNE removed due to gain ~ 0


@dataclass
class TuningTracker:
    """Aggregates tuning statistics across iterations (v2: extended)."""

    iterations: list = field(default_factory=list)
    total_iterations: int = 0
    total_iterations_with_tuning: int = 0
    total_trials: int = 0
    total_gain: float = 0.0
    total_tuning_duration_s: float = 0.0
    rescue_count: int = 0
    checkpoint_polish_count: int = 0
    final_polish_count: int = 0
    skip_count: int = 0
    total_annotations_stripped: int = 0

    def record(self, stats: IterationTuningStats) -> None:
        """Record stats for one iteration and update totals."""
        self.iterations.append(asdict(stats))
        self.total_iterations += 1
        if stats.tuning_ran:
            self.total_iterations_with_tuning += 1
            self.total_trials += stats.trials_completed + stats.trials_failed
            if stats.gain is not None:
                self.total_gain += stats.gain
            if stats.tuning_duration_s is not None:
                self.total_tuning_duration_s += stats.tuning_duration_s
            self.total_annotations_stripped += stats.annotations_stripped

            # Count by mode
            if stats.mode == "rescue":
                self.rescue_count += 1
            elif stats.mode == "checkpoint":
                self.checkpoint_polish_count += 1
            elif stats.mode == "final":
                self.final_polish_count += 1
        else:
            self.skip_count += 1

        # Log per-iteration summary
        if stats.tuning_ran:
            logger.info(
                f"[TUNE-{stats.mode.upper()}] iter={stats.iteration} | "
                f"reason={stats.selection_reason} | "
                f"annotations={stats.tune_annotations_found}"
                f"→{stats.tune_annotations_honored} "
                f"trials={stats.trials_completed}ok/{stats.trials_failed}fail "
                f"score={stats.original_score:.4f}→{stats.tuned_score:.4f} "
                f"gain={stats.gain:+.4f} "
                f"duration={stats.tuning_duration_s:.1f}s "
                f"warm_hint={stats.warm_hint_used} "
                f"params={list(stats.param_changes.keys())}"
            )
        else:
            logger.info(
                f"[TUNE-SKIP] iter={stats.iteration} | "
                f"annotations={stats.tune_annotations_found} — tuning skipped"
            )

    def summary(self) -> dict:
        """Return a summary dict for persistence."""
        avg_gain = (
            self.total_gain / self.total_iterations_with_tuning
            if self.total_iterations_with_tuning > 0
            else 0.0
        )
        avg_duration = (
            self.total_tuning_duration_s / self.total_iterations_with_tuning
            if self.total_iterations_with_tuning > 0
            else 0.0
        )

        # Compute per-mode averages
        rescue_gains = [
            s.get("gain", 0)
            for s in self.iterations
            if s.get("mode") == "rescue" and s.get("tuning_ran") and s.get("gain") is not None
        ]
        checkpoint_gains = [
            s.get("gain", 0)
            for s in self.iterations
            if s.get("mode") == "checkpoint" and s.get("tuning_ran") and s.get("gain") is not None
        ]
        final_gains = [
            s.get("gain", 0)
            for s in self.iterations
            if s.get("mode") == "final" and s.get("tuning_ran") and s.get("gain") is not None
        ]

        # Compute tune annotation rate (manipulation check)
        iterations_with_annotations = sum(
            1 for s in self.iterations if s.get("tune_annotations_found", 0) > 0
        )
        tune_annotation_rate = (
            iterations_with_annotations / self.total_iterations
            if self.total_iterations > 0
            else 0.0
        )

        return {
            "total_iterations_tracked": self.total_iterations,
            "total_iterations_with_tuning": self.total_iterations_with_tuning,
            "rescue_count": self.rescue_count,
            "checkpoint_polish_count": self.checkpoint_polish_count,
            "final_polish_count": self.final_polish_count,
            "skip_count": self.skip_count,
            "total_trials": self.total_trials,
            "total_tuning_wall_clock_s": round(self.total_tuning_duration_s, 2),
            "avg_gain_when_tuned": round(avg_gain, 4),
            "rescue_avg_gain": round(sum(rescue_gains) / max(1, len(rescue_gains)), 4),
            "checkpoint_polish_avg_gain": round(
                sum(checkpoint_gains) / max(1, len(checkpoint_gains)), 4
            ),
            "final_polish_avg_gain": round(sum(final_gains) / max(1, len(final_gains)), 4),
            "avg_tuning_duration_s": round(avg_duration, 2),
            "annotations_stripped_total": self.total_annotations_stripped,
            "tune_annotation_rate": round(tune_annotation_rate, 4),
            "per_iteration": self.iterations,
        }

    def save(self, path: Path) -> None:
        """Save tracker state to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.summary(), f, indent=2)
        logger.info(f"[TUNE-TRACK] Saved tuning tracker to {path}")


async def tune_program(
    code: str,
    evaluate_fn: Callable[[str, str], Awaitable[dict]],
    config: "TuningConfig",
    mode: str = "rescue",
    baseline_metrics: dict = None,
) -> Tuple[str, IterationTuningStats, Optional[dict]]:
    """Optimize @TUNE thresholds using Optuna, return rewritten code, stats, and metrics.

    Args:
        code: Child program code with @TUNE annotations.
        evaluate_fn: Async function(code, program_id) -> metrics dict.
        config: TuningConfig with tiered trial budgets.
        mode: "rescue" (5 trials), "checkpoint" (10 trials), or "final" (20 trials).
        baseline_metrics: Pre-computed baseline metrics (avoids redundant eval).

    Returns:
        Tuple of (optimized code, stats, best trial metrics or None).
    """
    stats = IterationTuningStats(mode=mode)
    start_time = time.time()

    # Strip any existing @TUNED from inherited parent annotations
    code = strip_tuned_annotations(code)

    # Parse @TUNE annotations -- count all, honor up to max_params
    all_params = parse_tune_annotations(code, max_params=999)
    params = all_params[: config.max_params]
    stats.tune_annotations_found = len(all_params)
    stats.tune_annotations_honored = len(params)

    if not params:
        return code, stats, None

    try:
        import optuna
    except ImportError:
        raise ImportError(
            "Optuna is required for threshold tuning. "
            "Install it with: pip install openevolve[tuning]"
        )

    # Suppress Optuna's verbose logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # Select trial budget based on mode (flat counts)
    if mode == "final":
        n_trials = config.final_trials
    elif mode == "checkpoint":
        n_trials = config.checkpoint_trials
    else:
        n_trials = config.rescue_trials

    # Baseline evaluation (reuse pre-computed if available)
    if baseline_metrics:
        original_metrics = baseline_metrics
    else:
        try:
            original_metrics = await evaluate_fn(code, "tune_baseline")
        except Exception:
            logger.warning("[TUNING] Baseline evaluation failed, skipping tuning")
            return code, stats, None
    original_score = original_metrics.get("combined_score", 0.0)

    # Extract warm hint from current @TUNE values in code
    current_values = extract_current_tune_values(code)

    def objective(trial):
        """Optuna objective: suggest values, evaluate, return score."""
        values = {}
        for p in params:
            if p.param_type == "int":
                values[p.name] = trial.suggest_int(p.name, int(p.low), int(p.high))
            else:
                values[p.name] = trial.suggest_float(p.name, p.low, p.high)

        # Rewrite code with trial values (no @TUNED yet, just values)
        trial_code = _rewrite_values_only(code, params, values)

        # Evaluate -- run async evaluate in a new event loop
        try:
            trial_id = f"tune_trial_{trial.number}"
            loop = asyncio.new_event_loop()
            try:
                metrics = loop.run_until_complete(evaluate_fn(trial_code, trial_id))
            finally:
                loop.close()
            score = metrics.get("combined_score", 0.0)
            trial.set_user_attr("metrics", metrics)
            return score
        except Exception as e:
            logger.debug(f"[TUNING] Trial {trial.number} failed: {e}")
            return float("-inf")

    # Create study with warm hint
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(),
    )

    # Seed Optuna with current values as trial 0 (warm hint)
    if current_values:
        seed = {p.name: current_values[p.name] for p in params if p.name in current_values}
        if seed:
            study.enqueue_trial(seed)
            stats.warm_hint_used = True

    # Run Optuna study in executor to avoid blocking async loop
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        lambda: study.optimize(objective, n_trials=n_trials, show_progress_bar=False),
    )

    # Collect trial stats
    completed = [t for t in study.trials if t.value is not None and t.value > float("-inf")]
    failed = len(study.trials) - len(completed)
    stats.trials_completed = len(completed)
    stats.trials_failed = failed
    stats.tuning_ran = True
    stats.tuning_duration_s = time.time() - start_time
    stats.original_score = original_score

    # Check if any trial beat the original
    try:
        best_trial = study.best_trial
        if best_trial.value is not None and best_trial.value > original_score:
            best_score = best_trial.value
            best_values = best_trial.params
            best_metrics = best_trial.user_attrs.get("metrics", original_metrics)

            stats.tuned_score = best_score
            stats.gain = best_score - original_score
            stats.param_changes = {
                p.name: {"was": p.value, "now": best_values.get(p.name, p.value)} for p in params
            }

            # Rewrite with @TUNED annotations (internal), then strip for DB
            result = rewrite_tune_values(
                code,
                params,
                best_values,
                original_score,
                best_score,
                original_metrics,
                best_metrics,
            )
            result = strip_tuned_for_db(result)

            # Count stripped annotations
            stats.annotations_stripped = result.count("@TUNE") - code.count("@TUNE")
            if stats.annotations_stripped < 0:
                stats.annotations_stripped = abs(stats.annotations_stripped)
            else:
                stats.annotations_stripped = 0

            logger.info(
                f"[TUNING] Optimized {len(params)} params over {n_trials} trials "
                f"(mode={mode}): score {original_score:.4f} -> {best_score:.4f} "
                f"(gain={best_score - original_score:+.4f})"
            )

            return result, stats, best_metrics
        else:
            # No improvement found
            stats.tuned_score = original_score
            stats.gain = 0.0
            return code, stats, original_metrics
    except ValueError:
        # No completed trials
        logger.warning("[TUNING] No trials completed, using original values")
        stats.tuned_score = original_score
        stats.gain = 0.0
        return code, stats, original_metrics


def _rewrite_values_only(code: str, params: List[TuneParam], values: dict) -> str:
    """Rewrite just the values (no @TUNED annotation). Used during trial loop."""
    lines = code.split("\n")
    param_by_line = {p.line_number: p for p in params}

    for line_num, param in param_by_line.items():
        if line_num >= len(lines):
            continue
        new_val = values.get(param.name)
        if new_val is None:
            continue

        old_line = lines[line_num]
        indent = old_line[: len(old_line) - len(old_line.lstrip())]

        # Detect assignment operator (:= for Go, = for Python/etc)
        assign_op = ":=" if ":=" in old_line.split("#")[0].split("//")[0] else "="

        if param.param_type == "int":
            assign = f"{indent}{param.name} {assign_op} {int(new_val)}"
        else:
            assign = f"{indent}{param.name} {assign_op} {round(new_val, 4)}"

        # Preserve the comment part (everything from # or // onward)
        comment_match = re.search(r"(?:#|//).*$", old_line)
        comment = comment_match.group(0) if comment_match else ""

        lines[line_num] = f"{assign}  {comment}"

    return "\n".join(lines)
