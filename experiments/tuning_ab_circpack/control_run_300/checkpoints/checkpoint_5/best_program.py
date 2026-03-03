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
    n = 26
    # Use hex grid: rows of [5, 5, 5, 5, 3, 3] or similar
    # Try multiple layouts and pick the best
    best_sum = 0
    best_centers = None
    best_radii = None

    # Layout 1: Hex grid with rows [5,5,5,5,3,3]
    for layout in range(4):
        centers = []
        if layout == 0:
            # 5x5 grid + 1 extra
            r_approx = 1.0 / 10.2
            for row in range(5):
                for col in range(5):
                    x = (col + 0.5) / 5.0
                    y = (row + 0.5) / 5.0
                    centers.append([x, y])
            centers.append([0.5, 0.5 / 5.0 + 5.0 * (0.5 / 5.0)])  # extra
            # Replace last with better position
            centers[25] = [0.5, 0.95]
        elif layout == 1:
            # Hex grid: rows of 5,6,5,6,4
            row_counts = [5, 6, 5, 6, 4]
            ny = len(row_counts)
            dy = 1.0 / (ny + 0.5)
            idx = 0
            for r, cnt in enumerate(row_counts):
                y = dy * (r + 0.75)
                dx = 1.0 / (cnt + 0.5)
                for c in range(cnt):
                    x = dx * (c + 0.75)
                    centers.append([x, y])
                    idx += 1
                    if idx >= n:
                        break
                if idx >= n:
                    break
        elif layout == 2:
            # Hex grid: 5,5,6,5,5
            row_counts = [5, 5, 6, 5, 5]
            ny = len(row_counts)
            dy = 1.0 / (ny + 0.5)
            idx = 0
            for r, cnt in enumerate(row_counts):
                y = dy * (r + 0.75)
                dx = 1.0 / (cnt + 0.5)
                off = 0.0 if cnt == 6 else dx * 0.0
                for c in range(cnt):
                    x = dx * (c + 0.75)
                    centers.append([x, y])
                    idx += 1
                    if idx >= n:
                        break
                if idx >= n:
                    break
        elif layout == 3:
            # Hex grid: 6,5,5,5,5
            row_counts = [6, 5, 5, 5, 5]
            ny = len(row_counts)
            h = np.sqrt(3) / 2
            dy = 1.0 / (ny * h + 1.0)
            idx = 0
            for r, cnt in enumerate(row_counts):
                y = dy * (r * h + 0.5)
                dx = 1.0 / (cnt + 0.5)
                for c in range(cnt):
                    x = dx * (c + 0.75)
                    centers.append([x, y])
                    idx += 1
                    if idx >= n:
                        break
                if idx >= n:
                    break

        centers = np.array(centers[:n])
        centers = np.clip(centers, 0.01, 0.99)
        radii = compute_max_radii(centers)
        s = np.sum(radii)
        if s > best_sum:
            best_sum = s
            best_centers = centers.copy()
            best_radii = radii.copy()

    return best_centers, best_radii, best_sum


def compute_max_radii(centers):
    n = centers.shape[0]
    # Precompute pairwise distances
    dists = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))
    # Wall distances
    wall_dist = np.min(np.column_stack([centers[:, 0], centers[:, 1],
                                         1 - centers[:, 0], 1 - centers[:, 1]]), axis=1)
    # Initialize radii to wall limits
    radii = wall_dist.copy()
    # Iteratively resolve overlaps - multiple passes for better convergence
    for iteration in range(50):
        changed = False
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            max_r = max(max_r, 0.0)
            if abs(radii[i] - max_r) > 1e-12:
                radii[i] = max_r
                changed = True
        if not changed:
            break
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
