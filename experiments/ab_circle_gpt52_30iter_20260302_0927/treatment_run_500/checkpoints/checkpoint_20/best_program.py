# HYPOTHESIS-1: Using the proven hex grid (5,6,5,6,4) with pure repulsive force optimization and non-destructive radii computation will recover the 0.86 score and improve beyond
# MECHANISM-1: Program 1 achieved 0.86 with this exact approach; the key is force-directed position optimization SEPARATE from radii computation, plus iterative max-radii that doesn't cascade errors
# EXPECT-1: combined_score > 0.86
# RESULT-1: CONFIRMED (actual=0.9486609607896715)

# HYPOTHESIS-2: Using scipy linprog to solve the LP for maximum sum of radii given fixed centers will yield better radii than iterative heuristics
# MECHANISM-2: The LP directly maximizes sum(r_i) subject to r_i+r_j<=d_ij and r_i<=wall_i, finding the true optimum instead of a heuristic approximation
# EXPECT-2: sum_radii > 2.3
# RESULT-2: CONFIRMED (actual=2.499721631680784)

# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    np.random.seed(42)
    
    # Hex grid layout: rows of 5, 6, 5, 6, 4 = 26
    centers_list = []
    row_counts = [5, 6, 5, 6, 4]
    n_rows = len(row_counts)
    dy = 1.0 / (n_rows + 1)
    
    for row_idx, count in enumerate(row_counts):
        y = dy * (row_idx + 1)
        dx = 1.0 / (count + 1)
        for col_idx in range(count):
            x = dx * (col_idx + 1)
            centers_list.append([x, y])
    
    centers = np.array(centers_list[:n])
    
    # Force-directed optimization to spread circles apart
    centers = optimize_positions(centers, iterations=600)
    
    # Compute optimal radii using LP
    radii = compute_optimal_radii_lp(centers)
    
    # Local search to further improve
    best_sum = np.sum(radii)
    best_centers = centers.copy()
    best_radii = radii.copy()
    
    rng = np.random.RandomState(123)
    for trial in range(800):
        idx = trial % n
        mag = 0.015 * (1.0 - trial / 800.0) + 0.001
        delta = rng.randn(2) * mag
        new_centers = best_centers.copy()
        new_centers[idx] = np.clip(new_centers[idx] + delta, 0.002, 0.998)
        new_radii = compute_optimal_radii_lp(new_centers)
        new_sum = np.sum(new_radii)
        if new_sum > best_sum:
            best_sum = new_sum
            best_centers = new_centers
            best_radii = new_radii
    
    return best_centers, best_radii, best_sum


def optimize_positions(centers, iterations=600):
    """Force-directed optimization using pure repulsive forces."""
    n = len(centers)
    lr = 0.001
    
    for it in range(iterations):
        forces = np.zeros_like(centers)
        
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.sqrt(np.sum(diff ** 2))
                if dist < 1e-10:
                    diff = np.array([0.001, 0.001])
                    dist = 0.00141
                force_mag = 1.0 / (dist * dist)
                force_dir = diff / dist
                forces[i] += force_dir * force_mag
                forces[j] -= force_dir * force_mag
        
        for i in range(n):
            x, y = centers[i]
            ws = 0.5
            forces[i, 0] += ws / max(x, 0.001) ** 2
            forces[i, 0] -= ws / max(1 - x, 0.001) ** 2
            forces[i, 1] += ws / max(y, 0.001) ** 2
            forces[i, 1] -= ws / max(1 - y, 0.001) ** 2
        
        max_force = np.max(np.sqrt(np.sum(forces ** 2, axis=1)))
        if max_force > 0:
            centers += forces / max_force * lr
        centers = np.clip(centers, 0.005, 0.995)
        lr *= 0.998
    
    return centers


def compute_optimal_radii_lp(centers):
    """Compute radii maximizing sum using LP via scipy."""
    n = len(centers)
    
    dists = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))
            dists[i, j] = d
            dists[j, i] = d
    
    wall_dist = np.zeros(n)
    for i in range(n):
        x, y = centers[i]
        wall_dist[i] = min(x, y, 1 - x, 1 - y)
    
    try:
        from scipy.optimize import linprog
        # Maximize sum(r_i) = minimize -sum(r_i)
        c = -np.ones(n)
        A_ub = []
        b_ub = []
        # Pairwise: r_i + r_j <= d_ij
        for i in range(n):
            for j in range(i + 1, n):
                row = np.zeros(n)
                row[i] = 1.0
                row[j] = 1.0
                A_ub.append(row)
                b_ub.append(dists[i, j])
        # Wall: r_i <= wall_dist_i
        for i in range(n):
            row = np.zeros(n)
            row[i] = 1.0
            A_ub.append(row)
            b_ub.append(wall_dist[i])
        
        A_ub = np.array(A_ub)
        b_ub = np.array(b_ub)
        bounds = [(0, None)] * n
        
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if res.success:
            return np.array(res.x)
    except ImportError:
        pass
    
    # Fallback: iterative approach
    radii = wall_dist.copy()
    for _ in range(100):
        for i in np.argsort(-wall_dist):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            radii[i] = max(max_r, 0.0)
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