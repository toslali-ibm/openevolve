#!/usr/bin/env python3
"""
Run A/B experiment: hypothesis-driven vs vanilla OpenEvolve.

Usage:
    python scripts/run_experiment.py \
        --task blis_router \
        --condition both \
        --runs 3 \
        --seed-start 100 \
        --iterations 10 \
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
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

TASK_CONFIGS = {
    "blis_router": {
        "initial_program": "examples/blis_router/initial_program.py",
        "evaluator": "examples/blis_router/evaluator.py",
        "treatment_config": "examples/blis_router/config_experiment_treatment.yaml",
        "control_config": "examples/blis_router/config_experiment_control.yaml",
    },
    "blis_router_tuning": {
        "initial_program": "examples/blis_router/initial_program.py",
        "evaluator": "examples/blis_router/evaluator.py",
        "treatment_config": "examples/blis_router/config_tuning_treatment.yaml",
        "control_config": "examples/blis_router/config_tuning_control.yaml",
    },
    "function_minimization": {
        "initial_program": "examples/function_minimization/initial_program.py",
        "evaluator": "examples/function_minimization/evaluator.py",
        "treatment_config": "examples/function_minimization/config_experiment_treatment.yaml",
        "control_config": "examples/function_minimization/config_experiment_control.yaml",
    },
    "circle_packing": {
        "initial_program": "examples/circle_packing/initial_program.py",
        "evaluator": "examples/circle_packing/evaluator.py",
        "treatment_config": "examples/circle_packing/config_experiment_treatment.yaml",
        "control_config": "examples/circle_packing/config_experiment_control.yaml",
    },
    "kissing_number": {
        "initial_program": "examples/alphaevolve_math_problems/kissing_number/initial_program.py",
        "evaluator": "examples/alphaevolve_math_problems/kissing_number/evaluator.py",
        "treatment_config": "examples/alphaevolve_math_problems/kissing_number/config_experiment_treatment.yaml",
        "control_config": "examples/alphaevolve_math_problems/kissing_number/config_experiment_control.yaml",
    },
    "heilbronn_triangle": {
        "initial_program": "examples/alphaevolve_math_problems/heilbronn_triangle/initial_program.py",
        "evaluator": "examples/alphaevolve_math_problems/heilbronn_triangle/evaluator.py",
        "treatment_config": "examples/alphaevolve_math_problems/heilbronn_triangle/config_experiment_treatment.yaml",
        "control_config": "examples/alphaevolve_math_problems/heilbronn_triangle/config_experiment_control.yaml",
    },
    "rust_adaptive_sort": {
        "initial_program": "examples/rust_adaptive_sort/initial_program.rs",
        "evaluator": "examples/rust_adaptive_sort/evaluator.py",
        "treatment_config": "examples/rust_adaptive_sort/config_experiment_treatment.yaml",
        "control_config": "examples/rust_adaptive_sort/config_experiment_control.yaml",
    },
    "circle_packing_tuning": {
        "initial_program": "examples/circle_packing/initial_program.py",
        "evaluator": "examples/circle_packing/evaluator.py",
        "treatment_config": "examples/circle_packing/config_tuning_treatment.yaml",
        "control_config": "examples/circle_packing/config_tuning_control.yaml",
    },
    "function_minimization_tuning": {
        "initial_program": "examples/function_minimization/initial_program.py",
        "evaluator": "examples/function_minimization/evaluator.py",
        "treatment_config": "examples/function_minimization/config_tuning_treatment.yaml",
        "control_config": "examples/function_minimization/config_tuning_control.yaml",
    },
    "web_scraper": {
        "initial_program": "examples/web_scraper_optillm/initial_program.py",
        "evaluator": "examples/web_scraper_optillm/evaluator.py",
        "treatment_config": "examples/web_scraper_optillm/config_experiment_treatment.yaml",
        "control_config": "examples/web_scraper_optillm/config_experiment_control.yaml",
    },
}


def run_single(task: str, condition: str, seed: int, output_dir: Path, iterations: int = 10) -> dict:
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
        "--iterations", str(iterations),
        "--output", str(run_dir),
    ]

    # Pass run-specific output dir to child process so evaluators write
    # hypothesis ledger / baseline metrics in isolation (not shared path).
    env = os.environ.copy()
    env["OPENEVOLVE_OUTPUT_DIR"] = str(run_dir)

    print(f"\nStarting {condition} run seed={seed} ({iterations} iters) -> {run_dir}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=14400, env=env)

    # Save stdout/stderr for debugging regardless of outcome
    (run_dir / "experiment_stdout.txt").write_text(result.stdout)
    (run_dir / "experiment_stderr.txt").write_text(result.stderr)

    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode}): {result.stderr[:500]}")
        return {"seed": seed, "condition": condition, "status": "failed", "error": result.stderr[:500]}

    # Collect convergence data from checkpoints
    convergence = collect_convergence(run_dir)
    ledger_info = check_hypothesis_stats(run_dir)

    print(f"  OK: {len(convergence)} checkpoints, {ledger_info}")
    return {"seed": seed, "condition": condition, "status": "ok", "convergence": convergence, "hypothesis": ledger_info}


def collect_convergence(run_dir: Path) -> list:
    """Extract best_score at each checkpoint iteration."""
    checkpoints_dir = run_dir / "checkpoints"
    if not checkpoints_dir.exists():
        return []

    points = []
    for cp_dir in sorted(checkpoints_dir.iterdir()):
        if not cp_dir.is_dir():
            continue
        # OpenEvolve saves best_program_info.json with metrics nested under "metrics"
        info_file = cp_dir / "best_program_info.json"
        if info_file.exists():
            with open(info_file) as f:
                info = json.load(f)
            metrics = info.get("metrics", info)  # fallback to top-level if no nested metrics
            iteration = int(cp_dir.name.split("_")[-1]) if "_" in cp_dir.name else 0
            points.append({
                "iteration": iteration,
                "best_combined_score": metrics.get("combined_score", metrics.get("overall_score", 0)),
            })
    return points


def check_hypothesis_stats(run_dir: Path) -> dict:
    """Collect hypothesis pipeline statistics for a run.

    Reads from hypothesis_tracker.json (V3 inline RESULT pipeline)
    with fallback to scanning checkpoints.
    """
    stats = {
        "tracker_exists": False,
        "total_iterations_tracked": 0,
        "total_hypotheses_generated": 0,
        "total_hypotheses_persisted": 0,
        "total_results_injected": 0,
        "total_iterations_with_parent_hypotheses": 0,
        "avg_hypotheses_per_iteration": 0,
        "persist_rate": 0,
        "inject_rate": 0,
        "inherit_rate": 0,
        "programs_with_hypotheses": 0,
        "total_evolved_programs": 0,
        "best_program_has_hypotheses": False,
    }

    # Primary: read hypothesis_tracker.json written by the pipeline
    tracker_path = run_dir / "hypothesis_tracker.json"
    # Also check inside db subdir (where process_parallel saves it)
    if not tracker_path.exists():
        tracker_path = run_dir / "db" / "hypothesis_tracker.json"
    if not tracker_path.exists():
        # Search for it
        for p in run_dir.rglob("hypothesis_tracker.json"):
            tracker_path = p
            break

    if tracker_path.exists():
        stats["tracker_exists"] = True
        try:
            with open(tracker_path) as f:
                tracker = json.load(f)
            stats["total_iterations_tracked"] = tracker.get("total_iterations_tracked", 0)
            stats["total_hypotheses_generated"] = tracker.get("total_hypotheses_generated", 0)
            stats["total_hypotheses_persisted"] = tracker.get("total_hypotheses_persisted", 0)
            stats["total_results_injected"] = tracker.get("total_results_injected", 0)
            stats["total_iterations_with_parent_hypotheses"] = tracker.get("total_iterations_with_parent_hypotheses", 0)
            stats["avg_hypotheses_per_iteration"] = tracker.get("avg_hypotheses_per_iteration", 0)
            stats["persist_rate"] = tracker.get("persist_rate", 0)
            stats["inject_rate"] = tracker.get("inject_rate", 0)
            stats["inherit_rate"] = tracker.get("inherit_rate", 0)
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: check programs in checkpoints for hypothesis comments
    checkpoints_dir = run_dir / "checkpoints"
    if checkpoints_dir.exists():
        for checkpoint_dir in sorted(checkpoints_dir.glob("checkpoint_*")):
            programs_dir = checkpoint_dir / "programs"
            if not programs_dir.exists():
                continue
            for prog_file in programs_dir.glob("*.json"):
                stats["total_evolved_programs"] += 1
                try:
                    prog = json.loads(prog_file.read_text())
                    code = prog.get("code", "")
                    if "HYPOTHESIS-" in code and "EXPECT-" in code:
                        stats["programs_with_hypotheses"] += 1
                except (json.JSONDecodeError, KeyError):
                    pass

    # Check if best program has hypotheses
    best_prog_path = run_dir / "best" / "best_program.py"
    if not best_prog_path.exists():
        for ext in [".go", ".r", ".rs"]:
            alt = run_dir / "best" / f"best_program{ext}"
            if alt.exists():
                best_prog_path = alt
                break
    if best_prog_path.exists():
        try:
            code = best_prog_path.read_text()
            stats["best_program_has_hypotheses"] = ("HYPOTHESIS-" in code and "EXPECT-" in code)
        except OSError:
            pass

    return stats


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
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per run")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parallel", action="store_true", help="Run all conditions/seeds in parallel")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    conditions = ["treatment", "control"] if args.condition == "both" else [args.condition]

    total_runs = len(conditions) * args.runs

    # Build list of (task, condition, seed) jobs
    jobs = []
    for condition in conditions:
        for i in range(args.runs):
            seed = args.seed_start + i
            jobs.append((args.task, condition, seed, output_dir, args.iterations))

    results = []
    if args.parallel:
        print(f"\nRunning {total_runs} jobs in parallel...")
        with ProcessPoolExecutor(max_workers=total_runs) as executor:
            future_to_job = {}
            for task, condition, seed, out, iters in jobs:
                future = executor.submit(run_single, task, condition, seed, out, iters)
                future_to_job[future] = (condition, seed)

            for future in as_completed(future_to_job):
                condition, seed = future_to_job[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"Run {condition} seed={seed} failed: {e}")
                    results.append({"seed": seed, "condition": condition, "status": "error", "error": str(e)})
    else:
        completed = 0
        for task, condition, seed, out, iters in jobs:
            completed += 1
            print(f"\n[{completed}/{total_runs}] {condition} seed={seed}")
            try:
                result = run_single(task, condition, seed, out, iters)
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

    # Print summary
    print(f"\n{'='*70}")
    print(f"EXPERIMENT COMPLETE: {args.task}")
    print(f"{'='*70}")
    for condition in conditions:
        cond_results = [r for r in results if r["condition"] == condition]
        ok = sum(1 for r in cond_results if r["status"] == "ok")
        failed = len(cond_results) - ok
        print(f"\n  {condition.upper()}: {ok} OK, {failed} failed")
        for r in cond_results:
            if r["status"] == "ok":
                h = r.get("hypothesis", {})
                cp = len(r.get("convergence", []))
                progs = h.get("programs_with_hypotheses", 0)
                total = h.get("total_evolved_programs", 0)
                pct = f"{100*progs/total:.0f}%" if total > 0 else "N/A"
                print(f"    seed={r['seed']}: {cp} checkpoints")
                if h.get("tracker_exists"):
                    print(f"      Pipeline tracking ({h.get('total_iterations_tracked', 0)} iters):")
                    print(f"        Generated: {h.get('total_hypotheses_generated', 0)} "
                          f"(avg {h.get('avg_hypotheses_per_iteration', 0)}/iter)")
                    print(f"        Persisted: {h.get('total_hypotheses_persisted', 0)} "
                          f"(rate={h.get('persist_rate', 0):.0%})")
                    print(f"        Results injected: {h.get('total_results_injected', 0)} "
                          f"(rate={h.get('inject_rate', 0):.0%})")
                    print(f"        Inherited (parent had hypos): "
                          f"{h.get('total_iterations_with_parent_hypotheses', 0)} "
                          f"(rate={h.get('inherit_rate', 0):.0%})")
                print(f"      Programs w/ hypotheses: {progs}/{total} ({pct})")
                print(f"      Best program has hypotheses: {h.get('best_program_has_hypotheses', False)}")
            else:
                print(f"    seed={r['seed']}: FAILED")

    print(f"\nResults in {output_dir}")
    print(f"Run: python scripts/analyze_experiment.py --data {csv_path} --output {output_dir / 'plots'}")


if __name__ == "__main__":
    main()
