# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Denser initial placement using a 5x5 grid plus one extra circle will significantly improve `sum_radii`.
# MECHANISM-1: The current concentric ring pattern for N=26 is inefficient, leaves large empty spaces, and contains a bug by only placing 25 circles instead of 26. A 5x5 grid provides a much more uniform and dense distribution, utilizing space more effectively, and fixing the circle count bug.
# EXPECT-1: sum_radii > 2.2
# HYPOTHESIS-2: Iterating the radius adjustment in `compute_max_radii` will improve the overall `sum_radii` and `validity`.
# MECHANISM-2: The `compute_max_radii` function currently performs only a single pass of overlap resolution. Overlaps can be cascaded, meaning reducing one pair's radii can cause or exacerbate overlaps with other circles. Multiple iterations allow the radii to converge to a more stable, non-overlapping state, maximizing the sum of radii given the center positions.
# EXPECT-2: combined_score > 0.8
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
    n = 26
    centers = np.zeros((n, 2))

    # Place circles in a 5x5 grid pattern for 25 circles
    # Using linspace(0.1, 0.9, 5) creates a grid where centers are 0.1, 0.3, 0.5, 0.7, 0.9
    # This ensures an initial distance from walls and even spacing.
    x_coords = np.linspace(0.1, 0.9, 5)
    y_coords = np.linspace(0.1, 0.9, 5)

    idx = 0
    for x in x_coords:
        for y in y_coords:
            if idx < 25: # Fill the first 25 slots with the grid
                centers[idx] = [x, y]
                idx += 1

    # Place the 26th circle. A common strategy for n=26 is a 5x5 grid with one additional circle
    # placed centrally in one of the 2x2 blocks (e.g., at 0.2, 0.2).
    if idx < n: # Ensure we don't exceed n
        centers[idx] = [0.2, 0.2] # Place the 26th circle in a gap
        idx += 1

    # The previous np.clip was overly restrictive and is not needed as compute_max_radii handles boundaries.

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
    # sum of radii at most d to avoid overlap.
    # This process needs to be iterative to resolve all overlaps.
    for _ in range(50): # Iterate multiple times for better convergence
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))

                # If current radii would cause overlap
                if radii[i] + radii[j] > dist:
                    # Scale both radii proportionally to resolve overlap
                    # Add a small epsilon to prevent division by zero if radii are tiny
                    if radii[i] + radii[j] > 1e-9:
                        scale = dist / (radii[i] + radii[j])
                        radii[i] *= scale
                        radii[j] *= scale
                    else: # If radii are already tiny, set to 0 to avoid issues
                        radii[i] = 0
                        radii[j] = 0
    
    # Ensure no radii become negative due to floating point inaccuracies or extreme overlaps
    return np.maximum(radii, 1e-7)


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
