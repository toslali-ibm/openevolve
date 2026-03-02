# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np
from scipy.optimize import linprog


def construct_packing():
    np.random.seed(42)
    n = 26
    # Try multiple initial configurations and pick the best
    best_sum = 0
    best_c = None
    best_r = None
    
    configs = [
        [5, 6, 5, 6, 4],   # 26
        [6, 5, 6, 5, 4],   # 26
        [5, 5, 6, 5, 5],   # 26
        [4, 5, 4, 5, 4, 4], # 26
        [5, 4, 5, 4, 5, 3], # 26
    ]
    
    for rows in configs:
        centers = make_hex_grid(rows)
        centers, radii = optimize_packing(centers, n)
        s = np.sum(radii)
        if s > best_sum:
            best_sum = s
            best_c = centers.copy()
            best_r = radii.copy()
    
    return best_c, best_r, best_sum


def make_hex_grid(rows):
    """Create hex grid centers for given row counts."""
    n = sum(rows)
    nrows = len(rows)
    max_count = max(rows)
    # Spacing based on fitting max_count circles across width
    spacing = 1.0 / (max_count + 0.5)
    dy = spacing * np.sqrt(3) / 2.0
    total_h = (nrows - 1) * dy
    y_start = (1.0 - total_h) / 2.0
    
    centers_list = []
    for row_idx, nc in enumerate(rows):
        y = y_start + row_idx * dy
        row_w = (nc - 1) * spacing
        x_start = (1.0 - row_w) / 2.0
        for j in range(nc):
            x = x_start + j * spacing
            centers_list.append([x, y])
    return np.array(centers_list[:n])


def compute_max_radii_lp(centers):
    """Use LP to maximize sum of radii subject to constraints."""
    n = len(centers)
    # Maximize sum(r_i) subject to:
    # r_i <= wall_dist_i for all i
    # r_i + r_j <= dist(i,j) for all i<j
    # r_i >= 0
    
    # LP: minimize -sum(r) = c^T r
    c = -np.ones(n)
    
    # Inequality constraints: A_ub @ r <= b_ub
    A_rows = []
    b_rows = []
    
    # Wall constraints: r_i <= wall_dist_i
    for i in range(n):
        row = np.zeros(n)
        row[i] = 1.0
        A_rows.append(row)
        b_rows.append(min(centers[i, 0], centers[i, 1], 
                         1 - centers[i, 0], 1 - centers[i, 1]))
    
    # Pairwise constraints: r_i + r_j <= dist(i,j)
    for i in range(n):
        for j in range(i + 1, n):
            d = np.linalg.norm(centers[i] - centers[j])
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            A_rows.append(row)
            b_rows.append(d)
    
    A_ub = np.array(A_rows)
    b_ub = np.array(b_rows)
    
    bounds = [(0, None)] * n
    result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    
    if result.success:
        return np.maximum(result.x, 0.0)
    else:
        return compute_max_radii_fallback(centers)


def compute_max_radii_fallback(centers):
    """Fallback iterative radii computation."""
    n = len(centers)
    wall_dist = np.min(np.column_stack([
        centers[:, 0], centers[:, 1],
        1 - centers[:, 0], 1 - centers[:, 1]
    ]), axis=1)
    dists = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(i + 1, n):
            d = np.linalg.norm(centers[i] - centers[j])
            dists[i, j] = d
            dists[j, i] = d
    radii = wall_dist.copy()
    for _ in range(80):
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


def optimize_packing(centers, n):
    """Optimize circle positions using local search with LP radii."""
    best_centers = centers.copy()
    best_radii = compute_max_radii_lp(best_centers)
    best_sum = np.sum(best_radii)
    
    # Multi-phase optimization
    for phase in range(3):
        step_base = [0.03, 0.01, 0.003][phase]
        n_iters = [600, 600, 400][phase]
        
        for iteration in range(n_iters):
            trial = best_centers.copy()
            # Pick random circle to perturb
            idx = np.random.randint(n)
            step = step_base * (1.0 - iteration / n_iters)
            dx = np.random.uniform(-step, step)
            dy = np.random.uniform(-step, step)
            trial[idx, 0] = np.clip(trial[idx, 0] + dx, 0.005, 0.995)
            trial[idx, 1] = np.clip(trial[idx, 1] + dy, 0.005, 0.995)
            
            trial_radii = compute_max_radii_lp(trial)
            trial_sum = np.sum(trial_radii)
            if trial_sum > best_sum:
                best_centers = trial
                best_radii = trial_radii
                best_sum = trial_sum
    
    return best_centers, best_radii


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
