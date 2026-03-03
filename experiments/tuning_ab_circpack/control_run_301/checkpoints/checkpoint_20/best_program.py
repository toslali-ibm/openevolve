# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    rows = [5, 6, 5, 6, 4]
    # Search over spacing + alternating row offset + mild anisotropic scaling.
    # These extra degrees of freedom help exploit square edge-effects.
    best_sum, best_centers = -1.0, None
    for s in np.linspace(0.176, 0.206, 9):
        for off in (0.0, 0.35, 0.5, 0.65):
            for ay in (0.96, 1.00, 1.04):
                dy = s * np.sqrt(3) / 2 * ay
                y0 = 0.5 - dy * (len(rows) - 1) / 2
                centers = np.zeros((n, 2))
                k = 0
                for ri, m in enumerate(rows):
                    y = y0 + ri * dy
                    w = s * (m - 1)
                    x0 = 0.5 - w / 2 + (off * s if (ri & 1) else 0.0)
                    for j in range(m):
                        centers[k] = (x0 + j * s, y)
                        k += 1
                centers = np.clip(centers, 0.002, 0.998)
                sr = float(compute_max_radii(centers).sum())
                if sr > best_sum:
                    best_sum, best_centers = sr, centers.copy()

    # Deterministic coordinate-search with decreasing step + diagonal moves
    centers = best_centers
    steps = (0.010, 0.006, 0.003, 0.0015)
    dirs = np.array(
        [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)],
        float,
    ) / np.sqrt(2)

    for step in steps:
        improved = True
        while improved:
            improved = False
            radii = compute_max_radii(centers)
            base = float(radii.sum())
            order = np.argsort(radii)  # move the most constrained circles first
            for i in order:
                best_pos, best_val = centers[i].copy(), base
                old = centers[i].copy()
                for d in dirs:
                    centers[i] = np.clip(old + step * d, 0.001, 0.999)
                    val = float(compute_max_radii(centers).sum())
                    if val > best_val + 1e-12:
                        best_val, best_pos = val, centers[i].copy()
                centers[i] = best_pos
                if best_val > base + 1e-12:
                    base = best_val
                    improved = True

    radii = compute_max_radii(centers)
    return centers, radii, float(radii.sum())


def compute_max_radii(centers):
    n = centers.shape[0]
    diff = centers[:, None, :] - centers[None, :, :]
    dists = np.sqrt((diff * diff).sum(axis=2))
    np.fill_diagonal(dists, np.inf)
    wall = np.min(np.c_[centers[:, 0], centers[:, 1], 1 - centers[:, 0], 1 - centers[:, 1]], axis=1)

    # Gauss-Seidel tightening; vectorized min over neighbors each step.
    r = wall.copy()
    for _ in range(120):
        r0 = r.copy()
        for i in range(n):
            r[i] = max(1e-8, min(wall[i], np.min(dists[i] - r)))
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
