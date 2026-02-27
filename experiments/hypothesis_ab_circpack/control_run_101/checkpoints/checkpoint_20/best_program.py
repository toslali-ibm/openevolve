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
    centers = np.zeros((n, 2))

    # Place circles in a structured pattern
    # This is a simple pattern - evolution will improve this

    # Use a high-density hexagonal-like staggered arrangement (5-4-5-4-5-3)
    # This fits 26 circles more efficiently than a square grid.
    rows_layout = [5, 4, 5, 4, 5, 3]
    num_rows = len(rows_layout)
    
    # Approximate optimal radius for initial placement
    r_init = 1.0 / (2 + (num_rows - 1) * np.sqrt(3))
    dy = np.sqrt(3) * r_init
    dx = 2 * r_init
    
    idx = 0
    for r in range(num_rows):
        num_cols = rows_layout[r]
        # Center the row horizontally
        row_width = (num_cols - 1) * dx
        x_start = (1.0 - row_width) / 2.0
        for c in range(num_cols):
            if idx < n:
                centers[idx] = [x_start + c * dx, r_init + r * dy]
                idx += 1

    centers = np.clip(centers, r_init, 1.0 - r_init)

    # Remove clipping: `compute_max_radii` handles boundary conditions naturally.
    # If a center is placed too close to an edge, its radius will be limited correctly.

    # Compute maximum valid radii for this configuration
    radii = compute_max_radii(centers)

    # Calculate the sum of radii
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

    # Iteratively solve for radii to maximize the sum (equitable distribution)
    for _ in range(15):
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > dist:
                    # Equalize radii at the point of contact to maximize total sum
                    mid = dist / 2.0
                    radii[i] = min(radii[i], mid)
                    radii[j] = min(radii[j], mid)

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
