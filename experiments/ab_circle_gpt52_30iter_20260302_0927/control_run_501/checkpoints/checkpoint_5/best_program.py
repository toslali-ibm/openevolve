# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Use known good packing: hex grid rows of 5,5,5,5,5,1 = 26
    # For 26 equal circles, radius ~ 1/(2*5.5) but we optimize
    # Hex grid: rows alternate offset, spacing = 2r, row height = r*sqrt(3)
    # Try rows: 5,6,5,6,4 = 26 circles in hex arrangement
    rows = [5, 6, 5, 6, 4]
    # Estimate radius for uniform packing
    r_est = 0.092
    centers_list = []
    total_h = (len(rows) - 1) * r_est * np.sqrt(3) + 2 * r_est
    y_start = 0.5 - (len(rows) - 1) * r_est * np.sqrt(3) / 2
    for row_idx, nc in enumerate(rows):
        y = y_start + row_idx * r_est * np.sqrt(3)
        total_w = (nc - 1) * 2 * r_est + 2 * r_est
        x_start = 0.5 - (nc - 1) * r_est
        if row_idx % 2 == 1:
            x_start = 0.5 - (nc - 1) * r_est
        for j in range(nc):
            x = x_start + j * 2 * r_est
            centers_list.append([x, y])
    centers = np.array(centers_list[:n])
    # Now optimize with iterative improvement
    centers, radii = optimize_packing(centers, n)
    return centers, radii, np.sum(radii)


def compute_max_radii_lp(centers):
    """Iteratively compute good radii using greedy approach."""
    n = len(centers)
    # Distance to walls
    wall_dist = np.min(np.column_stack([
        centers[:, 0], centers[:, 1],
        1 - centers[:, 0], 1 - centers[:, 1]
    ]), axis=1)
    # Pairwise distances
    dists = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(i + 1, n):
            d = np.linalg.norm(centers[i] - centers[j])
            dists[i, j] = d
            dists[j, i] = d
    # Iteratively assign radii - start with wall constraints
    radii = wall_dist.copy()
    # Multiple passes to resolve overlaps
    for _ in range(50):
        changed = False
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            max_r = max(max_r, 0.0)
            if abs(radii[i] - max_r) > 1e-10:
                radii[i] = max_r
                changed = True
        if not changed:
            break
    return radii


def optimize_packing(centers, n):
    """Optimize circle positions and radii using local search."""
    best_centers = centers.copy()
    best_radii = compute_max_radii_lp(best_centers)
    best_sum = np.sum(best_radii)
    # Perturbation-based optimization
    for iteration in range(2000):
        trial = best_centers.copy()
        idx = iteration % n
        step = 0.02 * (1.0 - iteration / 2000)
        dx = np.random.uniform(-step, step)
        dy = np.random.uniform(-step, step)
        trial[idx, 0] = np.clip(trial[idx, 0] + dx, 0.001, 0.999)
        trial[idx, 1] = np.clip(trial[idx, 1] + dy, 0.001, 0.999)
        trial_radii = compute_max_radii_lp(trial)
        trial_sum = np.sum(trial_radii)
        if trial_sum > best_sum:
            best_centers = trial
            best_radii = trial_radii
            best_sum = trial_sum
    return best_centers, best_radii


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
def run_packing():
    """Run the circle packing constructor for n=26"""
    centers, radii, sum_radii = construct_packing()
    return centers, radii, sum_radii


def visualize(centers, radii):
    """
    Visualize the circle packing

    Args:
        centers: np.array of shape (n, 2) with (x, y) coordinates
        radii: np.array of shape (n) with radius of each circle
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    fig, ax = plt.subplots(figsize=(8, 8))

    # Draw unit square
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.grid(True)

    # Draw circles
    for i, (center, radius) in enumerate(zip(centers, radii)):
        circle = Circle(center, radius, alpha=0.5)
        ax.add_patch(circle)
        ax.text(center[0], center[1], str(i), ha="center", va="center")

    plt.title(f"Circle Packing (n={len(centers)}, sum={sum(radii):.6f})")
    plt.show()


if __name__ == "__main__":
    centers, radii, sum_radii = run_packing()
    print(f"Sum of radii: {sum_radii}")
    # AlphaEvolve improved this to 2.635

    # Uncomment to visualize:
    visualize(centers, radii)
