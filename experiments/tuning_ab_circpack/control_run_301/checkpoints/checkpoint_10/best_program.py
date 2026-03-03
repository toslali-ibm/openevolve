# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Deterministic hex-lattice start (better than per-row uniform grids),
    # then small local search. Determinism avoids unlucky RNG evaluations.
    rng = np.random.default_rng(0)

    row_counts = [5, 6, 5, 6, 4]
    r0 = 0.095
    s = 2 * r0 * 1.01
    h = s * np.sqrt(3) / 2
    y0 = 0.5 - h * (len(row_counts) - 1) / 2

    centers = np.zeros((n, 2))
    k = 0
    for ri, m in enumerate(row_counts):
        y = y0 + ri * h
        w = s * (m - 1)
        x0 = 0.5 - w / 2 + (0.5 * s if (ri & 1) else 0.0)
        for j in range(m):
            centers[k] = (x0 + j * s, y)
            k += 1

    centers = np.clip(centers, 0.02, 0.98)

    radii = compute_max_radii(centers)
    best_sum = float(radii.sum())
    best_centers = centers.copy()
    best_radii = radii.copy()

    # Coordinate search: cycle through circles, try a few deterministic jitters
    for it in range(260):
        i = it % n
        step = 0.015 * (1.0 - it / 260.0)
        for _ in range(3):
            trial = best_centers.copy()
            d = rng.uniform(-step, step, 2)
            trial[i] = np.clip(trial[i] + d, 0.001, 0.999)
            tr = compute_max_radii(trial)
            ssum = float(tr.sum())
            if ssum > best_sum:
                best_sum, best_centers, best_radii = ssum, trial, tr

    return best_centers, best_radii, best_sum


def compute_max_radii(centers):
    n = centers.shape[0]
    wall = np.min(np.c_[centers[:, 0], centers[:, 1], 1 - centers[:, 0], 1 - centers[:, 1]], axis=1)

    diff = centers[:, None, :] - centers[None, :, :]
    d = np.sqrt((diff * diff).sum(2))
    np.fill_diagonal(d, np.inf)

    # Max-sum feasible radii for fixed centers is a linear program; this
    # monotone "tightening" iteration is a good cheap proxy and usually
    # beats proportional pairwise shrinking.
    r = wall.copy()
    for _ in range(80):
        r0 = r.copy()
        for i in range(n):
            r[i] = max(1e-6, min(wall[i], np.min(d[i] - r)))
        if np.max(np.abs(r - r0)) < 1e-11:
            break
    return r


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
