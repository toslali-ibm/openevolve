# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Hexagonal packing with rows [5,6,5,6,4] = 26
    # Optimize radius parameter for best packing
    best_sum = 0
    best_centers = None
    best_radii = None
    for r_approx in [0.088, 0.090, 0.092, 0.094, 0.096, 0.098, 0.100]:
        s = 2 * r_approx * 1.01
        row_configs = [5, 6, 5, 6, 4]
        hex_h = s * np.sqrt(3) / 2
        total_height = hex_h * (len(row_configs) - 1)
        y_start = 0.5 - total_height / 2
        idx = 0
        centers = np.zeros((n, 2))
        for row_idx, num_in_row in enumerate(row_configs):
            y = y_start + row_idx * hex_h
            row_width = s * (num_in_row - 1)
            x_start = 0.5 - row_width / 2
            for col in range(num_in_row):
                centers[idx] = [x_start + col * s, y]
                idx += 1
        centers = np.clip(centers, 0.01, 0.99)
        radii = compute_max_radii(centers)
        sr = np.sum(radii)
        if sr > best_sum:
            best_sum = sr
            best_centers = centers.copy()
            best_radii = radii.copy()
    # Try local optimization: nudge each center to improve sum
    centers = best_centers
    for outer in range(5):
        radii = compute_max_radii(centers)
        for i in range(n):
            best_r_sum = np.sum(radii)
            best_pos = centers[i].copy()
            for dx, dy in [(0.005,0),(-0.005,0),(0,0.005),(0,-0.005),
                           (0.002,0),(-0.002,0),(0,0.002),(0,-0.002)]:
                old = centers[i].copy()
                centers[i] = np.clip(old + [dx, dy], 0.01, 0.99)
                tr = compute_max_radii(centers)
                ts = np.sum(tr)
                if ts > best_r_sum:
                    best_r_sum = ts
                    best_pos = centers[i].copy()
                    radii = tr
                centers[i] = old
            centers[i] = best_pos
        radii = compute_max_radii(centers)
    return centers, radii, np.sum(radii)


def compute_max_radii(centers):
    n = centers.shape[0]
    dists = np.sqrt(((centers[:, None] - centers[None, :]) ** 2).sum(axis=2))
    wall_dist = np.min(np.column_stack([centers[:, 0], centers[:, 1],
                                         1 - centers[:, 0], 1 - centers[:, 1]]), axis=1)
    radii = wall_dist.copy()
    for iteration in range(80):
        changed = False
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            max_r = max(max_r, 1e-8)
            if abs(max_r - radii[i]) > 1e-12:
                radii[i] = max_r
                changed = True
        if not changed:
            break
    return np.maximum(radii, 1e-8)


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
