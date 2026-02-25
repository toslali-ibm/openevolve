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


def plot_convergence_curves(df: pd.DataFrame, output_dir: Path, title_suffix: str = ""):
    """Plot median convergence curves with IQR bands."""
    fig, ax = plt.subplots(figsize=(8, 5))

    for condition, color in [("treatment", "#2196F3"), ("control", "#FF5722")]:
        cond_data = df[df["condition"] == condition]
        if cond_data.empty:
            continue

        grouped = cond_data.groupby("iteration")["best_combined_score"]
        median = grouped.median()
        q25 = grouped.quantile(0.25)
        q75 = grouped.quantile(0.75)

        label = "Hypothesis-Driven" if condition == "treatment" else "Vanilla OpenEvolve"
        ax.plot(median.index, median.values, color=color, linewidth=2, label=label)
        ax.fill_between(median.index, q25.values, q75.values, color=color, alpha=0.2)

    ax.set_xlabel("Iteration", fontsize=12)
    ax.set_ylabel("Best Combined Score", fontsize=12)
    ax.set_title(f"Convergence: Hypothesis-Driven vs Vanilla{title_suffix}", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    output_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_dir / "convergence_curves.png", dpi=150)
    plt.close(fig)
    print(f"Saved convergence_curves.png")


def plot_final_scores_boxplot(df: pd.DataFrame, output_dir: Path):
    """Box plot of final best scores at last iteration."""
    max_iter = df["iteration"].max()
    final = df[df["iteration"] == max_iter]

    fig, ax = plt.subplots(figsize=(6, 5))
    data = [
        final[final["condition"] == "treatment"]["best_combined_score"].values,
        final[final["condition"] == "control"]["best_combined_score"].values,
    ]
    labels = ["Hypothesis-Driven", "Vanilla"]

    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    bp["boxes"][0].set_facecolor("#2196F3")
    bp["boxes"][1].set_facecolor("#FF5722")

    ax.set_ylabel("Final Best Score (iteration {})".format(max_iter), fontsize=12)
    ax.set_title("Final Score Distribution", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(output_dir / "final_scores_boxplot.png", dpi=150)
    plt.close(fig)
    print(f"Saved final_scores_boxplot.png")


def compute_statistics(df: pd.DataFrame) -> dict:
    """Compute Mann-Whitney U test and summary statistics."""
    max_iter = df["iteration"].max()
    final = df[df["iteration"] == max_iter]

    treatment = final[final["condition"] == "treatment"]["best_combined_score"]
    control = final[final["condition"] == "control"]["best_combined_score"]

    stats = {
        "treatment_median": float(treatment.median()),
        "treatment_iqr": float(treatment.quantile(0.75) - treatment.quantile(0.25)),
        "control_median": float(control.median()),
        "control_iqr": float(control.quantile(0.75) - control.quantile(0.25)),
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
    args = parser.parse_args()

    df = load_data(args.data)
    output_dir = Path(args.output)

    print(f"Loaded {len(df)} data points")
    print(f"Conditions: {df['condition'].unique()}")
    print(f"Seeds: {df['seed'].unique()}")
    print(f"Iterations: {sorted(df['iteration'].unique())}")

    plot_convergence_curves(df, output_dir, args.title)
    plot_final_scores_boxplot(df, output_dir)

    stats = compute_statistics(df)
    print("\n=== Statistical Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    with open(output_dir / "statistics.json", "w") as f:
        json.dump(stats, f, indent=2)


if __name__ == "__main__":
    main()
