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

    # Use a more dense initial configuration (approx 5.1 x 5.1)
    # 26 circles: 5 rows of 5, plus one extra in a high-density spot
    for i in range(n):
        centers[i] = [0.1 + (i % 5) * 0.2 + (0.1 if (i // 5) % 2 else 0), 
                      0.1 + (i // 5) * 0.17]
    
    # Force-directed relaxation with decreasing 'temperature'
    for step in range(200):
        force = np.zeros_like(centers)
        for i in range(n):
            # Repulsion from other circles
            for j in range(n):
                if i == j: continue
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                if dist < 0.19:
                    force[i] += (diff / (dist + 1e-6)) * (0.19 - dist)
            
            # Boundary constraints as soft forces
            x, y = centers[i]
            if x < 0.09: force[i, 0] += (0.09 - x)
            if x > 0.91: force[i, 0] += (0.91 - x)
            if y < 0.09: force[i, 1] += (0.09 - y)
            if y > 0.91: force[i, 1] += (0.91 - y)
            
        centers += force * 0.2
        centers = np.clip(centers, 0.01, 0.99)

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

    # Greedy radius expansion: sort by available space or use iterative pressure
    # This approach is more effective than simple proportional shrinkage
    for _ in range(20):
        for i in range(n):
            max_r = min(centers[i, 0], centers[i, 1], 1 - centers[i, 0], 1 - centers[i, 1])
            for j in range(n):
                if i == j: continue
                d = np.linalg.norm(centers[i] - centers[j])
                max_r = min(max_r, d - radii[j])
            radii[i] = max(0, max_r)

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
