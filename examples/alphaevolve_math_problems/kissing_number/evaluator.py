# ===--------------------------------------------------------------------------------------===#
#
# This file implements the evaluator for the kissing number problem on dimension 11.
#
# ===--------------------------------------------------------------------------------------===#
#
# Some of the code in this file is adapted from:
#
# google-deepmind/alphaevolve_results:
# Licensed under the Apache License v2.0.
#
# ===--------------------------------------------------------------------------------------===#

import json
import logging
import sys
import os
from importlib import __import__
from pathlib import Path
import time
import itertools
import numpy as np

from openevolve.evaluation_result import EvaluationResult
from openevolve.hypothesis import (
    parse_hypotheses,
    test_hypotheses,
    load_ledger,
    update_ledger,
    generate_knowledge_base_summary,
    format_hypothesis_results,
)

logger = logging.getLogger(__name__)

DIM = 11
TOL = 1e-6
BENCHMARK = 593
VALID_METRICS = {"num_points", "combined_score"}


def compute_squared_norm(point: list[int]) -> int:
    """Returns the squared norm of an integer vector using exact computation."""
    return sum(pow(int(x), 2) for x in point)


def verify_sphere_packing(sphere_centers: np.ndarray, tol: float = 1e-6):
    """Checks that after normalizing, the points correspond to a valid sphere packing for kissing numbers.

    Args:
        sphere_centers: the list of sphere centers, of shape [num_spheres, dimension].

    Raises:
        AssertionError: if the sphere packing is not a valid kissing configuration.
    """
    # Rounding to integers to guarantee exact computation throughout.
    sphere_centers = np.around(sphere_centers).astype(np.int64)
    squared_norms = [compute_squared_norm(list(center)) for center in sphere_centers]

    # Checks that the set doesn't contain 0.
    min_squared_norm = min(squared_norms)
    assert min_squared_norm > tol, f"Verification failed because the set contains 0."

    # Checks that the minimum pairwise distance between centers >= the maximum norm of the centers.
    max_squared_norm = max(squared_norms)
    min_squared_distance = min(
        compute_squared_norm(list(a - b)) for a, b in itertools.combinations(sphere_centers, 2)
    )
    assert (
        min_squared_distance >= max_squared_norm
    ), f"Verification failed because the minimum squared distance = {min_squared_distance} < {max_squared_norm} = maximum squared norm."


def evaluate(program_path: str):
    try:
        abs_program_path = os.path.abspath(program_path)
        program_dir = os.path.dirname(abs_program_path)
        module_name = os.path.splitext(os.path.basename(program_path))[0]

        try:
            sys.path.insert(0, program_dir)
            program = __import__(module_name)
            start_time = time.time()
            points = program.kissing_number11()
            end_time = time.time()
            eval_time = end_time - start_time
        except Exception as err:
            raise err
        finally:
            if program_dir in sys.path:
                sys.path.remove(program_dir)

        if not isinstance(points, np.ndarray):
            points = np.array(points)

        if points.shape[1] != 11:
            raise ValueError(
                f"Invalid shapes: points = {points.shape}, expected ({points.shape[1]},11)"
            )

        verify_sphere_packing(points, TOL)

        num_points = len(points)
        benchmark_ratio = num_points / BENCHMARK

        metrics = {
            "num_points": num_points,
            "combined_score": float(benchmark_ratio),
            "eval_time": float(eval_time),
        }
        artifacts = {}

        # --- Hypothesis pipeline (only when hypothesis_driven mode is enabled) ---
        hypothesis_enabled = os.environ.get("HYPOTHESIS_DRIVEN", "false") == "true"
        if hypothesis_enabled:
            try:
                with open(program_path, "r") as f:
                    source_code = f.read()

                hypotheses = parse_hypotheses(source_code, valid_metrics=VALID_METRICS)
                logger.info("[HYPOTHESIS] Parsed %d hypotheses from evolved code", len(hypotheses))

                if hypotheses:
                    run_output_dir = os.environ.get("OPENEVOLVE_OUTPUT_DIR")
                    if run_output_dir:
                        artifact_dir = Path(run_output_dir)
                    else:
                        artifact_dir = Path(__file__).parent / "openevolve_output"
                    artifact_dir.mkdir(parents=True, exist_ok=True)

                    baseline_path = artifact_dir / "baseline_metrics.json"
                    ledger_path = artifact_dir / "hypothesis_ledger.json"

                    if baseline_path.exists():
                        with open(baseline_path, "r") as f:
                            baseline_metrics = json.load(f)
                    else:
                        baseline_metrics = {
                            "num_points": 2,
                            "combined_score": 2 / BENCHMARK,
                        }
                        with open(baseline_path, "w") as f:
                            json.dump(baseline_metrics, f, indent=2)

                    actual_metrics = {
                        "num_points": num_points,
                        "combined_score": float(benchmark_ratio),
                    }

                    h_results = test_hypotheses(hypotheses, actual_metrics, baseline_metrics)
                    baseline_score = baseline_metrics.get("combined_score", 0)
                    hypothesis_results_text = format_hypothesis_results(
                        h_results, float(benchmark_ratio), baseline_score
                    )

                    ledger = load_ledger(ledger_path)
                    if not ledger["baseline"] and baseline_metrics:
                        ledger["baseline"] = baseline_metrics
                    update_ledger(ledger, h_results, float(benchmark_ratio), ledger_path)
                    logger.info("[HYPOTHESIS] Updated ledger (%d entries)", len(ledger.get("entries", [])))
                    knowledge_base_text = generate_knowledge_base_summary(ledger)

                    artifacts["hypothesis_results"] = hypothesis_results_text
                    artifacts["hypothesis_knowledge_base"] = knowledge_base_text
                else:
                    logger.info("[HYPOTHESIS] No hypotheses found in evolved code")
                    run_output_dir = os.environ.get("OPENEVOLVE_OUTPUT_DIR")
                    if run_output_dir:
                        ledger_path = Path(run_output_dir) / "hypothesis_ledger.json"
                    else:
                        ledger_path = Path(__file__).parent / "openevolve_output" / "hypothesis_ledger.json"
                    if ledger_path.exists():
                        ledger = load_ledger(ledger_path)
                        knowledge_base_text = generate_knowledge_base_summary(ledger)
                        if knowledge_base_text:
                            artifacts["hypothesis_knowledge_base"] = knowledge_base_text

            except Exception as e:
                logger.warning("[HYPOTHESIS] Pipeline error (non-fatal): %s", e)

        return EvaluationResult(metrics=metrics, artifacts=artifacts)

    except Exception as e:
        return {"combined_score": 0.0, "error": str(e)}
