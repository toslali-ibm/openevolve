# HYPOTHESIS-1: Simplifying to the proven hex-grid approach from Program 1 with faster radii computation and more efficient local search will restore validity and exceed 0.95 combined_score
# MECHANISM-1: The current program times out due to expensive vectorized distance recomputation in local_optimize; precomputing distances and using in-place Gauss-Seidel updates is much faster
# EXPECT-1: combined_score > 0.95
# RESULT-1: REFUTED (actual=0.9484116384624893)
# HYPOTHESIS-2: Using multiple step sizes in local optimization and more iterations within time budget will push sum_radii above 2.5
# MECHANISM-2: Coarse steps find better basin, fine steps refine; precomputed pairwise distances make each evaluation O(n) instead of O(n^2)
# EXPECT-2: sum_radii > 2.5
# RESULT-2: REFUTED (actual=2.499064667348659)
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    row_counts = [5, 4, 5, 4, 5, 3]  # sum = 26
    r_est = 0.1
    row_height = r_est * np.sqrt(3)
    
    centers = []
    y_start = r_est
    for row_idx, nc in enumerate(row_counts):
        y = y_start + row_idx * row_height
        if row_idx % 2 == 0:
            x_spacing = 1.0 / nc
            for j in range(nc):
                centers.append([x_spacing * (j + 0.5), y])
        else:
            x_spacing_even = 1.0 / 5
            for j in range(nc):
                centers.append([x_spacing_even * (j + 1), y])
    
    centers = np.array(centers[:n])
    radii = _compute_radii(centers)
    
    # Local optimization with precomputed structure
    best_sum = np.sum(radii)
    steps = [0.005, 0.003, 0.002, 0.001, 0.0005]
    dirs = np.array([(1,0),(-1,0),(0,1),(0,-1),(0.7,0.7),(0.7,-0.7),(-0.7,0.7),(-0.7,-0.7)])
    
    for step in steps:
        for _ in range(40):
            improved = False
            for i in range(n):
                old_pos = centers[i].copy()
                for d in dirs:
                    new_pos = old_pos + step * d
                    if new_pos[0] < 0.001 or new_pos[0] > 0.999 or new_pos[1] < 0.001 or new_pos[1] > 0.999:
                        continue
                    centers[i] = new_pos
                    tr = _compute_radii(centers)
                    s = np.sum(tr)
                    if s > best_sum + 1e-12:
                        radii = tr
                        best_sum = s
                        improved = True
                        break
                    centers[i] = old_pos
                if not improved:
                    centers[i] = old_pos
            if not improved:
                break
    
    return centers, radii, float(best_sum)


def _compute_radii(centers):
    n = centers.shape[0]
    dists = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            d = np.sqrt((centers[i,0]-centers[j,0])**2 + (centers[i,1]-centers[j,1])**2)
            dists[i,j] = d
            dists[j,i] = d
    
    wall = np.empty(n)
    for i in range(n):
        wall[i] = min(centers[i,0], centers[i,1], 1-centers[i,0], 1-centers[i,1])
    
    r = wall.copy()
    for _ in range(50):
        changed = False
        for i in range(n):
            mr = wall[i]
            for j in range(n):
                if i != j:
                    v = dists[i,j] - r[j]
                    if v < mr:
                        mr = v
            if mr < 0:
                mr = 0.0
            if abs(r[i] - mr) > 1e-12:
                r[i] = mr
                changed = True
        if not changed:
            break
    return r


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