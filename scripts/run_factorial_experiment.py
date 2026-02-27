#!/usr/bin/env python3
"""
Run 2x2 factorial experiment: hypothesis (off/on) x evolution mode (diff/full-rewrite).

Usage:
    python scripts/run_factorial_experiment.py \
        --task function_minimization \
        --condition all \
        --runs 3 \
        --seed-start 200 \
        --iterations 20 \
        --parallel \
        --output-dir experiments/factorial_ab_funcmin

Conditions:
    control_diff      — hypothesis=off, diff-based evolution
    treatment_diff    — hypothesis=on,  diff-based evolution
    control_full      — hypothesis=off, full-rewrite evolution
    treatment_full    — hypothesis=on,  full-rewrite evolution

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

ALL_CONDITIONS = ["control_diff", "treatment_diff", "control_full", "treatment_full"]

TASK_CONFIGS = {
    "function_minimization": {
        "initial_program": "examples/function_minimization/initial_program.py",
        "evaluator": "examples/function_minimization/evaluator.py",
        "control_diff_config": "examples/function_minimization/config_factorial_control_diff.yaml",
        "treatment_diff_config": "examples/function_minimization/config_factorial_treatment_diff.yaml",
        "control_full_config": "examples/function_minimization/config_factorial_control_full.yaml",
        "treatment_full_config": "examples/function_minimization/config_factorial_treatment_full.yaml",
    },
    "circle_packing": {
        "initial_program": "examples/circle_packing/initial_program.py",
        "evaluator": "examples/circle_packing/evaluator.py",
        "control_diff_config": "examples/circle_packing/config_factorial_control_diff.yaml",
        "treatment_diff_config": "examples/circle_packing/config_factorial_treatment_diff.yaml",
        "control_full_config": "examples/circle_packing/config_factorial_control_full.yaml",
        "treatment_full_config": "examples/circle_packing/config_factorial_treatment_full.yaml",
    },
    "kissing_number": {
        "initial_program": "examples/alphaevolve_math_problems/kissing_number/initial_program.py",
        "evaluator": "examples/alphaevolve_math_problems/kissing_number/evaluator.py",
        "control_diff_config": "examples/alphaevolve_math_problems/kissing_number/config_factorial_control_diff.yaml",
        "treatment_diff_config": "examples/alphaevolve_math_problems/kissing_number/config_factorial_treatment_diff.yaml",
        "control_full_config": "examples/alphaevolve_math_problems/kissing_number/config_factorial_control_full.yaml",
        "treatment_full_config": "examples/alphaevolve_math_problems/kissing_number/config_factorial_treatment_full.yaml",
    },
}


def run_single(task: str, condition: str, seed: int, output_dir: Path, iterations: int = 20) -> dict:
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

    env = os.environ.copy()
    env["OPENEVOLVE_OUTPUT_DIR"] = str(run_dir)

    print(f"\nStarting {condition} run seed={seed} ({iterations} iters) -> {run_dir}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200, env=env)

    (run_dir / "experiment_stdout.txt").write_text(result.stdout)
    (run_dir / "experiment_stderr.txt").write_text(result.stderr)

    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode}): {result.stderr[:500]}")
        return {"seed": seed, "condition": condition, "status": "failed", "error": result.stderr[:500]}

    convergence = collect_convergence(run_dir)
    ledger_info = check_hypothesis_stats(run_dir)
    diff_failures = count_diff_failures(run_dir)

    print(f"  OK: {len(convergence)} checkpoints, diff_failures={diff_failures}, {ledger_info}")
    return {
        "seed": seed,
        "condition": condition,
        "status": "ok",
        "convergence": convergence,
        "hypothesis": ledger_info,
        "diff_failures": diff_failures,
    }


def collect_convergence(run_dir: Path) -> list:
    """Extract best_score at each checkpoint iteration."""
    checkpoints_dir = run_dir / "checkpoints"
    if not checkpoints_dir.exists():
        return []

    points = []
    for cp_dir in sorted(checkpoints_dir.iterdir()):
        if not cp_dir.is_dir():
            continue
        info_file = cp_dir / "best_program_info.json"
        if info_file.exists():
            with open(info_file) as f:
                info = json.load(f)
            metrics = info.get("metrics", info)
            iteration = int(cp_dir.name.split("_")[-1]) if "_" in cp_dir.name else 0
            points.append({
                "iteration": iteration,
                "best_combined_score": metrics.get("combined_score", metrics.get("overall_score", 0)),
            })
    return points


def check_hypothesis_stats(run_dir: Path) -> dict:
    """Collect comprehensive hypothesis statistics for a run."""
    stats = {
        "ledger_exists": False,
        "ledger_entries": 0,
        "total_hypotheses_tested": 0,
        "confirmed": 0,
        "refuted": 0,
        "inconclusive": 0,
        "programs_with_hypotheses": 0,
        "total_evolved_programs": 0,
        "best_program_has_hypotheses": False,
    }

    ledger_path = run_dir / "hypothesis_ledger.json"
    if ledger_path.exists():
        stats["ledger_exists"] = True
        try:
            with open(ledger_path) as f:
                ledger = json.load(f)
            entries = ledger.get("entries", [])
            stats["ledger_entries"] = len(entries)
            for e in entries:
                for h in e.get("hypotheses", []):
                    stats["total_hypotheses_tested"] += 1
                    verdict = h.get("verdict", "")
                    if verdict == "CONFIRMED":
                        stats["confirmed"] += 1
                    elif verdict == "REFUTED":
                        stats["refuted"] += 1
                    else:
                        stats["inconclusive"] += 1
        except (json.JSONDecodeError, KeyError):
            pass

    for checkpoint_dir in sorted((run_dir / "checkpoints").glob("checkpoint_*")):
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

    best_prog_path = run_dir / "best" / "best_program.py"
    if best_prog_path.exists():
        try:
            code = best_prog_path.read_text()
            stats["best_program_has_hypotheses"] = ("HYPOTHESIS-" in code and "EXPECT-" in code)
        except OSError:
            pass

    return stats


def count_diff_failures(run_dir: Path) -> int:
    """Count diff parsing failures from stderr/logs."""
    count = 0
    for log_file in [run_dir / "experiment_stderr.txt"]:
        if log_file.exists():
            try:
                text = log_file.read_text()
                count += text.count("No valid diffs found")
                count += text.count("No valid code found")
            except OSError:
                pass
    # Also check log files in the logs directory
    logs_dir = run_dir / "logs"
    if logs_dir.exists():
        for log_file in logs_dir.glob("*.log"):
            try:
                text = log_file.read_text()
                count += text.count("No valid diffs found")
                count += text.count("No valid code found")
            except OSError:
                pass
    return count


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
    parser = argparse.ArgumentParser(description="Run 2x2 factorial hypothesis experiment")
    parser.add_argument("--task", required=True, choices=list(TASK_CONFIGS.keys()))
    parser.add_argument(
        "--condition", required=True,
        choices=ALL_CONDITIONS + ["all"],
        help="Which condition(s) to run. 'all' runs all 4.",
    )
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--seed-start", type=int, default=200)
    parser.add_argument("--iterations", type=int, default=20, help="Iterations per run")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--parallel", action="store_true", help="Run all conditions/seeds in parallel")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    conditions = ALL_CONDITIONS if args.condition == "all" else [args.condition]

    total_runs = len(conditions) * args.runs

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
    print(f"FACTORIAL EXPERIMENT COMPLETE: {args.task}")
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
                diff_fail = r.get("diff_failures", 0)
                print(f"    seed={r['seed']}: {cp} checkpoints, diff_failures={diff_fail}")
                print(f"      Hypothesis compliance: {progs}/{total} programs ({pct})")
                print(f"      Ledger: {h.get('ledger_entries', 0)} entries | "
                      f"confirmed={h.get('confirmed', 0)} refuted={h.get('refuted', 0)} "
                      f"inconclusive={h.get('inconclusive', 0)}")
            else:
                print(f"    seed={r['seed']}: FAILED")

    print(f"\nResults in {output_dir}")
    print(f"Run: python scripts/analyze_factorial_experiment.py "
          f"--data {csv_path} --results {output_dir / 'run_results.json'} "
          f"--output {output_dir / 'plots'}")


if __name__ == "__main__":
    main()
