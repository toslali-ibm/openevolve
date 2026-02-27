#!/usr/bin/env python3
"""
Analyze 2x2 factorial experiment results and generate paper-ready plots.

Usage:
    python scripts/analyze_factorial_experiment.py \
        --data experiments/factorial_ab_funcmin/convergence.csv \
        --results experiments/factorial_ab_funcmin/run_results.json \
        --output experiments/factorial_ab_funcmin/plots

Produces:
    1. 2x2 interaction plot (evolution_mode x hypothesis effect)
    2. Convergence curves (4 conditions overlaid with IQR bands)
    3. Final score boxplot (4 conditions side-by-side)
    4. Diff failure rate bar chart
    5. Hypothesis compliance summary (treatment conditions only)
    6. statistics.json with all test results
"""
import argparse
import json
import itertools
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import mannwhitneyu, kruskal


# Condition metadata for consistent labeling
CONDITION_META = {
    "control_diff":    {"hypothesis": "off", "mode": "diff",    "label": "Control+Diff",    "color": "#FF5722", "marker": "o"},
    "treatment_diff":  {"hypothesis": "on",  "mode": "diff",    "label": "Treatment+Diff",  "color": "#E91E63", "marker": "s"},
    "control_full":    {"hypothesis": "off", "mode": "full",    "label": "Control+Full",    "color": "#2196F3", "marker": "^"},
    "treatment_full":  {"hypothesis": "on",  "mode": "full",    "label": "Treatment+Full",  "color": "#4CAF50", "marker": "D"},
}


def load_data(csv_path: str) -> pd.DataFrame:
    return pd.read_csv(csv_path)


def apply_locf(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Last-Observation-Carried-Forward so every run has a value at every checkpoint."""
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


def get_final_scores(df: pd.DataFrame) -> pd.DataFrame:
    """Get the final (max iteration) score for each condition+seed."""
    max_iter = df["iteration"].max()
    return df[df["iteration"] == max_iter].copy()


def rank_biserial(u_stat, n1, n2):
    """Compute rank-biserial correlation from Mann-Whitney U."""
    return 2 * u_stat / (n1 * n2) - 1


# ---------------------------------------------------------------------------
# Plot 1: 2x2 Interaction Plot
# ---------------------------------------------------------------------------
def plot_interaction(df: pd.DataFrame, output_dir: Path):
    """x=evolution_mode, y=median_score, lines=hypothesis (on/off)."""
    final = get_final_scores(df)

    fig, ax = plt.subplots(figsize=(7, 5))

    for hyp_val, style in [("off", {"color": "#FF5722", "ls": "--", "marker": "o", "label": "Hypothesis OFF"}),
                           ("on",  {"color": "#4CAF50", "ls": "-",  "marker": "s", "label": "Hypothesis ON"})]:
        medians, lowers, uppers, modes = [], [], [], []
        for mode in ["diff", "full"]:
            conds = [c for c, m in CONDITION_META.items() if m["hypothesis"] == hyp_val and m["mode"] == mode]
            scores = final[final["condition"].isin(conds)]["best_combined_score"]
            med = scores.median() if len(scores) > 0 else 0
            q25 = scores.quantile(0.25) if len(scores) > 0 else 0
            q75 = scores.quantile(0.75) if len(scores) > 0 else 0
            medians.append(med)
            lowers.append(med - q25)
            uppers.append(q75 - med)
            modes.append(mode)

        x = [0, 1]
        ax.errorbar(x, medians, yerr=[lowers, uppers], **style,
                     markersize=10, capsize=5, linewidth=2)

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Diff-based", "Full-rewrite"], fontsize=12)
    ax.set_ylabel("Median Final Score", fontsize=12)
    ax.set_title("2x2 Interaction: Hypothesis x Evolution Mode", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "interaction_plot.png", dpi=150)
    plt.close(fig)
    print("Saved interaction_plot.png")


# ---------------------------------------------------------------------------
# Plot 2: Convergence Curves
# ---------------------------------------------------------------------------
def plot_convergence_curves(df: pd.DataFrame, output_dir: Path):
    """4 conditions overlaid with IQR bands."""
    fig, ax = plt.subplots(figsize=(10, 6))

    for cond, meta in CONDITION_META.items():
        cond_data = df[df["condition"] == cond]
        if cond_data.empty:
            continue

        grouped = cond_data.groupby("iteration")["best_combined_score"]
        median = grouped.median()
        q25 = grouped.quantile(0.25)
        q75 = grouped.quantile(0.75)

        n_runs = cond_data["seed"].nunique()
        ax.plot(median.index, median.values, color=meta["color"], linewidth=2,
                label=f"{meta['label']} (n={n_runs})", marker=meta["marker"], markersize=4)
        ax.fill_between(median.index, q25.values, q75.values, color=meta["color"], alpha=0.15)

    ax.set_xlabel("Iteration", fontsize=12)
    ax.set_ylabel("Best Combined Score", fontsize=12)
    ax.set_title("Convergence Curves: 2x2 Factorial", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_dir / "convergence_curves.png", dpi=150)
    plt.close(fig)
    print("Saved convergence_curves.png")


# ---------------------------------------------------------------------------
# Plot 3: Final Score Boxplot
# ---------------------------------------------------------------------------
def plot_final_scores_boxplot(df: pd.DataFrame, output_dir: Path):
    """4 conditions side-by-side."""
    final = get_final_scores(df)

    fig, ax = plt.subplots(figsize=(8, 5))
    data = []
    labels = []
    colors = []
    for cond in ["control_diff", "treatment_diff", "control_full", "treatment_full"]:
        scores = final[final["condition"] == cond]["best_combined_score"].values
        data.append(scores)
        meta = CONDITION_META[cond]
        labels.append(f"{meta['label']}\n(n={len(scores)})")
        colors.append(meta["color"])

    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("Final Best Score", fontsize=12)
    ax.set_title("Final Score Distribution: 2x2 Factorial", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(output_dir / "final_scores_boxplot.png", dpi=150)
    plt.close(fig)
    print("Saved final_scores_boxplot.png")


# ---------------------------------------------------------------------------
# Plot 4: Diff Failure Rate Bar Chart
# ---------------------------------------------------------------------------
def plot_diff_failures(run_results: list, output_dir: Path):
    """Bar chart of diff/code parse failures per condition."""
    cond_failures = {}
    cond_counts = {}
    for r in run_results:
        if r["status"] != "ok":
            continue
        cond = r["condition"]
        cond_failures[cond] = cond_failures.get(cond, 0) + r.get("diff_failures", 0)
        cond_counts[cond] = cond_counts.get(cond, 0) + 1

    if not cond_failures:
        print("No diff failure data to plot")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    conds = ["control_diff", "treatment_diff", "control_full", "treatment_full"]
    conds = [c for c in conds if c in cond_failures]
    x = range(len(conds))
    # Average failures per run
    heights = [cond_failures[c] / max(cond_counts[c], 1) for c in conds]
    colors = [CONDITION_META[c]["color"] for c in conds]
    labels = [CONDITION_META[c]["label"] for c in conds]

    bars = ax.bar(x, heights, color=colors, alpha=0.7, edgecolor="black")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Avg Parse Failures per Run", fontsize=12)
    ax.set_title("Diff/Code Parse Failures by Condition", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")

    # Add value labels
    for bar, h in zip(bars, heights):
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.1, f"{h:.1f}",
                ha="center", va="bottom", fontsize=10)

    fig.tight_layout()
    fig.savefig(output_dir / "diff_failures.png", dpi=150)
    plt.close(fig)
    print("Saved diff_failures.png")


# ---------------------------------------------------------------------------
# Plot 5: Hypothesis Compliance Summary
# ---------------------------------------------------------------------------
def plot_hypothesis_compliance(run_results: list, output_dir: Path):
    """Grouped bar chart of hypothesis compliance for treatment conditions."""
    treatment_conds = ["treatment_diff", "treatment_full"]
    cond_data = {}

    for r in run_results:
        if r["status"] != "ok" or r["condition"] not in treatment_conds:
            continue
        cond = r["condition"]
        h = r.get("hypothesis", {})
        if cond not in cond_data:
            cond_data[cond] = {"compliance_rates": [], "confirmed": [], "refuted": []}
        total = h.get("total_evolved_programs", 0)
        with_hyp = h.get("programs_with_hypotheses", 0)
        rate = with_hyp / total if total > 0 else 0
        cond_data[cond]["compliance_rates"].append(rate)
        cond_data[cond]["confirmed"].append(h.get("confirmed", 0))
        cond_data[cond]["refuted"].append(h.get("refuted", 0))

    if not cond_data:
        print("No hypothesis compliance data to plot")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Panel 1: Compliance rate
    conds = [c for c in treatment_conds if c in cond_data]
    x = range(len(conds))
    means = [np.mean(cond_data[c]["compliance_rates"]) for c in conds]
    stds = [np.std(cond_data[c]["compliance_rates"]) for c in conds]
    colors = [CONDITION_META[c]["color"] for c in conds]
    labels = [CONDITION_META[c]["label"] for c in conds]

    ax1.bar(x, means, yerr=stds, color=colors, alpha=0.7, edgecolor="black", capsize=5)
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, fontsize=10)
    ax1.set_ylabel("Hypothesis Compliance Rate", fontsize=12)
    ax1.set_title("Programs with Valid Hypotheses", fontsize=13)
    ax1.set_ylim(0, 1.1)
    ax1.grid(True, alpha=0.3, axis="y")

    # Panel 2: Confirmed vs Refuted
    width = 0.35
    x_pos = np.arange(len(conds))
    confirmed_means = [np.mean(cond_data[c]["confirmed"]) for c in conds]
    refuted_means = [np.mean(cond_data[c]["refuted"]) for c in conds]

    ax2.bar(x_pos - width/2, confirmed_means, width, label="Confirmed", color="#4CAF50", alpha=0.7)
    ax2.bar(x_pos + width/2, refuted_means, width, label="Refuted", color="#F44336", alpha=0.7)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(labels, fontsize=10)
    ax2.set_ylabel("Avg Count per Run", fontsize=12)
    ax2.set_title("Hypothesis Verdicts", fontsize=13)
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(output_dir / "hypothesis_compliance.png", dpi=150)
    plt.close(fig)
    print("Saved hypothesis_compliance.png")


# ---------------------------------------------------------------------------
# Statistical Analysis
# ---------------------------------------------------------------------------
def compute_statistics(df: pd.DataFrame) -> dict:
    """Full factorial statistical analysis."""
    final = get_final_scores(df)
    max_iter = int(df["iteration"].max())

    stats = {"comparison_iteration": max_iter, "conditions": {}}

    # Per-condition descriptives
    all_conditions = ["control_diff", "treatment_diff", "control_full", "treatment_full"]
    condition_scores = {}
    for cond in all_conditions:
        scores = final[final["condition"] == cond]["best_combined_score"]
        condition_scores[cond] = scores.values
        stats["conditions"][cond] = {
            "n": len(scores),
            "median": float(scores.median()) if len(scores) > 0 else None,
            "mean": float(scores.mean()) if len(scores) > 0 else None,
            "std": float(scores.std()) if len(scores) > 0 else None,
            "iqr": float(scores.quantile(0.75) - scores.quantile(0.25)) if len(scores) > 0 else None,
        }

    # Omnibus: Kruskal-Wallis across all 4 conditions
    groups = [condition_scores[c] for c in all_conditions if len(condition_scores[c]) > 0]
    if len(groups) >= 2 and all(len(g) >= 1 for g in groups):
        try:
            h_stat, p_value = kruskal(*groups)
            stats["kruskal_wallis"] = {"H": float(h_stat), "p": float(p_value)}
        except ValueError:
            stats["kruskal_wallis"] = {"error": "insufficient data"}
    else:
        stats["kruskal_wallis"] = {"error": "insufficient groups"}

    # Pairwise Mann-Whitney U with Bonferroni correction
    pairs = list(itertools.combinations(all_conditions, 2))
    n_comparisons = len(pairs)
    pairwise = {}
    for c1, c2 in pairs:
        s1, s2 = condition_scores.get(c1, np.array([])), condition_scores.get(c2, np.array([]))
        key = f"{c1}_vs_{c2}"
        if len(s1) >= 2 and len(s2) >= 2:
            u_stat, p_raw = mannwhitneyu(s1, s2, alternative="two-sided")
            p_bonf = min(p_raw * n_comparisons, 1.0)
            r = rank_biserial(u_stat, len(s1), len(s2))
            pairwise[key] = {
                "U": float(u_stat),
                "p_raw": float(p_raw),
                "p_bonferroni": float(p_bonf),
                "rank_biserial_r": float(r),
                "n1": len(s1),
                "n2": len(s2),
            }
        else:
            pairwise[key] = {"error": "insufficient data"}
    stats["pairwise_mann_whitney"] = pairwise

    # Main effects
    # Hypothesis main effect: (treatment_diff + treatment_full) vs (control_diff + control_full)
    hyp_on = np.concatenate([condition_scores.get("treatment_diff", []), condition_scores.get("treatment_full", [])])
    hyp_off = np.concatenate([condition_scores.get("control_diff", []), condition_scores.get("control_full", [])])
    if len(hyp_on) >= 2 and len(hyp_off) >= 2:
        u, p = mannwhitneyu(hyp_on, hyp_off, alternative="two-sided")
        stats["main_effect_hypothesis"] = {
            "U": float(u), "p": float(p),
            "rank_biserial_r": float(rank_biserial(u, len(hyp_on), len(hyp_off))),
            "median_on": float(np.median(hyp_on)),
            "median_off": float(np.median(hyp_off)),
        }

    # Evolution mode main effect: (control_diff + treatment_diff) vs (control_full + treatment_full)
    mode_diff = np.concatenate([condition_scores.get("control_diff", []), condition_scores.get("treatment_diff", [])])
    mode_full = np.concatenate([condition_scores.get("control_full", []), condition_scores.get("treatment_full", [])])
    if len(mode_diff) >= 2 and len(mode_full) >= 2:
        u, p = mannwhitneyu(mode_diff, mode_full, alternative="two-sided")
        stats["main_effect_mode"] = {
            "U": float(u), "p": float(p),
            "rank_biserial_r": float(rank_biserial(u, len(mode_diff), len(mode_full))),
            "median_diff": float(np.median(mode_diff)),
            "median_full": float(np.median(mode_full)),
        }

    # Interaction: (D-C) vs (B-A)
    # D = treatment_full, C = control_full, B = treatment_diff, A = control_diff
    # We compare the hypothesis effect in full-rewrite mode vs diff mode
    d_scores = condition_scores.get("treatment_full", np.array([]))
    c_scores = condition_scores.get("control_full", np.array([]))
    b_scores = condition_scores.get("treatment_diff", np.array([]))
    a_scores = condition_scores.get("control_diff", np.array([]))

    if len(d_scores) > 0 and len(c_scores) > 0 and len(b_scores) > 0 and len(a_scores) > 0:
        # Compute differences: for each paired combo, treatment - control
        # Since runs aren't paired, use median differences as interaction estimate
        hyp_effect_full = float(np.median(d_scores) - np.median(c_scores))
        hyp_effect_diff = float(np.median(b_scores) - np.median(a_scores))
        stats["interaction"] = {
            "hypothesis_effect_full_mode": hyp_effect_full,
            "hypothesis_effect_diff_mode": hyp_effect_diff,
            "interaction_estimate": float(hyp_effect_full - hyp_effect_diff),
            "interpretation": (
                "Positive interaction: hypothesis helps MORE in full-rewrite mode"
                if hyp_effect_full > hyp_effect_diff
                else "Negative interaction: hypothesis helps MORE in diff mode"
            ),
        }

    return stats


def main():
    parser = argparse.ArgumentParser(description="Analyze 2x2 factorial experiment")
    parser.add_argument("--data", required=True, help="Path to convergence.csv")
    parser.add_argument("--results", default=None, help="Path to run_results.json")
    parser.add_argument("--output", required=True, help="Output directory for plots")
    parser.add_argument("--title", default="", help="Title suffix for plots")
    args = parser.parse_args()

    df = load_data(args.data)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded {len(df)} data points")
    print(f"Conditions: {df['condition'].unique()}")
    print(f"Seeds: {df['seed'].unique()}")
    print(f"Iterations: {sorted(df['iteration'].unique())}")

    # Apply LOCF
    df = apply_locf(df)
    print(f"After LOCF: {len(df)} data points")

    # Generate plots
    plot_convergence_curves(df, output_dir)
    plot_final_scores_boxplot(df, output_dir)
    plot_interaction(df, output_dir)

    # Load run results for diff-failure and hypothesis plots
    run_results = []
    if args.results and Path(args.results).exists():
        with open(args.results) as f:
            run_results = json.load(f)
        plot_diff_failures(run_results, output_dir)
        plot_hypothesis_compliance(run_results, output_dir)

    # Statistical analysis
    stats = compute_statistics(df)

    print("\n" + "=" * 70)
    print("STATISTICAL SUMMARY")
    print("=" * 70)

    print(f"\nComparison at iteration: {stats['comparison_iteration']}")

    print("\nPer-condition descriptives:")
    for cond, desc in stats.get("conditions", {}).items():
        label = CONDITION_META.get(cond, {}).get("label", cond)
        print(f"  {label}: median={desc.get('median', 'N/A')}, n={desc.get('n', 0)}")

    kw = stats.get("kruskal_wallis", {})
    if "H" in kw:
        print(f"\nKruskal-Wallis (omnibus): H={kw['H']:.3f}, p={kw['p']:.4f}")
    else:
        print(f"\nKruskal-Wallis: {kw.get('error', 'N/A')}")

    print("\nPairwise Mann-Whitney U (Bonferroni-corrected):")
    for key, vals in stats.get("pairwise_mann_whitney", {}).items():
        if "error" in vals:
            print(f"  {key}: {vals['error']}")
        else:
            sig = "*" if vals["p_bonferroni"] < 0.05 else ""
            print(f"  {key}: U={vals['U']:.1f}, p_bonf={vals['p_bonferroni']:.4f}{sig}, r={vals['rank_biserial_r']:.3f}")

    me_hyp = stats.get("main_effect_hypothesis", {})
    if "p" in me_hyp:
        print(f"\nMain effect — Hypothesis: U={me_hyp['U']:.1f}, p={me_hyp['p']:.4f}, "
              f"r={me_hyp['rank_biserial_r']:.3f} (on={me_hyp['median_on']:.4f}, off={me_hyp['median_off']:.4f})")

    me_mode = stats.get("main_effect_mode", {})
    if "p" in me_mode:
        print(f"Main effect — Mode: U={me_mode['U']:.1f}, p={me_mode['p']:.4f}, "
              f"r={me_mode['rank_biserial_r']:.3f} (diff={me_mode['median_diff']:.4f}, full={me_mode['median_full']:.4f})")

    interaction = stats.get("interaction", {})
    if interaction:
        print(f"\nInteraction:")
        print(f"  Hypothesis effect in full-rewrite: {interaction['hypothesis_effect_full_mode']:+.4f}")
        print(f"  Hypothesis effect in diff mode:    {interaction['hypothesis_effect_diff_mode']:+.4f}")
        print(f"  Interaction estimate:              {interaction['interaction_estimate']:+.4f}")
        print(f"  {interaction['interpretation']}")

    # Save statistics
    with open(output_dir / "statistics.json", "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\nSaved statistics.json to {output_dir}")


if __name__ == "__main__":
    main()
