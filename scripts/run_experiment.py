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
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)

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

    # Check ledger
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

    # Check programs in checkpoints for hypothesis comments
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

    # Check if best program has hypotheses
    best_prog_path = run_dir / "best" / "best_program.py"
    if not best_prog_path.exists():
        # Try other extensions
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
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    conditions = ["treatment", "control"] if args.condition == "both" else [args.condition]

    total_runs = len(conditions) * args.runs
    completed = 0

    results = []
    for condition in conditions:
        for i in range(args.runs):
            seed = args.seed_start + i
            completed += 1
            print(f"\n[{completed}/{total_runs}] {condition} seed={seed}")
            try:
                result = run_single(args.task, condition, seed, output_dir, iterations=args.iterations)
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
                print(f"      Hypothesis compliance: {progs}/{total} programs ({pct})")
                print(f"      Ledger: {h.get('ledger_entries', 0)} entries | "
                      f"confirmed={h.get('confirmed', 0)} refuted={h.get('refuted', 0)} "
                      f"inconclusive={h.get('inconclusive', 0)}")
                print(f"      Best program has hypotheses: {h.get('best_program_has_hypotheses', False)}")
            else:
                print(f"    seed={r['seed']}: FAILED")

    print(f"\nResults in {output_dir}")
    print(f"Run: python scripts/analyze_experiment.py --data {csv_path} --output {output_dir / 'plots'}")


if __name__ == "__main__":
    main()
