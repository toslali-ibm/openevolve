#!/usr/bin/env python3
"""
Analyze hypothesis A/B experiment results and generate plots.

Usage:
    python scripts/analyze_experiment.py --data experiments/hypothesis_ab_blis/convergence.csv --output experiments/hypothesis_ab_blis/plots/
"""
import argparse
import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy.stats import mannwhitneyu


def load_data(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def apply_locf(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Last-Observation-Carried-Forward so every run has a value at every checkpoint.

    For each (condition, seed), if a checkpoint iteration is missing, carry forward
    the last available score.  This prevents runs that ended early from being silently
    dropped from statistics and plots.
    """
    all_iterations = sorted(df["iteration"].unique())
    rows = []
    for (condition, seed), group in df.groupby(["condition", "seed"]):
        group = group.sort_values("iteration")
        last_score = None
        available = dict(zip(group["iteration"], group["best_combined_score"]))
        for it in all_iterations:
            if it in available:
                last_score = available[it]
            if last_score is not None:
                rows.append({
                    "condition": condition,
                    "seed": seed,
                    "iteration": it,
                    "best_combined_score": last_score,
                })
    return pd.DataFrame(rows)


LABEL_PRESETS = {
    "hypothesis": {
        "treatment": "Hypothesis-Driven",
        "control": "Vanilla OpenEvolve",
        "title": "Hypothesis-Driven vs Vanilla",
    },
    "tuning": {
        "treatment": "Tuning",
        "control": "Control",
        "title": "Tuning vs Control",
    },
}


def plot_convergence_curves(df: pd.DataFrame, output_dir: Path, title_suffix: str = "", labels: str = "hypothesis"):
    """Plot median convergence curves with IQR bands."""
    preset = LABEL_PRESETS[labels]
    fig, ax = plt.subplots(figsize=(8, 5))

    for condition, color in [("treatment", "#2196F3"), ("control", "#FF5722")]:
        cond_data = df[df["condition"] == condition]
        if cond_data.empty:
            print(f"WARNING: No data for condition '{condition}'")
            continue

        grouped = cond_data.groupby("iteration")["best_combined_score"]
        median = grouped.median()
        q25 = grouped.quantile(0.25)
        q75 = grouped.quantile(0.75)

        n_runs = cond_data["seed"].nunique()
        label = f"{preset[condition]} (n={n_runs})"
        ax.plot(median.index, median.values, color=color, linewidth=2, label=label, marker="o", markersize=4)
        ax.fill_between(median.index, q25.values, q75.values, color=color, alpha=0.2)

    ax.set_xlabel("Iteration", fontsize=12)
    ax.set_ylabel("Best Combined Score", fontsize=12)
    ax.set_title(f"Convergence: {preset['title']}{title_suffix}", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    output_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_dir / "convergence_curves.png", dpi=150)
    plt.close(fig)
    print(f"Saved convergence_curves.png")


def plot_final_scores_boxplot(df: pd.DataFrame, output_dir: Path, labels: str = "hypothesis"):
    """Box plot of final best scores at last iteration."""
    preset = LABEL_PRESETS[labels]
    # Use the max iteration that BOTH conditions have data for
    treatment_iters = set(df[df["condition"] == "treatment"]["iteration"].unique())
    control_iters = set(df[df["condition"] == "control"]["iteration"].unique())
    common_iters = treatment_iters & control_iters

    if not common_iters:
        print("WARNING: No common iterations between treatment and control — cannot create boxplot")
        return

    max_iter = max(common_iters)
    final = df[df["iteration"] == max_iter]

    treatment_scores = final[final["condition"] == "treatment"]["best_combined_score"].values
    control_scores = final[final["condition"] == "control"]["best_combined_score"].values

    if len(treatment_scores) == 0 or len(control_scores) == 0:
        print(f"WARNING: Empty data at iteration {max_iter} — treatment={len(treatment_scores)}, control={len(control_scores)}")
        return

    fig, ax = plt.subplots(figsize=(6, 5))
    data = [treatment_scores, control_scores]
    labels = [f"{preset['treatment']}\n(n={len(treatment_scores)})", f"{preset['control']}\n(n={len(control_scores)})"]

    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    bp["boxes"][0].set_facecolor("#2196F3")
    bp["boxes"][1].set_facecolor("#FF5722")

    ax.set_ylabel(f"Final Best Score (iteration {max_iter})", fontsize=12)
    ax.set_title("Final Score Distribution", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(output_dir / "final_scores_boxplot.png", dpi=150)
    plt.close(fig)
    print(f"Saved final_scores_boxplot.png")


def compute_statistics(df: pd.DataFrame) -> dict:
    """Compute Mann-Whitney U test and summary statistics.

    Uses the max iteration that both conditions share data for (after LOCF).
    """
    treatment_iters = set(df[df["condition"] == "treatment"]["iteration"].unique())
    control_iters = set(df[df["condition"] == "control"]["iteration"].unique())
    common_iters = treatment_iters & control_iters

    if not common_iters:
        return {"error": "no common iterations between treatment and control"}

    max_iter = max(common_iters)
    final = df[df["iteration"] == max_iter]

    treatment = final[final["condition"] == "treatment"]["best_combined_score"]
    control = final[final["condition"] == "control"]["best_combined_score"]

    stats = {
        "comparison_iteration": int(max_iter),
        "treatment_median": float(treatment.median()) if len(treatment) > 0 else None,
        "treatment_iqr": float(treatment.quantile(0.75) - treatment.quantile(0.25)) if len(treatment) > 0 else None,
        "control_median": float(control.median()) if len(control) > 0 else None,
        "control_iqr": float(control.quantile(0.75) - control.quantile(0.25)) if len(control) > 0 else None,
        "n_treatment": len(treatment),
        "n_control": len(control),
    }

    if len(treatment) >= 3 and len(control) >= 3:
        u_stat, p_value = mannwhitneyu(treatment, control, alternative="greater")
        stats["mann_whitney_u"] = float(u_stat)
        stats["p_value"] = float(p_value)
        # Rank-biserial correlation
        n1, n2 = len(treatment), len(control)
        stats["rank_biserial_r"] = 2 * u_stat / (n1 * n2) - 1

    return stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to convergence.csv")
    parser.add_argument("--output", required=True, help="Output directory for plots")
    parser.add_argument("--title", default="", help="Title suffix for plots")
    parser.add_argument(
        "--labels",
        choices=["hypothesis", "tuning"],
        default="hypothesis",
        help="Label style: 'hypothesis' (Hypothesis-Driven vs Vanilla) or 'tuning' (Tuning vs Control)",
    )
    args = parser.parse_args()

    df = load_data(args.data)
    output_dir = Path(args.output)

    print(f"Loaded {len(df)} data points")
    print(f"Conditions: {df['condition'].unique()}")
    print(f"Seeds: {df['seed'].unique()}")
    print(f"Iterations: {sorted(df['iteration'].unique())}")

    # Apply LOCF so runs that ended early still contribute to later checkpoints
    df = apply_locf(df)
    print(f"After LOCF: {len(df)} data points")

    plot_convergence_curves(df, output_dir, args.title, labels=args.labels)
    plot_final_scores_boxplot(df, output_dir, labels=args.labels)

    stats = compute_statistics(df)
    print("\n=== Statistical Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    with open(output_dir / "statistics.json", "w") as f:
        json.dump(stats, f, indent=2)


if __name__ == "__main__":
    main()
