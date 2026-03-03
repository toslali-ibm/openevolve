# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Use a known-good approach: place 26 equal circles in hex grid pattern
    # For 26 circles, try a 5-6 row hex arrangement
    # Row counts: 5, 6, 5, 6, 4 = 26 circles
    
    r_init = 0.0869  # @TUNE [0.070, 0.120] @TUNED(was=0.094, gain=+0.00, best_impact=eval_time:+0.2062)
    row_counts = [5, 6, 5, 6, 4]
    nrows = len(row_counts)
    
    # Hex grid spacing
    dy = 1.0 / nrows
    centers = []
    for row_idx, count in enumerate(row_counts):
        y = dy * (row_idx + 0.5)
        dx = 1.0 / count
        x_offset = 0.0 if count == max(row_counts) else dx * 0.5
        for col_idx in range(count):
            x = x_offset + dx * (col_idx + 0.5)
            centers.append([x, y])
    
    centers = np.array(centers[:n])
    
    # Iterative radii assignment - assign radii fairly
    radii = np.full(n, r_init)
    
    # Iteratively grow radii
    n_iters = 491  # @TUNE [50, 500] int @TUNED(was=200, gain=+0.00, best_impact=eval_time:+0.2062)
    for iteration in range(n_iters):
        # Compute max allowed radius for each circle
        max_r = np.full(n, 1.0)
        for i in range(n):
            x, y = centers[i]
            max_r[i] = min(x, y, 1.0 - x, 1.0 - y)
        
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))
                # Each circle can take at most dist - r_other
                allowed_i = dist - radii[j]
                allowed_j = dist - radii[i]
                if allowed_i < max_r[i]:
                    max_r[i] = allowed_i
                if allowed_j < max_r[j]:
                    max_r[j] = allowed_j
        
        max_r = np.maximum(max_r, 0.001)
        growth = 0.6158  # @TUNE [0.5, 0.99] @TUNED(was=0.85, gain=+0.00, best_impact=eval_time:+0.2062)
        radii = radii * (1 - growth) + max_r * growth
        radii = np.minimum(radii, max_r)
    
    # Final safety: ensure validity
    for _ in range(50):
        valid = True
        for i in range(n):
            x, y = centers[i]
            wall_max = min(x, y, 1.0 - x, 1.0 - y)
            if radii[i] > wall_max:
                radii[i] = wall_max
                valid = False
            for j in range(i + 1, n):
                dist = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))
                if radii[i] + radii[j] > dist:
                    scale = dist / (radii[i] + radii[j]) * 0.9999
                    radii[i] *= scale
                    radii[j] *= scale
                    valid = False
        if valid:
            break
    
    sum_radii = np.sum(radii)
    return centers, radii, sum_radii


def compute_max_radii(centers):
    """
    Compute the maximum possible radii for each circle position
    such that they don't overlap and stay within the unit square.

    Args:
        centers: np.array of shape (n, 2) with (x, y) coordinates

    Returns:
        np.array of shape (n) with radius of each circle
    """
    n = centers.shape[0]
    radii = np.ones(n)

    # First, limit by distance to square borders
    for i in range(n):
        x, y = centers[i]
        # Distance to borders
        radii[i] = min(x, y, 1 - x, 1 - y)

    # Then, limit by distance to other circles
    # Each pair of circles with centers at distance d can have
    # sum of radii at most d to avoid overlap
    for i in range(n):
        for j in range(i + 1, n):
            dist = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))

            # If current radii would cause overlap
            if radii[i] + radii[j] > dist:
                # Scale both radii proportionally
                scale = dist / (radii[i] + radii[j])
                radii[i] *= scale
                radii[j] *= scale

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
