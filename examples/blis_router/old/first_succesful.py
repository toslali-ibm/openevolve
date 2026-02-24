import matplotlib.pyplot as plt
import numpy as np

# Baseline (original)
baseline = {
    "combined_score": 4564.475420055555,
    "avg_e2e_ms": 3060.2600734444445,
    "avg_p95_ms": 6068.690766666667,
    # "cache_warmup_e2e_ms": 5734.5725258,
    # "load_spikes_e2e_ms": 3285.4380412,
    # "multiturn_e2e_ms": 160.7696533333333
}

# Optimized (new)
optimized = {
    "combined_score": 3872.3686077888888,
    "avg_e2e_ms": 2610.920415577778,
    "avg_p95_ms": 5133.8168,
    # "cache_warmup_e2e_ms": 4287.307672,
    # "load_spikes_e2e_ms": 3359.7881814,
    # "multiturn_e2e_ms": 185.66539333333333
}

metrics = list(baseline.keys())

baseline_vals = [baseline[m] for m in metrics]
optimized_vals = [optimized[m] for m in metrics]

# Compute percentage improvement
improvements = []
for m in metrics:

    imp = (baseline[m] - optimized[m]) / baseline[m] * 100
    improvements.append(imp)
    print(baseline[m], optimized[m], imp)

x = np.arange(len(metrics))
width = 0.35

plt.figure()

bars1 = plt.bar(x - width/2, baseline_vals, width, label="Baseline")
bars2 = plt.bar(x + width/2, optimized_vals, width, label="Optimized")

# Add percentage labels
for i, bar in enumerate(bars2):
    height = bar.get_height()
    plt.text(
        bar.get_x() + bar.get_width()/2,
        height,
        f"{improvements[i]:.1f}%",
        ha="center",
        va="bottom"
    )

plt.xticks(x, metrics, rotation=25)
plt.ylabel("Metric Value")
plt.title("Baseline vs Optimized Routing (All Metrics)")
plt.legend()
plt.tight_layout()
plt.show()