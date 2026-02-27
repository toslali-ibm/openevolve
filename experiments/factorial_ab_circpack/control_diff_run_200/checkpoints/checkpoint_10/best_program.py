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

    # Hexagonal packing: ~5.1 columns and ~5.1 rows
    # We'll place circles in a dense arrangement and then relax them
    for i in range(n):
        row = i // 5
        col = i % 5
        x = 0.1 + col * 0.2 + (0.1 if row % 2 else 0)
        y = 0.1 + row * 0.1732
        centers[i] = [x, y]
    
    # Simple iterative relaxation to improve spacing
    for _ in range(50):
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                if dist < 0.19:
                    push = (0.19 - dist) * (diff / dist) * 0.5
                    centers[i] += push
                    centers[j] -= push
            centers[i] = np.clip(centers[i], 0.09, 0.91)

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

    # Limit by distance to other circles
    # Sort pairs by distance to handle tightest constraints first
    for _ in range(10): # Iterative refinement for radius balancing
        for i in range(n):
            for j in range(n):
                if i == j: continue
                dist = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > dist:
                    # Adjust radii to be exactly touching
                    avg = (radii[i] + radii[j])
                    radii[i] = (radii[i] / avg) * dist * 0.5 + radii[i] * 0.5
                    radii[j] = dist - radii[i]

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
