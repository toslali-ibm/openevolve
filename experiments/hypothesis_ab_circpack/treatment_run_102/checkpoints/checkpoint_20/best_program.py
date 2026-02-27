# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Replace the inefficient concentric ring pattern with a 5x5 grid and add a 26th circle at the center.
# MECHANISM-1: The original concentric ring pattern for 25 circles (with the 26th circle effectively at (0,0) and radius 0) is a very poor packing for N=26. A 5x5 grid of circles provides a much denser and more structured arrangement, yielding a base sum of 2.5 for equal radii. Adding the 26th circle at the square's absolute center (0.5, 0.5) leverages an often underutilized central void, allowing for a potentially larger overall sum as `compute_max_radii` will efficiently fill the space.
# EXPECT-1: sum_radii > 2.5
# HYPOTHESIS-2: Remove the `np.clip` operation on circle centers.
# MECHANISM-2: The `np.clip(centers, 0.01, 0.99)` operation in the original code incorrectly constrains circle centers, especially those intended to be near the boundaries (e.g., at 0.1). This artificial restriction forces their maximum possible radii to be smaller (e.g., 0.01 instead of 0.1), significantly reducing the overall sum of radii. The `compute_max_radii` function already correctly handles boundary constraints by calculating `min(x, y, 1-x, 1-y)`. Removing this redundant and detrimental clipping will allow circles to expand to their full potential near the edges, which is crucial for dense packings.
# EXPECT-2: sum_radii > 2.6
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

    # First, place a large circle in the center
    # Strategy: 5x5 grid for 25 circles, plus one central circle for N=26
    # For a 5x5 grid, circles would ideally have radius 1/10 = 0.1
    # Centers for these would be at (0.1, 0.1), (0.1, 0.3), ..., (0.9, 0.9)

    idx = 0
    # Place 25 circles in a 5x5 grid
    for i in range(5):
        for j in range(5):
            centers[idx, 0] = 0.1 + i * 0.2  # x-coordinate
            centers[idx, 1] = 0.1 + j * 0.2  # y-coordinate
            idx += 1

    # Place the 26th circle at a central interstitial position.
    # The previous code had centers[idx] = [0.5, 0.5], which was a duplicate of centers[12].
    centers[idx] = [0.2, 0.2]

    # Removed the problematic np.clip operation based on Hypothesis 2.
    # The compute_max_radii function already handles boundary constraints.

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
