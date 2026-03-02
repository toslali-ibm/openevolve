# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def make_hex_grid(row_counts, hex_offset=True):
    n = sum(row_counts)
    ny = len(row_counts)
    dy = 1.0 / ny
    centers = []
    for row, nc in enumerate(row_counts):
        y = dy * (row + 0.5)
        dx = 1.0 / nc
        off = 0.5 * dx if (hex_offset and row % 2 == 1) else 0.0
        for col in range(nc):
            x = dx * (col + 0.5) + off
            x = min(x, 1.0 - dx * 0.1)
            centers.append([x, y])
    return np.array(centers[:n])


def optimize_centers(centers, n, max_iters=12):
    radii = compute_max_radii_iterative(centers)
    best_sum = np.sum(radii)
    best_centers = centers.copy()
    best_radii = radii.copy()
    
    dirs = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1),
            (0.5,0),(-0.5,0),(0,0.5),(0,-0.5),(0.5,0.5),(-0.5,-0.5)]
    
    for outer in range(max_iters):
        step = 0.025 * (0.6 ** outer)
        improved = False
        for i in range(n):
            for dx, dy in dirs:
                trial = best_centers.copy()
                trial[i, 0] = np.clip(trial[i, 0] + step*dx, 0.001, 0.999)
                trial[i, 1] = np.clip(trial[i, 1] + step*dy, 0.001, 0.999)
                trial_radii = compute_max_radii_iterative(trial)
                trial_sum = np.sum(trial_radii)
                if trial_sum > best_sum:
                    best_sum = trial_sum
                    best_centers = trial.copy()
                    best_radii = trial_radii.copy()
                    improved = True
        if not improved and outer > 3:
            break
    return best_centers, best_radii, best_sum


def construct_packing():
    n = 26
    configs = [
        [5, 5, 6, 5, 5],
        [5, 6, 5, 5, 5],
        [5, 6, 5, 6, 4],
        [4, 6, 5, 6, 5],
        [6, 5, 5, 5, 5],
        [5, 5, 5, 5, 6],
        [4, 5, 6, 6, 5],
        [5, 5, 6, 6, 4],
        [6, 5, 6, 5, 4],
        [4, 5, 5, 6, 6],
    ]
    
    best_sum = 0
    best_centers = None
    best_radii = None
    
    for rc in configs:
        for hex_off in [True, False]:
            centers = make_hex_grid(rc, hex_off)
            c, r, s = optimize_centers(centers, n, max_iters=10)
            if s > best_sum:
                best_sum = s
                best_centers = c
                best_radii = r
    
    # Final polish on best solution with more iterations
    best_centers, best_radii, best_sum = optimize_centers(best_centers, n, max_iters=6)
    
    return best_centers, best_radii, best_sum


def compute_max_radii_iterative(centers):
    n = centers.shape[0]
    # Compute all pairwise distances
    dists = np.sqrt(((centers[:, None] - centers[None, :]) ** 2).sum(axis=2))
    # Wall distances
    wall_dist = np.min(np.column_stack([
        centers[:, 0], centers[:, 1],
        1 - centers[:, 0], 1 - centers[:, 1]
    ]), axis=1)
    
    # Initialize radii to wall distance
    radii = wall_dist.copy()
    
    # Iteratively shrink radii to resolve overlaps
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
    
    # Grow radii greedily to maximize sum
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
