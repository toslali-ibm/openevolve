# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Use hexagonal-like packing: rows of 5,5,5,5,6 or similar
    # Try rows: 5,6,5,6,4 = 26 with hex offset
    row_counts = [5, 5, 6, 5, 5]
    n_rows = len(row_counts)
    # Equal vertical spacing
    dy = 1.0 / n_rows
    r_approx = dy / 2.0  # approximate radius
    
    centers = []
    for row_idx, count in enumerate(row_counts):
        y = dy * (row_idx + 0.5)
        dx = 1.0 / count
        x_offset = 0.0
        # Hex offset for alternating rows
        if row_idx % 2 == 1:
            x_offset = dx * 0.5
        for col_idx in range(count):
            x = dx * (col_idx + 0.5)
            if row_idx % 2 == 1:
                x = dx * col_idx + dx * 0.5
            centers.append([x, y])
    
    centers = np.array(centers[:n])
    
    # Iterative radii computation - multiple passes for better result
    radii = compute_max_radii(centers)
    
    # Local optimization: jiggle centers to increase sum of radii
    best_sum = np.sum(radii)
    best_centers = centers.copy()
    best_radii = radii.copy()
    
    for iteration in range(200):
        trial = best_centers.copy()
        # Perturb one random circle
        idx = iteration % n
        step = 0.02 * (1.0 - iteration / 200.0)
        np.random.seed(42 + iteration)
        delta = np.random.randn(2) * step
        trial[idx] += delta
        # Keep inside bounds
        trial[idx] = np.clip(trial[idx], 0.001, 0.999)
        
        trial_radii = compute_max_radii(trial)
        trial_sum = np.sum(trial_radii)
        
        if trial_sum > best_sum:
            best_sum = trial_sum
            best_centers = trial.copy()
            best_radii = trial_radii.copy()
    
    return best_centers, best_radii, best_sum


def compute_max_radii(centers):
    n = centers.shape[0]
    # Compute all pairwise distances
    dists = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))
    
    # Wall distances
    wall_dist = np.min([centers[:, 0], centers[:, 1], 
                        1 - centers[:, 0], 1 - centers[:, 1]], axis=0)
    
    # Start with wall-limited radii
    radii = wall_dist.copy()
    
    # Iteratively shrink radii to resolve overlaps (multiple passes)
    for _ in range(20):
        changed = False
        for i in range(n):
            for j in range(i + 1, n):
                d = dists[i, j]
                overlap = radii[i] + radii[j] - d
                if overlap > 1e-12:
                    # Shrink proportionally
                    total = radii[i] + radii[j]
                    radii[i] *= d / total
                    radii[j] *= d / total
                    changed = True
        if not changed:
            break
    
    # Expansion pass: try to grow each circle
    for _ in range(10):
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if j != i:
                    max_r = min(max_r, dists[i, j] - radii[j])
            if max_r > radii[i]:
                radii[i] = max_r
    
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
