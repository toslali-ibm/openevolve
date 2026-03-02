# EVOLVE-BLOCK-START
# HYPOTHESIS-1: A 5x5 grid with one extra circle is more efficient than concentric rings.
# MECHANISM-1: Grid-based layouts distribute circles more uniformly in a square container,
#   reducing the extreme overlaps found in polar coordinates when applied to a square.
# EXPECT-1: sum_radii > 2.1
# HYPOTHESIS-2: Iterative radius relaxation improves the sum over proportional scaling.
# MECHANISM-2: Proportional scaling is a one-pass greedy approach; iterative relaxation
#   allows circles with more "room" to expand, filling gaps left by constrained neighbors.
# EXPECT-2: combined_score > 0.8
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Create 5x5 grid
    coords = np.linspace(0.1, 0.9, 5)
    xv, yv = np.meshgrid(coords, coords)
    centers = np.vstack([xv.ravel(), yv.ravel()]).T
    
    # Add 26th circle and apply jitter to allow space for growth
    centers = np.vstack([centers, [0.5, 0.5]])
    centers[:25:2, 0] += 0.015 
    
    centers = np.clip(centers, 0.01, 0.99)
    radii = compute_max_radii(centers)
    return centers, radii, np.sum(radii)

def compute_max_radii(centers):
    n = centers.shape[0]
    radii = np.zeros(n) + 0.01
    # Iterative relaxation to maximize radii sum
    for _ in range(80):
        for i in range(n):
            # Bound by square edges
            r_i = min(centers[i,0], centers[i,1], 1-centers[i,0], 1-centers[i,1])
            # Bound by neighbor circles
            for j in range(n):
                if i == j: continue
                dist = np.linalg.norm(centers[i] - centers[j])
                r_i = min(r_i, dist - radii[j])
            radii[i] = max(0, r_i)
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
