# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Deterministic hex-like scaffold (good equal-radius baseline), then a small
    # coordinate descent on centers to increase feasible radii sum.
    row_counts = [4, 5, 4, 5, 4, 4]  # 26
    r0 = 0.0893  # baseline from best known equal-radius attempt
    dy = 2.0 * r0 * 0.8660254037844386  # sqrt(3)/2 * 2r
    y0 = r0

    centers = []
    for row_idx, nc in enumerate(row_counts):
        y = y0 + row_idx * dy
        dx = 2.0 * r0
        x0 = r0 + (0.5 * dx if (row_idx % 2 == 1) else 0.0)
        for col_idx in range(nc):
            centers.append([x0 + col_idx * dx, y])
    centers = np.clip(np.array(centers[:n], dtype=float), 1e-4, 1 - 1e-4)

    radii = compute_max_radii(centers)
    best_sum = float(np.sum(radii))
    best_centers = centers.copy()
    best_radii = radii.copy()

    # Small, deterministic local search: coordinate descent with decreasing step.
    step0 = 0.0599  # @TUNE [0.005, 0.06] @TUNED(was=0.03, gain=+0.03, best_impact=sum_radii:+0.0798)
    n_passes = 6  # @TUNE [1, 8] int @TUNED(was=4, gain=+0.03, best_impact=sum_radii:+0.0798)
    shrink = 0.4766  # @TUNE [0.35, 0.85] @TUNED(was=0.55, gain=+0.03, best_impact=sum_radii:+0.0798)
    for p in range(n_passes):
        step = step0 * (shrink ** p)
        for i in range(n):
            for ax in (0, 1):
                for sgn in (-1.0, 1.0):
                    trial = best_centers.copy()
                    trial[i, ax] = np.clip(trial[i, ax] + sgn * step, 1e-4, 1 - 1e-4)
                    tr = compute_max_radii(trial)
                    ts = float(np.sum(tr))
                    if ts > best_sum:
                        best_sum, best_centers, best_radii = ts, trial, tr

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

    # Final hard projection (guarantees validity)
    for _ in range(30):
        radii = np.minimum(radii, wall)
        changed = False
        for i in range(n):
            for j in range(i + 1, n):
                s = radii[i] + radii[j]
                if s > dists[i, j]:
                    # shrink the larger one first (empirically better for sum)
                    excess = s - dists[i, j]
                    if radii[i] >= radii[j]:
                        radii[i] = max(0.0, radii[i] - excess)
                    else:
                        radii[j] = max(0.0, radii[j] - excess)
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
