# EVOLVE-BLOCK-START
# HYPOTHESIS-1: A 5x5 grid with one extra circle improves sum_radii over concentric rings.
# MECHANISM-1: Grid-based packing provides a more uniform distribution in square containers,
#   reducing the large gaps created by sparse circular rings.
# EXPECT-1: sum_radii > 1.2
# HYPOTHESIS-2: Iterative radius equalization improves the sum of radii.
# MECHANISM-2: The initial compute_max_radii scales both radii proportionally, but
#   iteratively redistributing slack allows smaller circles to grow into available gaps.
# EXPECT-2: target_ratio > 0.5
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    """
    Construct a 5x5 grid + 1 central circle arrangement for 26 circles.
    """
    n = 26
    # 5x5 grid covers 25 circles
    grid_points = np.linspace(0.1, 0.9, 5)
    gx, gy = np.meshgrid(grid_points, grid_points)
    centers = np.column_stack([gx.ravel(), gy.ravel()])
    
    # Place the 26th circle at a position that minimizes overlap
    # A slight offset from center works well for grid-based packing
    extra_circle = np.array([[0.5, 0.5]])
    centers = np.concatenate([centers, extra_circle], axis=0)

    # Compute maximum valid radii for this configuration
    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)

    return centers, radii, sum_radii


def compute_max_radii(centers):
    """
    Compute max radii using an iterative approach to better distribute space.
    """
    n = centers.shape[0]
    # Initialize radii to boundary constraints
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)

    # Iteratively resolve overlaps to maximize the sum of radii
    for _ in range(20):
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > d:
                    # Adjust radii proportionally to their current size
                    ratio = radii[i] / (radii[i] + radii[j])
                    radii[i] = d * ratio
                    radii[j] = d * (1 - ratio)
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
