# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Try multiple hex grid layouts, pick the best, then optimize.
    # Layout candidates: different row patterns that sum to 26
    layouts = [
        [4, 5, 4, 5, 4, 4],
        [5, 4, 5, 4, 4, 4],
        [4, 5, 5, 4, 4, 4],
        [5, 5, 4, 4, 4, 4],
        [4, 4, 5, 4, 5, 4],
        [5, 4, 4, 5, 4, 4],
        [4, 5, 4, 4, 5, 4],
        [3, 4, 5, 4, 5, 5],
    ]

    best_sum = -1.0
    best_centers = None
    best_radii = None

    for row_counts in layouts:
        nrows = len(row_counts)
        # Space rows evenly across the square
        dy = 1.0 / (nrows + 1)
        centers = []
        for row_idx, nc in enumerate(row_counts):
            y = dy * (row_idx + 1)
            dx = 1.0 / (nc + 1)
            x_off = dx * 0.5 if (row_idx % 2 == 1) else 0.0
            for col_idx in range(nc):
                x = dx * (col_idx + 1) + x_off
                centers.append([np.clip(x, 0.01, 0.99), np.clip(y, 0.01, 0.99)])
        centers = np.array(centers[:n], dtype=float)
        radii = compute_max_radii(centers)
        s = float(np.sum(radii))
        if s > best_sum:
            best_sum, best_centers, best_radii = s, centers.copy(), radii.copy()

    # Multi-pass coordinate descent with diagonal moves too
    step0 = 0.111  # @TUNE [0.02, 0.12] @TUNED(was=0.06, gain=+0.02, best_impact=eval_time:+0.1942)
    n_passes = 12  # @TUNE [4, 12] int @TUNED(was=8, gain=+0.02, best_impact=eval_time:+0.1942)
    shrink = 0.6046  # @TUNE [0.4, 0.75] @TUNED(was=0.55, gain=+0.02, best_impact=eval_time:+0.1942)
    for p in range(n_passes):
        step = step0 * (shrink ** p)
        improved = True
        while improved:
            improved = False
            for i in range(n):
                for dxy in [(step,0),(-step,0),(0,step),(0,-step),
                            (step,step),(-step,step),(step,-step),(-step,-step)]:
                    trial = best_centers.copy()
                    trial[i, 0] = np.clip(trial[i, 0] + dxy[0], 1e-4, 1 - 1e-4)
                    trial[i, 1] = np.clip(trial[i, 1] + dxy[1], 1e-4, 1 - 1e-4)
                    tr = compute_max_radii(trial)
                    ts = float(np.sum(tr))
                    if ts > best_sum + 1e-10:
                        best_sum, best_centers, best_radii = ts, trial, tr
                        improved = True

    return best_centers, best_radii, best_sum


def compute_max_radii(centers):
    n = centers.shape[0]
    # Vectorized pairwise distances
    diff = centers[:, None, :] - centers[None, :, :]
    dists = np.sqrt((diff * diff).sum(axis=2))
    np.fill_diagonal(dists, np.inf)

    # Wall caps
    wall = np.minimum.reduce([centers[:, 0], centers[:, 1], 1 - centers[:, 0], 1 - centers[:, 1]])
    radii = wall.copy()

    # Enforce r_i + r_j <= d_ij by shrinking only what's necessary.
    for _ in range(80):
        # For each i, the tightest constraint is r_i <= min_j (d_ij - r_j)
        bound_from_neighbors = np.min(dists - radii[None, :], axis=1)
        new_r = np.minimum(wall, bound_from_neighbors)
        new_r = np.maximum(new_r, 0.0)
        # Damped update improves stability vs. oscillation
        radii2 = 0.6 * radii + 0.4 * new_r
        if np.max(np.abs(radii2 - radii)) < 1e-12:
            radii = radii2
            break
        radii = radii2

    # Final hard projection (guarantees validity) - proportional shrinking
    for _ in range(50):
        radii = np.minimum(radii, wall)
        changed = False
        for i in range(n):
            for j in range(i + 1, n):
                s = radii[i] + radii[j]
                if s > dists[i, j]:
                    scale = dists[i, j] / s * 0.999999
                    radii[i] *= scale
                    radii[j] *= scale
                    changed = True
        if not changed:
            break
    return radii


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
