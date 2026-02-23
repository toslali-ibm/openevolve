#!/usr/bin/env python3
"""
Workload Validation Script for BLIS Router

Tests 4 routing configurations against all specified workloads to verify
that workloads are routing-sensitive (i.e., different routing strategies
produce meaningfully different latencies).

Configurations tested:
  1. sabotaged   - Always route to instance 0 (ignores scores)
  2. prefix-only - prefix-affinity=1.0, load-balance=0.01
  3. load-only   - prefix-affinity=0.01, load-balance=1.0
  4. baseline    - prefix-affinity=1.0, load-balance=1.0
  5. oracle      - Hand-crafted adaptive router (oracle_program.py)

Usage:
  # Test v2 workloads (default)
  python validate_workloads.py

  # Test specific workloads
  python validate_workloads.py workload_v2_multiturn.yaml workload_v2_load_spikes.yaml

  # Test all workloads (v1 + v2)
  python validate_workloads.py --all

  # Override model
  BLIS_MODEL=Qwen/Qwen2-7B python validate_workloads.py
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
INFERENCE_SIM_DIR = SCRIPT_DIR / "inference-sim"
ROUTING_GO_PATH = INFERENCE_SIM_DIR / "sim" / "routing.go"
POLICY_PATH = SCRIPT_DIR / "routing_policy.yaml"

SIM_MODEL = os.environ.get("BLIS_MODEL", "meta-llama/llama-3.1-8b-instruct")

# The normal argmax EVOLVE-BLOCK (from initial_program.py)
NORMAL_EVOLVE_BLOCK = """\t// EVOLVE-BLOCK-START
\t// Compute composite scores from all scorers
\tscores := make(map[string]float64, len(snapshots))
\tfor i, scorer := range ws.scorers {
\t\tdimScores := scorer(req, snapshots)
\t\tfor _, snap := range snapshots {
\t\t\ts := dimScores[snap.ID]
\t\t\t// Clamp to [0,1] per INV-1
\t\t\tif s < 0 {
\t\t\t\ts = 0
\t\t\t}
\t\t\tif s > 1 {
\t\t\t\ts = 1
\t\t\t}
\t\t\tscores[snap.ID] += s * ws.weights[i]
\t\t}
\t}

\t// Argmax: select instance with highest composite score.
\t// Ties broken by first occurrence in snapshot order (strict >).
\tbestScore := -1.0
\tbestIdx := 0
\tfor i, snap := range snapshots {
\t\tif scores[snap.ID] > bestScore {
\t\t\tbestScore = scores[snap.ID]
\t\t\tbestIdx = i
\t\t}
\t}
\t// EVOLVE-BLOCK-END"""

# Sabotaged: always pick instance 0 regardless of scores
SABOTAGED_EVOLVE_BLOCK = """\t// EVOLVE-BLOCK-START
\t// Compute composite scores from all scorers
\tscores := make(map[string]float64, len(snapshots))
\tfor i, scorer := range ws.scorers {
\t\tdimScores := scorer(req, snapshots)
\t\tfor _, snap := range snapshots {
\t\t\ts := dimScores[snap.ID]
\t\t\t// Clamp to [0,1] per INV-1
\t\t\tif s < 0 {
\t\t\t\ts = 0
\t\t\t}
\t\t\tif s > 1 {
\t\t\t\ts = 1
\t\t\t}
\t\t\tscores[snap.ID] += s * ws.weights[i]
\t\t}
\t}

\t// SABOTAGED: Always pick instance 0 regardless of scores
\tbestScore := scores[snapshots[0].ID]
\tbestIdx := 0
\t// EVOLVE-BLOCK-END"""

# Oracle: load-enhanced scoring with SLO-awareness
ORACLE_EVOLVE_BLOCK = """\t// EVOLVE-BLOCK-START
\t// Compute composite scores from all scorers
\tscores := make(map[string]float64, len(snapshots))
\tfor i, scorer := range ws.scorers {
\t\tdimScores := scorer(req, snapshots)
\t\tfor _, snap := range snapshots {
\t\t\ts := dimScores[snap.ID]
\t\t\tif s < 0 {
\t\t\t\ts = 0
\t\t\t}
\t\t\tif s > 1 {
\t\t\t\ts = 1
\t\t\t}
\t\t\tscores[snap.ID] += s * ws.weights[i]
\t\t}
\t}

\t// Recompute: prefix-affinity creates 0.8 vs 0.0 gaps that dominate.
\t// Load-balance adds ~0.02. Fix: 85% load, 15% original as tiebreaker.
\tfor _, snap := range snapshots {
\t\tload := float64(snap.EffectiveLoad())
\t\tloadScore := 1.0 / (1.0 + load)
\t\toriginal := scores[snap.ID]
\t\tscores[snap.ID] = original*0.15 + loadScore*0.85
\t}

\t// SLO-aware: realtime requests prefer idle instances
\tif req.SLOClass == "realtime" {
\t\tfor _, snap := range snapshots {
\t\t\tif snap.QueueDepth > 5 {
\t\t\t\tscores[snap.ID] *= 0.7
\t\t\t}
\t\t}
\t}

\tbestScore := -1.0
\tbestIdx := 0
\tfor i, snap := range snapshots {
\t\tif scores[snap.ID] > bestScore {
\t\t\tbestScore = scores[snap.ID]
\t\t\tbestIdx = i
\t\t}
\t}
\t// EVOLVE-BLOCK-END"""

# Policy YAML templates
POLICY_TEMPLATE = """\
admission:
  policy: always-admit
priority:
  policy: constant
routing:
  policy: weighted
  scorers:
  - name: prefix-affinity
    weight: {prefix_weight}
  - name: load-balance
    weight: {load_weight}
scheduler: fcfs
"""

# The 4 test configurations
CONFIGS = {
    "sabotaged": {
        "description": "Always route to instance 0",
        "prefix_weight": 1.0,
        "load_weight": 1.0,
        "custom_evolve_block": SABOTAGED_EVOLVE_BLOCK,
    },
    "prefix-only": {
        "description": "prefix-affinity=1.0, load-balance=0.01",
        "prefix_weight": 1.0,
        "load_weight": 0.01,
        "custom_evolve_block": None,
    },
    "load-only": {
        "description": "prefix-affinity=0.01, load-balance=1.0",
        "prefix_weight": 0.01,
        "load_weight": 1.0,
        "custom_evolve_block": None,
    },
    "baseline": {
        "description": "prefix-affinity=1.0, load-balance=1.0",
        "prefix_weight": 1.0,
        "load_weight": 1.0,
        "custom_evolve_block": None,
    },
    "oracle": {
        "description": "Adaptive: load penalty + SLO-aware + cache boost",
        "prefix_weight": 1.0,
        "load_weight": 1.0,
        "custom_evolve_block": ORACLE_EVOLVE_BLOCK,
    },
}


def build_sim_cmd(workload_path: Path) -> list[str]:
    """Build the simulation command for a workload."""
    cmd = [
        "./simulation_worker",
        "run",
        "--model",
        SIM_MODEL,
        "--num-instances",
        "4",
        "--policy-config",
        str(POLICY_PATH),
        "--workload-spec",
        str(workload_path),
        "--log",
        "info",
    ]
    if "Qwen" in SIM_MODEL:
        cmd += [
            "--hardware",
            "H100",
            "--tp",
            "1",
            "--alpha-coeffs",
            "4680.303204056608,0.0,0.0",
            "--beta-coeffs",
            "7051.796874715078,19.538416565504026,25.431830886933543",
            "--total-kv-blocks",
            "65833",
            "--max-num-running-reqs",
            "256",
            "--max-num-scheduled-tokens",
            "4096",
        ]
    return cmd


def parse_cluster_metrics(output_text: str) -> dict | None:
    """Parse cluster-wide metrics from simulation output."""
    json_blocks = []
    in_json = False
    json_buffer = ""
    brace_count = 0
    for line in output_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("{"):
            in_json = True
            brace_count = 0
        if in_json:
            json_buffer += line + "\n"
            brace_count += stripped.count("{") - stripped.count("}")
            if brace_count == 0 and json_buffer.strip():
                try:
                    json_blocks.append(json.loads(json_buffer))
                except json.JSONDecodeError:
                    pass
                json_buffer = ""
                in_json = False
    for block in json_blocks:
        if block.get("instance_id") == "cluster":
            return block
    return None


def apply_config(config_name: str, original_go_code: str) -> bool:
    """Apply a routing configuration. Returns True on success."""
    cfg = CONFIGS[config_name]

    # Write policy YAML
    policy_text = POLICY_TEMPLATE.format(
        prefix_weight=cfg["prefix_weight"],
        load_weight=cfg["load_weight"],
    )
    POLICY_PATH.write_text(policy_text)

    # Replace EVOLVE-BLOCK if custom code provided, else restore original
    custom_block = cfg.get("custom_evolve_block")
    if custom_block:
        modified = original_go_code.replace(NORMAL_EVOLVE_BLOCK, custom_block)
        if modified == original_go_code:
            print(f"  ERROR: Could not find EVOLVE-BLOCK to replace")
            return False
        ROUTING_GO_PATH.write_text(modified)
    else:
        ROUTING_GO_PATH.write_text(original_go_code)

    # Build
    result = subprocess.run(
        ["go", "build", "-o", "simulation_worker", "main.go"],
        cwd=INFERENCE_SIM_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        print(f"  BUILD FAILED: {result.stderr[:200]}")
        return False

    return True


def run_workload(workload_path: Path) -> dict | None:
    """Run a single workload and return cluster metrics."""
    cmd = build_sim_cmd(workload_path)
    try:
        result = subprocess.run(
            cmd,
            cwd=INFERENCE_SIM_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            print(f"    FAILED: {result.stderr[:200]}")
            return None
        output = result.stdout + (result.stderr or "")
        return parse_cluster_metrics(output)
    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT (180s)")
        return None


def find_workloads(args) -> list[Path]:
    """Determine which workloads to test."""
    if args.all:
        pattern = "workload_*.yaml"
    elif args.workloads:
        return [SCRIPT_DIR / w for w in args.workloads]
    else:
        # Default: v2 workloads
        pattern = "workload_v2_*.yaml"

    files = sorted(SCRIPT_DIR.glob(pattern))
    if not files:
        print(f"No workloads found matching {pattern}")
        sys.exit(1)
    return files


def main():
    parser = argparse.ArgumentParser(description="Validate BLIS workloads for routing sensitivity")
    parser.add_argument("workloads", nargs="*", help="Specific workload YAML files to test")
    parser.add_argument("--all", action="store_true", help="Test all workloads (v1 + v2)")
    parser.add_argument(
        "--configs",
        nargs="*",
        default=list(CONFIGS.keys()),
        choices=list(CONFIGS.keys()),
        help="Which configs to test (default: all 4)",
    )
    args = parser.parse_args()

    workload_paths = find_workloads(args)
    workload_names = [p.stem.replace("workload_", "") for p in workload_paths]

    print(f"Model: {SIM_MODEL}")
    print(f"Workloads: {', '.join(workload_names)}")
    print(f"Configs: {', '.join(args.configs)}")
    print()

    # Extract Go code from initial_program.py (not routing.go which may be stale)
    initial_program_path = SCRIPT_DIR / "initial_program.py"
    initial_text = initial_program_path.read_text()
    match = re.search(r'GO_ROUTING_CODE\s*=\s*"""(.*?)"""', initial_text, re.DOTALL)
    if not match:
        print("ERROR: Could not extract GO_ROUTING_CODE from initial_program.py")
        sys.exit(1)
    original_go_code = match.group(1).strip()
    original_policy = POLICY_PATH.read_text()

    # Results: config_name -> workload_name -> {e2e_mean_ms, e2e_p95_ms}
    results = {}

    try:
        for config_name in args.configs:
            cfg = CONFIGS[config_name]
            print(f"=== {config_name}: {cfg['description']} ===")

            if not apply_config(config_name, original_go_code):
                print(f"  Skipping {config_name} (build failed)\n")
                continue

            results[config_name] = {}
            for wpath, wname in zip(workload_paths, workload_names):
                print(f"  Running {wname}...", end=" ", flush=True)
                metrics = run_workload(wpath)
                if metrics and "e2e_mean_ms" in metrics:
                    e2e = float(metrics["e2e_mean_ms"])
                    p95 = float(metrics.get("e2e_p95_ms", e2e))
                    results[config_name][wname] = {"e2e_mean_ms": e2e, "e2e_p95_ms": p95}
                    print(f"mean={e2e:.1f}ms  p95={p95:.1f}ms")
                else:
                    results[config_name][wname] = None
                    print("FAILED")

            print()

    finally:
        # Always restore originals
        ROUTING_GO_PATH.write_text(original_go_code)
        POLICY_PATH.write_text(original_policy)
        # Rebuild with original code
        subprocess.run(
            ["go", "build", "-o", "simulation_worker", "main.go"],
            cwd=INFERENCE_SIM_DIR,
            capture_output=True,
            timeout=60,
        )
        print("(Restored original routing.go and routing_policy.yaml)\n")

    # Print comparison table
    print_results_table(results, workload_names, args.configs)

    # Save results to JSON
    out_path = SCRIPT_DIR / "validation_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")


def print_results_table(results: dict, workload_names: list[str], config_names: list[str]):
    """Print a formatted comparison table with % change from baseline."""
    baseline_key = "baseline" if "baseline" in results else None

    # Header
    col_w = 14
    wk_w = max(len(w) for w in workload_names) + 2
    header = f"{'Workload':<{wk_w}}"
    for cfg in config_names:
        header += f"  {cfg:>{col_w}}"
    if baseline_key:
        for cfg in config_names:
            if cfg != baseline_key:
                header += f"  {'%Δ ' + cfg:>{col_w}}"

    print("=" * len(header))
    print("E2E Mean Latency (ms)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for wname in workload_names:
        row = f"{wname:<{wk_w}}"
        baseline_val = None

        # Absolute values
        for cfg in config_names:
            val = results.get(cfg, {}).get(wname)
            if val:
                row += f"  {val['e2e_mean_ms']:>{col_w}.1f}"
                if cfg == baseline_key:
                    baseline_val = val["e2e_mean_ms"]
            else:
                row += f"  {'FAIL':>{col_w}}"

        # % change from baseline
        if baseline_key and baseline_val:
            for cfg in config_names:
                if cfg == baseline_key:
                    continue
                val = results.get(cfg, {}).get(wname)
                if val:
                    pct = (val["e2e_mean_ms"] - baseline_val) / baseline_val * 100
                    marker = "!" if abs(pct) > 5 else " "
                    row += f"  {pct:>+{col_w - 1}.1f}%{marker}"
                else:
                    row += f"  {'N/A':>{col_w}}"

        print(row)

    print("-" * len(header))

    # P95 table
    print()
    print("=" * len(header))
    print("E2E P95 Latency (ms)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for wname in workload_names:
        row = f"{wname:<{wk_w}}"
        baseline_val = None

        for cfg in config_names:
            val = results.get(cfg, {}).get(wname)
            if val:
                row += f"  {val['e2e_p95_ms']:>{col_w}.1f}"
                if cfg == baseline_key:
                    baseline_val = val["e2e_p95_ms"]
            else:
                row += f"  {'FAIL':>{col_w}}"

        if baseline_key and baseline_val:
            for cfg in config_names:
                if cfg == baseline_key:
                    continue
                val = results.get(cfg, {}).get(wname)
                if val:
                    pct = (val["e2e_p95_ms"] - baseline_val) / baseline_val * 100
                    marker = "!" if abs(pct) > 5 else " "
                    row += f"  {pct:>+{col_w - 1}.1f}%{marker}"
                else:
                    row += f"  {'N/A':>{col_w}}"

        print(row)

    print("-" * len(header))

    # Summary
    if baseline_key:
        print()
        print("Legend: %Δ = change vs baseline  |  ! = >5% change (routing-sensitive)")
        print()

        # Count sensitive workloads per config
        for cfg in config_names:
            if cfg == baseline_key:
                continue
            sensitive = 0
            total = 0
            for wname in workload_names:
                base = results.get(baseline_key, {}).get(wname)
                val = results.get(cfg, {}).get(wname)
                if base and val:
                    total += 1
                    pct = abs(val["e2e_mean_ms"] - base["e2e_mean_ms"]) / base["e2e_mean_ms"] * 100
                    if pct > 5:
                        sensitive += 1
            print(f"  {cfg}: {sensitive}/{total} workloads routing-sensitive (>5% change)")


if __name__ == "__main__":
    main()
