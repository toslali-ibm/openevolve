# HYPOTHESIS-1: Reverting to Program 1's proven approach (force relaxation + LP radii in local search) will recover the 0.9487 score since the fast iterative radii caused the decline to 0.6815
# MECHANISM-1: The iterative radii method gives inaccurate estimates causing local search to accept bad moves; LP radii are exact, so search moves are correctly evaluated
# EXPECT-1: combined_score > 0.94
# RESULT-1: CONFIRMED (actual=0.9504048510589433)

# HYPOTHESIS-2: Using more local search iterations (1000) with LP radii and a wider perturbation range will push beyond 2.50 sum_radii
# MECHANISM-2: Program 1 used 800 iterations and got 2.4997; more iterations with good step sizes explore more of the landscape
# EXPECT-2: sum_radii > 2.49
# RESULT-2: CONFIRMED (actual=2.5043167825403154)

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
    
    # Force-directed optimization
    centers = _relax(centers, 600)
    
    # LP radii
    radii = _compute_radii_lp(centers)
    best_sum = float(np.sum(radii))
    best_centers = centers.copy()
    best_radii = radii.copy()
    
    # Local search with LP radii evaluation
    rng = np.random.RandomState(123)
    for trial in range(1000):
        idx = trial % n
        mag = 0.018 * (1.0 - trial / 1000.0) + 0.001
        delta = rng.randn(2) * mag
        new_centers = best_centers.copy()
        new_centers[idx] = np.clip(new_centers[idx] + delta, 0.002, 0.998)
        new_radii = _compute_radii_lp(new_centers)
        new_sum = float(np.sum(new_radii))
        if new_sum > best_sum:
            best_sum = new_sum
            best_centers = new_centers
            best_radii = new_radii
    
    return best_centers, best_radii, best_sum


def _relax(centers, iters):
    """Force-directed optimization using pure repulsive forces."""
    n = len(centers)
    lr = 0.001
    for it in range(iters):
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
            forces[i, 0] += ws / max(x, 0.001) ** 2 - ws / max(1 - x, 0.001) ** 2
            forces[i, 1] += ws / max(y, 0.001) ** 2 - ws / max(1 - y, 0.001) ** 2
        max_force = np.max(np.sqrt(np.sum(forces ** 2, axis=1)))
        if max_force > 0:
            centers += forces / max_force * lr
        centers = np.clip(centers, 0.005, 0.995)
        lr *= 0.998
    return centers


def _compute_radii_lp(centers):
    """Use LP to maximize sum of radii."""
    n = len(centers)
    dists = np.sqrt(((centers[:, None] - centers[None, :]) ** 2).sum(axis=2))
    wall = np.array([min(c[0], c[1], 1-c[0], 1-c[1]) for c in centers])
    try:
        from scipy.optimize import linprog
        c_obj = -np.ones(n)
        A_rows = []
        b_vals = []
        for i in range(n):
            for j in range(i+1, n):
                row = np.zeros(n)
                row[i] = 1.0
                row[j] = 1.0
                A_rows.append(row)
                b_vals.append(dists[i, j])
        for i in range(n):
            row = np.zeros(n)
            row[i] = 1.0
            A_rows.append(row)
            b_vals.append(wall[i])
        res = linprog(c_obj, A_ub=np.array(A_rows), b_ub=np.array(b_vals),
                      bounds=[(0, None)] * n, method='highs')
        if res.success:
            return np.maximum(res.x, 0.0)
    except:
        pass
    # Fallback
    radii = wall.copy()
    np.fill_diagonal(dists, np.inf)
    for _ in range(100):
        for i in np.argsort(-wall):
            radii[i] = max(min(wall[i], np.min(dists[i] - radii)), 0.0)
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