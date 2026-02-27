# EVOLVE-BLOCK-START
# HYPOTHESIS-1: A 5x5 grid with one extra circle improves sum_radii over concentric rings.
# MECHANISM-1: Grid-based initialization provides a more uniform distribution,
#   reducing the extreme overlap of the outer ring which was clipped at 0.7 radius.
# EXPECT-1: sum_radii > 2.0
# HYPOTHESIS-2: Iterative relaxation of radii increases total sum.
# MECHANISM-2: The current compute_max_radii scales both circles equally;
#   a greedy approach can better fill gaps by prioritizing smaller constraints.
# EXPECT-2: target_ratio > 0.8
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    """Constructs 26 circles using a jittered grid strategy."""
    n = 26
    # 5x5 grid covers 25 circles
    side = 5
    coords = np.linspace(0.12, 0.88, side)
    xv, yv = np.meshgrid(coords, coords)
    
    centers = np.zeros((n, 2))
    centers[:25, 0] = xv.flatten()
    centers[:25, 1] = yv.flatten()
    
    # 26th circle at a location that displaces the least sum
    centers[25] = [0.5, 0.5]
    
    # Apply a structured jitter to move circles towards a hexagonal-like shift
    for i in range(25):
        row = i // 5
        if row % 2 == 0:
            centers[i, 0] += 0.04
            
    centers = np.clip(centers, 0.02, 0.98)
    radii = compute_max_radii(centers)
    return centers, radii, np.sum(radii)


def compute_max_radii(centers):
    """Compute radii using iterative constraint relaxation."""
    n = centers.shape[0]
    # Start with max possible radius (distance to nearest wall)
    radii = np.array([min(c[0], c[1], 1-c[0], 1-c[1]) for c in centers])
    
    # Iteratively resolve overlaps. 20 iterations to converge.
    for _ in range(20):
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > d:
                    # Contract both circles to touch exactly
                    shrinkage = d / (radii[i] + radii[j])
                    radii[i] *= shrinkage
                    radii[j] *= shrinkage
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
