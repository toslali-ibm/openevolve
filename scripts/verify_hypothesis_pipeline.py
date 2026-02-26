#!/usr/bin/env python3
"""
Verify the hypothesis-driven evolution pipeline end-to-end.

Runs a SHORT experiment (3 iterations, treatment + control) for function_minimization,
then inspects logs, ledger, and artifacts to confirm the pipeline works correctly.

Usage:
    python scripts/verify_hypothesis_pipeline.py

Checks:
  [TREATMENT]
    1. LLM generated hypothesis comments in evolved code
    2. Hypotheses were parsed correctly (parse_hypotheses found them)
    3. Ledger was populated (hypothesis_ledger.json exists and has entries)
    4. Knowledge base was generated (hypothesis_knowledge_base artifact exists)
    5. System prompt contains hypothesis instructions (not doubled)

  [CONTROL]
    6. System prompt does NOT contain hypothesis instructions
    7. Ledger is empty or does not exist
    8. No hypothesis_knowledge_base artifact
"""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VERIFY_DIR = REPO_ROOT / "experiments" / "_verify_hypothesis"


def run_openevolve(condition: str, output_dir: Path, iterations: int = 3) -> bool:
    """Run a short OpenEvolve experiment and return True if it succeeded."""
    task = "function_minimization"
    config_suffix = "treatment" if condition == "treatment" else "control"
    config_path = f"examples/{task}/config_experiment_{config_suffix}.yaml"

    cmd = [
        sys.executable, "openevolve-run.py",
        f"examples/{task}/initial_program.py",
        f"examples/{task}/evaluator.py",
        "--config", config_path,
        "--iterations", str(iterations),
        "--output", str(output_dir),
    ]

    env = os.environ.copy()
    env["OPENEVOLVE_OUTPUT_DIR"] = str(output_dir)

    print(f"\n{'='*60}")
    print(f"Running {condition.upper()} ({iterations} iterations) -> {output_dir}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=env, cwd=str(REPO_ROOT))

    # Save stdout/stderr for debugging
    (output_dir / "stdout.txt").write_text(result.stdout)
    (output_dir / "stderr.txt").write_text(result.stderr)

    if result.returncode != 0:
        print(f"  FAILED (exit code {result.returncode})")
        print(f"  stderr: {result.stderr[:500]}")
        return False

    print(f"  OK")
    return True


def find_log_file(output_dir: Path) -> Path | None:
    """Find the OpenEvolve log file in the output directory."""
    log_dir = output_dir / "logs"
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob("openevolve_*.log"))
    return logs[-1] if logs else None


def check_treatment(output_dir: Path) -> dict:
    """Run all treatment checks and return results."""
    results = {}

    # Check 1: Look for hypothesis comments in evolved programs
    programs_found_with_hypotheses = 0
    total_programs = 0
    for checkpoint_dir in sorted((output_dir / "checkpoints").glob("checkpoint_*")):
        programs_dir = checkpoint_dir / "programs"
        if not programs_dir.exists():
            continue
        for prog_file in programs_dir.glob("*.json"):
            total_programs += 1
            try:
                prog = json.loads(prog_file.read_text())
                code = prog.get("code", "")
                if "HYPOTHESIS-" in code and "MECHANISM-" in code and "EXPECT-" in code:
                    programs_found_with_hypotheses += 1
            except (json.JSONDecodeError, KeyError):
                pass

    results["programs_with_hypotheses"] = programs_found_with_hypotheses
    results["total_programs"] = total_programs
    results["check_1_hypotheses_in_code"] = programs_found_with_hypotheses > 0

    # Check 2: Hypotheses were parsed (look in log for [HYPOTHESIS] Parsed)
    log_file = find_log_file(output_dir)
    parsed_count = 0
    verdict_count = 0
    kb_generated = False
    prompt_has_hypothesis = False
    prompt_doubled = False

    if log_file:
        log_text = log_file.read_text()
        for line in log_text.splitlines():
            if "[HYPOTHESIS] Parsed" in line and "hypotheses from evolved code" in line:
                # Extract count: "[HYPOTHESIS] Parsed 3 hypotheses..."
                parts = line.split("Parsed ")[1] if "Parsed " in line else ""
                try:
                    n = int(parts.split(" ")[0])
                    parsed_count += n
                except (ValueError, IndexError):
                    pass
            if "[HYPOTHESIS]" in line and "verdict=" in line:
                verdict_count += 1
            if "[HYPOTHESIS] Knowledge base:" in line:
                kb_generated = True
            if "config already contains hypothesis instructions" in line:
                prompt_has_hypothesis = True
            if "Appended generic hypothesis template" in line:
                prompt_doubled = True

    results["hypotheses_parsed_total"] = parsed_count
    results["check_2_hypotheses_parsed"] = parsed_count > 0
    results["verdicts_recorded"] = verdict_count
    results["check_3_verdicts_recorded"] = verdict_count > 0

    # Check 3: Ledger exists and has entries
    ledger_path = output_dir / "hypothesis_ledger.json"
    ledger_entries = 0
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text())
            ledger_entries = len(ledger.get("entries", []))
        except (json.JSONDecodeError, KeyError):
            pass
    results["ledger_entries"] = ledger_entries
    results["check_4_ledger_populated"] = ledger_entries > 0

    # Check 4: Knowledge base was generated
    results["check_5_knowledge_base_generated"] = kb_generated

    # Check 5: Prompt not doubled
    results["check_6_prompt_not_doubled"] = prompt_has_hypothesis and not prompt_doubled

    return results


def check_control(output_dir: Path) -> dict:
    """Run all control checks and return results."""
    results = {}

    # Check 6: System prompt does NOT contain hypothesis instructions
    log_file = find_log_file(output_dir)
    hypothesis_in_prompt = False
    if log_file:
        log_text = log_file.read_text()
        hypothesis_in_prompt = "hypothesis_driven=true" in log_text.lower() or "[HYPOTHESIS] Appended" in log_text

    results["check_7_no_hypothesis_in_prompt"] = not hypothesis_in_prompt

    # Check 7: Ledger is empty or does not exist
    ledger_path = output_dir / "hypothesis_ledger.json"
    ledger_empty = True
    if ledger_path.exists():
        try:
            ledger = json.loads(ledger_path.read_text())
            if len(ledger.get("entries", [])) > 0:
                ledger_empty = False
        except (json.JSONDecodeError, KeyError):
            pass
    results["check_8_ledger_empty"] = ledger_empty

    # Check 8: No hypothesis artifacts in programs
    programs_with_hypotheses = 0
    for checkpoint_dir in sorted((output_dir / "checkpoints").glob("checkpoint_*")):
        programs_dir = checkpoint_dir / "programs"
        if not programs_dir.exists():
            continue
        for prog_file in programs_dir.glob("*.json"):
            try:
                prog = json.loads(prog_file.read_text())
                code = prog.get("code", "")
                if "HYPOTHESIS-" in code and "EXPECT-" in code:
                    programs_with_hypotheses += 1
            except (json.JSONDecodeError, KeyError):
                pass
    results["control_programs_with_hypotheses"] = programs_with_hypotheses
    # Allow some leakage (LLM might generate hypothesis-like comments unprompted)
    results["check_9_minimal_hypothesis_leakage"] = programs_with_hypotheses == 0

    return results


def main():
    import shutil

    # Clean up previous verification runs
    if VERIFY_DIR.exists():
        shutil.rmtree(VERIFY_DIR)
    VERIFY_DIR.mkdir(parents=True)

    treatment_dir = VERIFY_DIR / "treatment"
    control_dir = VERIFY_DIR / "control"

    iterations = 3
    treatment_ok = run_openevolve("treatment", treatment_dir, iterations=iterations)
    control_ok = run_openevolve("control", control_dir, iterations=iterations)

    print(f"\n{'='*60}")
    print("VERIFICATION RESULTS")
    print(f"{'='*60}")

    all_pass = True

    if treatment_ok:
        treatment_results = check_treatment(treatment_dir)
        print(f"\n--- TREATMENT ({iterations} iterations) ---")
        for k, v in treatment_results.items():
            if k.startswith("check_"):
                status = "PASS" if v else "FAIL"
                if not v:
                    all_pass = False
                print(f"  [{status}] {k}: {v}")
            else:
                print(f"         {k}: {v}")
    else:
        all_pass = False
        print("\n--- TREATMENT: RUN FAILED ---")

    if control_ok:
        control_results = check_control(control_dir)
        print(f"\n--- CONTROL ({iterations} iterations) ---")
        for k, v in control_results.items():
            if k.startswith("check_"):
                status = "PASS" if v else "FAIL"
                if not v:
                    all_pass = False
                print(f"  [{status}] {k}: {v}")
            else:
                print(f"         {k}: {v}")
    else:
        all_pass = False
        print("\n--- CONTROL: RUN FAILED ---")

    print(f"\n{'='*60}")
    if all_pass:
        print("OVERALL: ALL CHECKS PASSED")
    else:
        print("OVERALL: SOME CHECKS FAILED -- review above")
    print(f"Verification data: {VERIFY_DIR}")
    print(f"{'='*60}")

    # Save results JSON
    all_results = {
        "treatment_ran": treatment_ok,
        "control_ran": control_ok,
    }
    if treatment_ok:
        all_results["treatment"] = treatment_results
    if control_ok:
        all_results["control"] = control_results
    all_results["all_pass"] = all_pass

    with open(VERIFY_DIR / "verification_results.json", "w") as f:
        json.dump(all_results, f, indent=2)

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
