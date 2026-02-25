#!/usr/bin/env python3
"""
Run A/B experiment: hypothesis-driven vs vanilla OpenEvolve.

Usage:
    python scripts/run_experiment.py \
        --task blis_router \
        --condition treatment \
        --runs 3 \
        --seed-start 100 \
        --output-dir experiments/hypothesis_ab_blis

Each run gets an isolated output directory and random seed.
After all runs complete, convergence data is collected into a CSV.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

TASK_CONFIGS = {
    "blis_router": {
        "initial_program": "examples/blis_router/initial_program.py",
        "evaluator": "examples/blis_router/evaluator.py",
        "treatment_config": "examples/blis_router/config_experiment_treatment.yaml",
        "control_config": "examples/blis_router/config_experiment_control.yaml",
    },
    "function_minimization": {
        "initial_program": "examples/function_minimization/initial_program.py",
        "evaluator": "examples/function_minimization/evaluator.py",
        "treatment_config": "examples/function_minimization/config_experiment_treatment.yaml",
        "control_config": "examples/function_minimization/config_experiment_control.yaml",
    },
    "signal_processing": {
        "initial_program": "examples/signal_processing/initial_program.py",
        "evaluator": "examples/signal_processing/evaluator.py",
        "treatment_config": "examples/signal_processing/config_experiment_treatment.yaml",
        "control_config": "examples/signal_processing/config_experiment_control.yaml",
    },
}


def run_single(task: str, condition: str, seed: int, output_dir: Path) -> dict:
    """Run a single OpenEvolve experiment and return convergence data."""
    task_info = TASK_CONFIGS[task]
    config_path = task_info[f"{condition}_config"]

    run_dir = output_dir / f"{condition}_run_{seed}"
    run_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "openevolve-run.py",
        task_info["initial_program"],
        task_info["evaluator"],
        "--config", config_path,
        "--iterations", "10",
        "--output", str(run_dir),
    ]

    print(f"Starting {condition} run seed={seed} -> {run_dir}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

    if result.returncode != 0:
        print(f"  FAILED: {result.stderr[:500]}")
        return {"seed": seed, "condition": condition, "status": "failed", "error": result.stderr[:500]}

    # Collect convergence data from checkpoints
    convergence = collect_convergence(run_dir)
    return {"seed": seed, "condition": condition, "status": "ok", "convergence": convergence}


def collect_convergence(run_dir: Path) -> list:
    """Extract best_score at each checkpoint iteration."""
    checkpoints_dir = run_dir / "checkpoints"
    if not checkpoints_dir.exists():
        return []

    points = []
    for cp_dir in sorted(checkpoints_dir.iterdir()):
        if not cp_dir.is_dir():
            continue
        metrics_file = cp_dir / "best_metrics.json"
        if metrics_file.exists():
            with open(metrics_file) as f:
                metrics = json.load(f)
            iteration = int(cp_dir.name.split("_")[-1]) if "_" in cp_dir.name else 0
            points.append({
                "iteration": iteration,
                "best_combined_score": metrics.get("combined_score", 0),
            })
    return points


def write_csv(results: list, output_path: Path):
    """Write convergence data to CSV for analysis."""
    rows = []
    for r in results:
        if r["status"] != "ok":
            continue
        for point in r.get("convergence", []):
            rows.append({
                "condition": r["condition"],
                "seed": r["seed"],
                "iteration": point["iteration"],
                "best_combined_score": point["best_combined_score"],
            })

    if not rows:
        print("No convergence data to write")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["condition", "seed", "iteration", "best_combined_score"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote convergence CSV to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run hypothesis A/B experiment")
    parser.add_argument("--task", required=True, choices=list(TASK_CONFIGS.keys()))
    parser.add_argument("--condition", required=True, choices=["treatment", "control", "both"])
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=100)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    conditions = ["treatment", "control"] if args.condition == "both" else [args.condition]

    results = []
    for condition in conditions:
        for i in range(args.runs):
            seed = args.seed_start + i
            try:
                result = run_single(args.task, condition, seed, output_dir)
                results.append(result)
            except Exception as e:
                print(f"Run failed: {e}")
                results.append({"seed": seed, "condition": condition, "status": "error", "error": str(e)})

    # Write CSV
    csv_path = output_dir / "convergence.csv"
    write_csv(results, csv_path)

    # Write raw results
    with open(output_dir / "run_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nExperiment complete. Results in {output_dir}")


if __name__ == "__main__":
    main()
