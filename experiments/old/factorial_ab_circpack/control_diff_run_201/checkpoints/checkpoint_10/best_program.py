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

    # Create a 5x5 grid and place the 26th circle in the center
    grid_size = 5
    coords = np.linspace(0.1, 0.9, grid_size)
    idx = 0
    for x in coords:
        for y in coords:
            if idx < n:
                centers[idx] = [x, y]
                idx += 1
    if idx < n:
        centers[idx] = [0.5, 0.5]

    # Force-directed relaxation to optimize spacing
    for _ in range(100):
        forces = np.zeros((n, 2))
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                if dist < 0.19: # Target diameter for n=26
                    forces[i] += (diff / (dist + 1e-6)) * (0.19 - dist)
                    forces[j] -= (diff / (dist + 1e-6)) * (0.19 - dist)
        centers += forces * 0.1
        centers = np.clip(centers, 0.04, 0.96)

    # Compute maximum valid radii for this configuration
    radii = compute_max_radii(centers)

    # Calculate the sum of radii
    sum_radii = np.sum(radii)

    return centers, radii, sum_radii


def compute_max_radii(centers):
    """
    Compute radii by ensuring no overlaps and staying within bounds.
    """
    n = centers.shape[0]
    # Initialize with distance to boundaries
    radii = np.min(np.hstack([centers, 1 - centers]), axis=1)
    
    # Adjust for inter-circle distances
    for i in range(n):
        for j in range(i + 1, n):
            dist = np.linalg.norm(centers[i] - centers[j])
            if radii[i] + radii[j] > dist:
                # Share the available space proportional to current constraints
                share = radii[i] / (radii[i] + radii[j])
                radii[i] = dist * share
                radii[j] = dist * (1 - share)
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
