#!/usr/bin/env python3
"""Plot bar comparison of best vs baseline metrics for a given experiment.

Usage:
    python examples/blis_router/scripts/plot_metrics_comparison.py <experiment_name>

Example:
    python examples/blis_router/scripts/plot_metrics_comparison.py openevolve_output_succss_dynwrkld_qwen

This reads:
    examples/blis_router/<experiment_name>/baseline_metrics.json
    examples/blis_router/<experiment_name>/best/best_program_info.json

And saves the resulting figure to:
    examples/blis_router/<experiment_name>/metrics_comparison.png
"""

import argparse
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

BLIS_ROUTER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def load_metrics(experiment_dir):
    baseline_path = os.path.join(experiment_dir, "baseline_metrics.json")
    best_path = os.path.join(experiment_dir, "best", "best_program_info.json")

    if not os.path.exists(baseline_path):
        sys.exit(f"Error: {baseline_path} not found")
    if not os.path.exists(best_path):
        sys.exit(f"Error: {best_path} not found")

    with open(baseline_path) as f:
        baseline = json.load(f)
    with open(best_path) as f:
        best_raw = json.load(f)

    best = best_raw.get("metrics", best_raw)
    return baseline, best


def compute_pct_diff(baseline_val, best_val):
    if baseline_val == 0:
        return 0.0
    return ((best_val - baseline_val) / abs(baseline_val)) * 100


def plot_comparison(baseline, best, experiment_name, output_path):
    skip = {"success_rate", "num_successful", "num_failed"}
    common = [k for k in baseline if k in best and k not in skip]

    if not common:
        sys.exit("Error: no common metrics found between baseline and best")

    # Negate combined_score so it becomes positive (originally negative)
    negate = {"combined_score"}

    # Order: primary metrics first, then the rest separated by a dashed line
    primary = ["combined_score", "avg_e2e_ms", "avg_p95_ms"]
    primary_keys = [k for k in primary if k in common]
    secondary_keys = [k for k in common if k not in primary]
    ordered = primary_keys + secondary_keys
    divider_pos = len(primary_keys) - 0.5  # x position for vertical dashed line

    n = len(ordered)
    x = np.arange(n)
    width = 0.35

    baseline_vals = [baseline[k] * (-1 if k in negate else 1) for k in ordered]
    best_vals = [best[k] * (-1 if k in negate else 1) for k in ordered]

    fig, ax = plt.subplots(figsize=(max(12, n * 2.4), 7))

    ax.bar(x - width / 2, baseline_vals, width, label="Baseline", color="#5B9BD5", edgecolor="white")
    ax.bar(x + width / 2, best_vals, width, label="Best (Evolved)", color="#ED7D31", edgecolor="white")

    # Vertical dashed line separating primary from secondary metrics
    if primary_keys and secondary_keys:
        ax.axvline(divider_pos, color="gray", linestyle="--", linewidth=1.2, alpha=0.7)

    # Add percentage diff annotations
    for i in range(n):
        pct = compute_pct_diff(baseline_vals[i], best_vals[i])
        top = max(baseline_vals[i], best_vals[i])
        offset = abs(top) * 0.03 + abs(baseline_vals[i] - best_vals[i]) * 0.05
        color = "green" if pct < 0 else ("red" if pct > 0 else "gray")
        sign = "+" if pct > 0 else ""
        ax.annotate(
            f"{sign}{pct:.1f}%",
            xy=(x[i], top + offset),
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color=color,
        )

    # Pretty labels (mark negated ones)
    labels = []
    for k in ordered:
        label = k.replace("_", " ").title()
        if k in negate:
            label = f"{label}"
        labels.append(label)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=12)
    ax.set_ylabel("Value (ms)", fontsize=14)
    ax.set_title(f"Baseline vs Best — {experiment_name}", fontsize=15, fontweight="bold")
    ax.legend(fontsize=13)
    ax.axhline(0, color="black", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    print(f"Saved figure to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Plot baseline vs best metrics comparison")
    parser.add_argument("experiment", help="Experiment directory name (e.g. openevolve_output_succss_dynwrkld_qwen)")
    args = parser.parse_args()

    experiment_dir = os.path.join(BLIS_ROUTER_DIR, args.experiment)
    if not os.path.isdir(experiment_dir):
        sys.exit(f"Error: directory {experiment_dir} does not exist")

    baseline, best = load_metrics(experiment_dir)
    output_path = os.path.join(experiment_dir, "metrics_comparison.png")
    plot_comparison(baseline, best, args.experiment, output_path)


if __name__ == "__main__":
    main()
