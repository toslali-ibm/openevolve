# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    row_counts = [5, 5, 6, 5, 5]
    ny = len(row_counts)
    dy = 1.0 / ny
    centers = []
    for row, nc in enumerate(row_counts):
        y = dy * (row + 0.5)
        dx = 1.0 / nc
        for col in range(nc):
            centers.append([dx * (col + 0.5), y])
    centers = np.array(centers[:n])
    radii = compute_max_radii(centers)
    best_sum = np.sum(radii)
    best_centers = centers.copy()
    best_radii = radii.copy()
    for outer in range(10):
        step = 0.02 * (0.55 ** outer)
        for i in range(n):
            for dx, dy in [(step,0),(-step,0),(0,step),(0,-step),
                           (step,step),(-step,step),(step,-step),(-step,-step),
                           (step*.5,0),(-.5*step,0),(0,step*.5),(0,-step*.5)]:
                trial = best_centers.copy()
                trial[i] = np.clip(trial[i] + [dx, dy], 0.001, 0.999)
                tr = compute_max_radii(trial)
                ts = np.sum(tr)
                if ts > best_sum:
                    best_sum = ts
                    best_centers = trial
                    best_radii = tr
    return best_centers, best_radii, best_sum


def compute_max_radii(centers):
    n = centers.shape[0]
    dists = np.sqrt(((centers[:, None] - centers[None, :]) ** 2).sum(axis=2))
    wall_dist = np.min(np.column_stack([
        centers[:, 0], centers[:, 1],
        1 - centers[:, 0], 1 - centers[:, 1]]), axis=1)
    radii = wall_dist.copy()
    for _ in range(50):
        changed = False
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            max_r = max(max_r, 0.0)
            if max_r < radii[i] - 1e-12:
                radii[i] = max_r
                changed = True
        if not changed:
            break
    for _ in range(50):
        changed = False
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            max_r = max(max_r, 0.0)
            if max_r > radii[i] + 1e-12:
                radii[i] = max_r
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
