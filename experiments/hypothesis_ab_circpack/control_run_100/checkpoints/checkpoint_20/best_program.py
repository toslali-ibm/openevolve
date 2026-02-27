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

    # Place circles in a staggered 5x5+1 grid (hexagonal-ish)
    # 26 circles: 5 rows of 5, plus one extra
    idx = 0
    rows, cols = 5, 5
    dx = 1.0 / cols
    # Adjust dy for a more hexagonal aspect ratio
    dy_hex_ratio = np.sqrt(3) / 2
    dy = dx * dy_hex_ratio # Optimal dy for hexagonal packing if dx is fixed

    # Calculate vertical offset to center the grid
    total_grid_height = rows * dy
    y_offset = (1.0 - total_grid_height) / 2.0
    
    for r in range(rows):
        for c in range(cols):
            if idx < n:
                # Offset every other row to create hexagonal pattern
                shift = 0.5 * dx if r % 2 == 1 else 0.0
                x = (c + 0.5) * dx + shift
                y = y_offset + (r + 0.5) * dy # Apply vertical offset
                centers[idx] = [x, y]
                idx += 1
    
    # Place the 26th circle in a remaining gap
    # With the grid compressed vertically, this corner might have more space
    if idx < n:
        centers[idx] = [0.95, 0.95]

    centers = np.clip(centers, 0.05, 0.95)

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

    # Iterative relaxation to balance radii
    for _ in range(10):
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > dist:
                    # Equalize radii to maximize sum in dense areas
                    r_new = dist / 2.0
                    radii[i] = min(radii[i], r_new)
                    radii[j] = min(radii[j], r_new)

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
