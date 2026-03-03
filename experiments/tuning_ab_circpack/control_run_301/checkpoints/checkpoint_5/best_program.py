# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    """
    Construct a specific arrangement of 26 circles in a unit square
    that attempts to maximize the sum of their radii.

    Returns:
        Tuple of (centers, radii, sum_of_radii)
        centers: np.array of shape (26, 2) with (x, y) coordinates
        radii: np.array of shape (26) with radius of each circle
        sum_of_radii: Sum of all radii
    """
    # Initialize arrays for 26 circles
    n = 26
    
    # Use hexagonal-style packing: rows of 5 and 6 alternating
    # Row heights for hex packing with spacing s: rows at 0, s*sqrt(3)/2, s*sqrt(3), ...
    # For 26 circles: rows of 5,6,5,5,5 = 26 or 5,5,6,5,5 = 26
    # Try 6 rows: 4,5,4,5,4,4 = 26 or 5,5,4,4,4,4=26
    # Best: rows of 5,5,5,5,3,3 or hexagonal offset rows
    
    # Use a well-tuned hexagonal arrangement
    # 5 rows: 5,6,5,6,4 = 26
    r_approx = 0.093  # approximate radius for spacing
    s = 2 * r_approx * 1.02  # slight gap
    
    row_configs = [5, 6, 5, 6, 4]  # 26 total
    hex_h = s * np.sqrt(3) / 2
    
    total_height = hex_h * (len(row_configs) - 1)
    y_start = 0.5 - total_height / 2
    
    idx = 0
    centers = np.zeros((n, 2))
    for row_idx, num_in_row in enumerate(row_configs):
        y = y_start + row_idx * hex_h
        row_width = s * (num_in_row - 1)
        x_start = 0.5 - row_width / 2
        for col in range(num_in_row):
            x = x_start + col * s
            centers[idx] = [x, y]
            idx += 1
    
    # Ensure all centers allow some radius inside the square
    min_margin = 0.02
    centers = np.clip(centers, min_margin, 1.0 - min_margin)

    # Compute maximum valid radii for this configuration
    radii = compute_max_radii(centers)

    # Calculate the sum of radii
    sum_radii = np.sum(radii)

    return centers, radii, sum_radii


def compute_max_radii(centers):
    """
    Compute maximum radii iteratively for better optimization.
    """
    n = centers.shape[0]
    
    # Precompute pairwise distances
    dists = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))
            dists[i, j] = d
            dists[j, i] = d
    
    # Wall distances
    wall_dist = np.zeros(n)
    for i in range(n):
        x, y = centers[i]
        wall_dist[i] = min(x, y, 1 - x, 1 - y)
    
    # Iterative approach: repeatedly compute max radius for each circle
    radii = wall_dist.copy()
    
    for iteration in range(50):
        changed = False
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            max_r = max(max_r, 1e-6)
            if abs(max_r - radii[i]) > 1e-10:
                radii[i] = max_r
                changed = True
        if not changed:
            break
    
    # Ensure all positive
    radii = np.maximum(radii, 1e-6)
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
