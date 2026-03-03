# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Use equal-radius approach: find radius r such that 26 circles of radius r
    # fit in hex grid pattern inside unit square
    # Layout: 6 rows with counts [4,5,4,5,4,4] = 26, hex offset on odd rows
    
    r = 0.0893  # @TUNE [0.07, 0.11] @TUNED(was=0.0925, gain=+0.14, best_impact=sum_radii:+0.3717)
    
    rows_config = [4, 5, 4, 5, 4, 4]  # 26 total
    num_rows = len(rows_config)
    
    # Vertical spacing between row centers
    dy = 2.0 * r * 0.866  # sqrt(3) * r for hex packing
    
    positions = []
    y_start = r  # start from top with margin r
    
    for row_idx, count in enumerate(rows_config):
        y = y_start + row_idx * dy
        # Horizontal spacing
        dx = 2.0 * r
        x_start = r + (0.5 * dx if (row_idx % 2 == 1) else 0.0)
        for col_idx in range(count):
            x = x_start + col_idx * dx
            positions.append([x, y])
    
    centers = np.array(positions[:n])
    
    # Compute safe radii: equal radius, limited by walls and neighbors
    # First check wall constraints
    wall_limit = np.min([centers[:, 0], centers[:, 1],
                         1.0 - centers[:, 0], 1.0 - centers[:, 1]], axis=0)
    
    # Check pairwise distances
    dists = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(dists, 1e10)
    min_half_dist = np.min(dists, axis=1) / 2.0
    
    # Each circle gets the minimum of wall distance and half min neighbor distance
    radii = np.minimum(wall_limit, min_half_dist)
    
    # Use uniform radius (min across all) for cleaner packing
    uniform_r = np.min(radii)
    radii = np.full(n, uniform_r)
    
    sum_radii = np.sum(radii)
    return centers, radii, sum_radii


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
