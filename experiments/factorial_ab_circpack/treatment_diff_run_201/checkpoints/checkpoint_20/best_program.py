# EVOLVE-BLOCK-START
# HYPOTHESIS-1: A 5x5 grid with one additional circle improves packing density.
# MECHANISM-1: Grid-based initialization provides uniform distribution, and for n=26,
#   a 5x5 base (25 circles) plus one central or edge-filler circle minimizes wasted space.
# EXPECT-1: sum_radii > 2.0
# HYPOTHESIS-2: Iterative relaxation of centers increases radii sum.
# MECHANISM-2: Moving centers away from their nearest neighbors iteratively
#   allows radii to expand, balancing local constraints more effectively than a static ring.
# EXPECT-2: target_ratio > 0.8
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Create a 5x5 grid (25 circles)
    side = 5
    x = np.linspace(0.1, 0.9, side)
    y = np.linspace(0.1, 0.9, side)
    xv, yv = np.meshgrid(x, y)
    centers = np.vstack([xv.ravel(), yv.ravel()]).T
    
    # Add the 26th circle in a 'gap' that is not already occupied by the 5x5 grid.
    # The 5x5 grid has centers at 0.1, 0.3, 0.5, 0.7, 0.9.
    # (0.5, 0.5) is already one of these, so adding it again caused a bug.
    # Placing it at (0.2, 0.2) fills a corner 'quadrant' formed by (0.1,0.1), (0.1,0.3), (0.3,0.1), (0.3,0.3).
    extra = np.array([[0.2, 0.2]])
    centers = np.vstack([centers, extra])

    # Iterative repulsion to maximize space between centers
    # Increased iterations and adjusted parameters for potentially better packing.
    for _ in range(200): # Increased number of iterations for better convergence
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                # Slightly decreased target distance to encourage tighter packing
                target = 0.18
                if dist < target:
                    # Apply a push proportional to the overlap, increased push strength slightly
                    push = (target - dist) * 0.5 * (diff / (dist + 1e-9))
                    centers[i] += push
                    centers[j] -= push
            # Clip centers to stay within bounds after repulsion.
            # Relaxed clipping to allow centers closer to the actual container boundaries (0 to 1).
            centers[i] = np.clip(centers[i], 0.05, 0.95)

    radii = compute_max_radii(centers)
    return centers, radii, np.sum(radii)

def compute_max_radii(centers):
    n = centers.shape[0]
    radii = np.zeros(n)
    for i in range(n):
        radii[i] = min(centers[i, 0], centers[i, 1], 1 - centers[i, 0], 1 - centers[i, 1])
    
    for _ in range(20):
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > dist:
                    # Proportionally shrink to fit
                    ratio = dist / (radii[i] + radii[j])
                    radii[i] *= ratio
                    radii[j] *= ratio
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
