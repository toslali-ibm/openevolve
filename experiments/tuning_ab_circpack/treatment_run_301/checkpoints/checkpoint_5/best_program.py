# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Use a well-optimized configuration based on known good packings
    # 26 circles ~ 5x5 grid + 1 extra, or hex arrangement
    # Try hex-offset grid: rows of 5 and 4 alternating
    # Row counts: 5, 4, 5, 4, 5, 3 = 26
    row_counts = [5, 4, 5, 4, 5, 3]
    n_rows = len(row_counts)
    
    spacing_y = 0.1654  # @TUNE [0.12, 0.20] @TUNED(was=0.155, gain=+0.06, best_impact=sum_radii:+0.1466)
    spacing_x = 0.1944  # @TUNE [0.13, 0.22] @TUNED(was=0.175, gain=+0.06, best_impact=sum_radii:+0.1466)
    
    centers = []
    total_h = spacing_y * (n_rows - 1)
    y_start = 0.5 - total_h / 2.0
    
    for row_idx, count in enumerate(row_counts):
        y = y_start + row_idx * spacing_y
        total_w = spacing_x * (count - 1)
        x_start = 0.5 - total_w / 2.0
        for col in range(count):
            x = x_start + col * spacing_x
            centers.append([x, y])
    
    centers = np.array(centers[:n])
    
    # Ensure all centers are inside the square with margin
    margin = 0.02
    centers = np.clip(centers, margin, 1.0 - margin)
    
    # Iterative radius computation - assign radii to maximize sum
    radii = compute_max_radii_iterative(centers)
    sum_radii = np.sum(radii)
    return centers, radii, sum_radii


def compute_max_radii_iterative(centers):
    n = centers.shape[0]
    dists = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(dists, np.inf)
    
    # Wall distances
    wall_dist = np.min(np.column_stack([
        centers[:, 0], centers[:, 1],
        1.0 - centers[:, 0], 1.0 - centers[:, 1]
    ]), axis=1)
    
    n_iters = 410  # @TUNE [50, 500] int @TUNED(was=200, gain=+0.06, best_impact=sum_radii:+0.1466)
    radii = np.minimum(wall_dist, np.min(dists, axis=1) / 2.0)
    
    for _ in range(n_iters):
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            radii[i] = max(max_r, 1e-10)
    
    # Final safety clamp
    radii = np.maximum(radii, 1e-10)
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
