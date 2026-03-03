"""
Structured threshold tuning for OpenEvolve.

Parses @TUNE annotations from LLM-generated code, runs Optuna to find
optimal threshold values, and rewrites code with @TUNED feedback.
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


def strip_tuned_annotations(code: str) -> str:
    """Remove all @TUNED(...) annotations from code, preserving @TUNE."""
    return _TUNED_RE.sub("", code)


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
    """Per-iteration tuning pipeline statistics."""

    iteration: int = 0
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


@dataclass
class TuningTracker:
    """Aggregates tuning statistics across iterations."""

    iterations: list = field(default_factory=list)
    total_iterations: int = 0
    total_iterations_with_tuning: int = 0
    total_trials: int = 0
    total_gain: float = 0.0
    total_tuning_duration_s: float = 0.0

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

        # Log per-iteration summary
        if stats.tuning_ran:
            logger.info(
                f"[TUNE-TRACK] iter={stats.iteration} | "
                f"annotations={stats.tune_annotations_found}"
                f"→{stats.tune_annotations_honored} "
                f"trials={stats.trials_completed}ok/{stats.trials_failed}fail "
                f"score={stats.original_score:.4f}→{stats.tuned_score:.4f} "
                f"gain={stats.gain:+.4f} "
                f"duration={stats.tuning_duration_s:.1f}s "
                f"params={list(stats.param_changes.keys())}"
            )
        else:
            logger.info(
                f"[TUNE-TRACK] iter={stats.iteration} | "
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
        return {
            "total_iterations_tracked": self.total_iterations,
            "total_iterations_with_tuning": self.total_iterations_with_tuning,
            "total_trials": self.total_trials,
            "avg_gain_when_tuned": round(avg_gain, 4),
            "avg_tuning_duration_s": round(avg_duration, 2),
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
) -> Tuple[str, IterationTuningStats]:
    """Optimize @TUNE thresholds using Optuna, return rewritten code and stats.

    Args:
        code: Child program code with @TUNE annotations.
        evaluate_fn: Async function(code, program_id) -> metrics dict.
        config: TuningConfig with budget, max_params, etc.

    Returns:
        Tuple of (optimized code, stats).
        Falls back to original code if tuning fails.
    """
    stats = IterationTuningStats()
    start_time = time.time()

    # Strip any existing @TUNED from inherited parent annotations
    code = strip_tuned_annotations(code)

    # Parse @TUNE annotations — count all, honor up to max_params
    all_params = parse_tune_annotations(code, max_params=999)
    params = all_params[: config.max_params]
    stats.tune_annotations_found = len(all_params)
    stats.tune_annotations_honored = len(params)

    if not params:
        return code, stats

    try:
        import optuna
    except ImportError:
        raise ImportError(
            "Optuna is required for threshold tuning. "
            "Install it with: pip install openevolve[tuning]"
        )

    # Suppress Optuna's verbose logging
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    n_trials = config.budget + len(params) * config.budget_scale_per_param

    # Evaluate original code first to get baseline
    try:
        original_metrics = await evaluate_fn(code, "tune_baseline")
        original_score = original_metrics.get("combined_score", 0.0)
    except Exception:
        logger.warning("[TUNING] Baseline evaluation failed, skipping tuning")
        return code, stats

    # Track best result
    best_score = original_score
    best_values = {p.name: p.value for p in params}
    best_metrics = original_metrics.copy()

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

        # Evaluate — run async evaluate in a new event loop
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

    # Run Optuna study in executor to avoid blocking async loop
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(),
    )

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
    except ValueError:
        # No completed trials
        logger.warning("[TUNING] No trials completed, using original values")
        stats.tuned_score = original_score
        stats.gain = 0.0
        return code, stats

    stats.tuned_score = best_score
    stats.gain = best_score - original_score
    stats.param_changes = {
        p.name: {"was": p.value, "now": best_values.get(p.name, p.value)} for p in params
    }

    # Rewrite with @TUNED annotations
    result = rewrite_tune_values(
        code,
        params,
        best_values,
        original_score,
        best_score,
        original_metrics,
        best_metrics,
    )

    gain = best_score - original_score
    logger.info(
        f"[TUNING] Optimized {len(params)} params over {n_trials} trials: "
        f"score {original_score:.4f} → {best_score:.4f} (gain={gain:+.4f})"
    )

    return result, stats


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
