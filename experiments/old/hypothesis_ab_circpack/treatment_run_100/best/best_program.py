# EVOLVE-BLOCK-START
# HYPOTHESIS-1: A 5x5 grid with one extra circle is more efficient than concentric rings.
# MECHANISM-1: A regular grid minimizes empty space between circles in a square container,
#   providing a higher baseline sum_radii than arbitrary rings.
# EXPECT-1: sum_radii > 1.8
# HYPOTHESIS-2: Jittered grid placement allows for better local optimization.
# MECHANISM-2: Slight offsets from a perfect grid allow circles to "nestle" closer,
#   reducing the impact of the rigid square boundaries.
# EXPECT-2: target_ratio > 0.7
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # 5x5 Grid with offsets to mimic hexagonal packing
    centers = np.zeros((n, 2))
    idx = 0
    for r in range(5):
        for c in range(5):
            x = 0.1 + c * 0.2
            y = 0.1 + r * 0.2
            if r % 2 == 1: # Shift odd rows
                x += 0.08
            centers[idx] = [x, y]
            idx += 1
    centers[25] = [0.9, 0.5] # 26th circle on the edge
    
    centers = np.clip(centers, 0.02, 0.98)
    radii = compute_max_radii(centers)
    return centers, radii, np.sum(radii)

def compute_max_radii(centers):
    n = centers.shape[0]
    # Distances to 4 boundaries
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    # Pairwise distances
    for i in range(n):
        for j in range(i + 1, n):
            d = np.linalg.norm(centers[i] - centers[j])
            if radii[i] + radii[j] > d:
                # Equalize radii to resolve conflict
                r_new = d / 2.0
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
