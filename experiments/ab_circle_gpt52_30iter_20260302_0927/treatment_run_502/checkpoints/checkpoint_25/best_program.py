# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using scipy LP to maximize sum of radii (instead of Gauss-Seidel fixed-point) combined with better hex layouts and gradient-based center optimization will significantly improve sum_radii
# MECHANISM-1: LP finds the true maximum sum of radii for given centers; gradient-based optimization moves centers in the direction that increases LP objective most
# EXPECT-1: sum_radii > 2.50
# RESULT-1: REFUTED (actual=2.487045194115579)
# HYPOTHESIS-2: Starting from a carefully constructed 5-row hex grid (5,5,6,5,5) with proper spacing and using LP radii will exceed the previous 2.4148 substantially
# MECHANISM-2: The 5,5,6,5,5 pattern fills the square symmetrically; LP radii allocation gives larger circles more space where available
# EXPECT-2: combined_score > 0.95
# RESULT-2: REFUTED (actual=0.9438501685448119)
"""Constructor-based circle packing for n=26 circles"""
import numpy as np
from scipy.optimize import linprog


def construct_packing():
    n = 26
    best_sum = 0
    best_centers = None
    best_radii = None

    candidates = []

    # Generate many hex grid candidates
    row_configs = [
        [5, 6, 5, 6, 4],
        [6, 5, 6, 5, 4],
        [5, 5, 6, 5, 5],
        [4, 5, 4, 5, 4, 4],
        [5, 4, 5, 4, 5, 3],
        [3, 4, 5, 4, 5, 4, 1],
        [4, 5, 5, 5, 4, 3],
        [5, 5, 5, 5, 3, 3],
        [4, 4, 5, 4, 5, 4],
        [5, 4, 4, 5, 4, 4],
        [3, 5, 5, 5, 5, 3],
        [4, 5, 5, 5, 5, 2],
        [5, 5, 5, 5, 6],
        [6, 5, 5, 5, 5],
    ]
    for rc in row_configs:
        if sum(rc) != n:
            continue
        c = generate_hex_grid(rc)
        if c is not None and len(c) == n:
            candidates.append(c)

    # Tight hex grid with proper spacing
    for r_factor in [0.094, 0.096, 0.098, 0.100, 0.102]:
        c = generate_tight_hex(r_factor)
        if c is not None:
            candidates.append(c)

    # Literature-inspired config
    lit = generate_literature_config()
    if lit is not None:
        candidates.append(lit)

    # Equal-spaced config from Program 2
    candidates.append(generate_program2_config())

    for centers in candidates:
        radii = compute_max_radii_lp(centers)
        if radii is not None:
            s = np.sum(radii)
            if s > best_sum:
                best_sum = s
                best_centers = centers.copy()
                best_radii = radii.copy()

    # Gradient-based local optimization
    if best_centers is not None:
        best_centers, best_radii, best_sum = local_optimize(best_centers, best_radii, best_sum)

    return best_centers, best_radii, best_sum


def generate_program2_config():
    """Config from Program 2 which scored 0.9131."""
    return np.array([
        [0.099655, 0.099655],[0.298965, 0.099655],[0.500000, 0.099655],[0.701035, 0.099655],[0.900345, 0.099655],
        [0.199310, 0.272188],[0.399620, 0.272188],[0.600380, 0.272188],[0.800690, 0.272188],
        [0.099655, 0.444721],[0.298965, 0.444721],[0.500000, 0.444721],[0.701035, 0.444721],[0.900345, 0.444721],
        [0.199310, 0.617254],[0.399620, 0.617254],[0.600380, 0.617254],[0.800690, 0.617254],
        [0.099655, 0.789787],[0.298965, 0.789787],[0.500000, 0.789787],[0.701035, 0.789787],[0.900345, 0.789787],
        [0.298965, 0.962320],[0.500000, 0.962320],[0.701035, 0.962320],
    ])


def generate_hex_grid(row_config):
    n_rows = len(row_config)
    n = sum(row_config)
    dy = 1.0 / (n_rows + 1)
    centers = []
    for row_idx, n_cols in enumerate(row_config):
        y = dy * (row_idx + 1)
        dx = 1.0 / (n_cols + 1)
        offset = 0.0
        if row_idx % 2 == 1:
            offset = dx * 0.5
        for col_idx in range(n_cols):
            x = dx * (col_idx + 1) + offset
            centers.append([np.clip(x, 0.01, 0.99), np.clip(y, 0.01, 0.99)])
    if len(centers) != n:
        return None
    return np.array(centers)


def generate_tight_hex(r_approx):
    """Generate hex grid with specific radius-based spacing."""
    n = 26
    row_counts = [5, 6, 5, 6, 4]
    dy = r_approx * np.sqrt(3) * 2
    dx = r_approx * 2

    total_h = (len(row_counts) - 1) * dy + 2 * r_approx
    y_off = (1.0 - total_h) / 2 + r_approx

    centers = []
    for row_idx, nc in enumerate(row_counts):
        y = y_off + row_idx * dy
        total_w = (nc - 1) * dx + 2 * r_approx
        x_off = (1.0 - total_w) / 2 + r_approx
        if row_idx % 2 == 1:
            # Offset by half spacing for hex
            pass  # already centered differently due to different nc
        for col_idx in range(nc):
            x = x_off + col_idx * dx
            centers.append([np.clip(x, 0.005, 0.995), np.clip(y, 0.005, 0.995)])

    if len(centers) != n:
        return None
    return np.array(centers)


def generate_literature_config():
    n = 26
    r_approx = 1.0 / (2 * 5.1)
    centers = []
    y1 = r_approx
    for i in range(5):
        x = r_approx + i * 2 * r_approx * 1.02
        centers.append([x, y1])
    y2 = y1 + r_approx * np.sqrt(3)
    for i in range(6):
        x = i * 2 * r_approx * 1.02
        centers.append([x, y2])
    y3 = y2 + r_approx * np.sqrt(3)
    for i in range(5):
        x = r_approx + i * 2 * r_approx * 1.02
        centers.append([x, y3])
    y4 = y3 + r_approx * np.sqrt(3)
    for i in range(6):
        x = i * 2 * r_approx * 1.02
        centers.append([x, y4])
    y5 = y4 + r_approx * np.sqrt(3)
    for i in range(4):
        x = 2 * r_approx + i * 2 * r_approx * 1.02
        centers.append([x, y5])
    centers = np.array(centers[:n])
    for dim in range(2):
        mn, mx = centers[:, dim].min(), centers[:, dim].max()
        if mx > mn:
            centers[:, dim] = 0.05 + 0.9 * (centers[:, dim] - mn) / (mx - mn)
        else:
            centers[:, dim] = 0.5
    return centers


def compute_max_radii_lp(centers):
    """Use linear programming to maximize sum of radii."""
    n = centers.shape[0]

    # Pairwise distances
    diff = centers[:, None, :] - centers[None, :, :]
    dists = np.sqrt((diff * diff).sum(axis=2))

    # Wall distances
    wall = np.min(np.column_stack([
        centers[:, 0], centers[:, 1],
        1 - centers[:, 0], 1 - centers[:, 1]
    ]), axis=1)

    # LP: maximize sum(r_i) = minimize -sum(r_i)
    # subject to: r_i + r_j <= d_ij for all i<j
    #             r_i <= wall_i for all i
    #             r_i >= 0

    c_obj = -np.ones(n)  # minimize negative sum

    # Pairwise constraints: r_i + r_j <= d_ij
    pairs = []
    b_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            pairs.append(row)
            b_pairs.append(dists[i, j])

    # Wall constraints: r_i <= wall_i
    A_wall = np.eye(n)
    b_wall = wall

    if pairs:
        A_ub = np.vstack([np.array(pairs), A_wall])
        b_ub = np.concatenate([np.array(b_pairs), b_wall])
    else:
        A_ub = A_wall
        b_ub = b_wall

    bounds = [(0, None) for _ in range(n)]

    try:
        result = linprog(c_obj, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        if result.success:
            return result.x
    except:
        pass

    # Fallback to iterative method
    return compute_max_radii_iterative(centers)


def compute_max_radii_iterative(centers):
    n = centers.shape[0]
    dists = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(dists, 1e9)
    wall = np.min(np.column_stack([
        centers[:, 0], centers[:, 1],
        1 - centers[:, 0], 1 - centers[:, 1]
    ]), axis=1)
    radii = wall.copy()
    for _ in range(200):
        old = radii.copy()
        for i in range(n):
            radii[i] = max(0.0, min(wall[i], np.min(dists[i] - radii)))
        if np.max(np.abs(radii - old)) < 1e-12:
            break
    return radii


def local_optimize(centers, radii, current_sum, n_iters=300):
    """Jitter centers to improve total sum of radii using LP for radii."""
    n = len(radii)
    best_centers = centers.copy()
    best_radii = radii.copy()
    best_sum = current_sum

    step = 0.015
    for it in range(n_iters):
        i = it % n
        improved_this_circle = False
        for dx, dy in [(step, 0), (-step, 0), (0, step), (0, -step),
                        (step*0.7, step*0.7), (-step*0.7, -step*0.7),
                        (step*0.7, -step*0.7), (-step*0.7, step*0.7)]:
            trial = best_centers.copy()
            trial[i, 0] = np.clip(trial[i, 0] + dx, 0.001, 0.999)
            trial[i, 1] = np.clip(trial[i, 1] + dy, 0.001, 0.999)
            trial_radii = compute_max_radii_lp(trial)
            if trial_radii is not None:
                trial_sum = np.sum(trial_radii)
                if trial_sum > best_sum + 1e-10:
                    best_centers = trial.copy()
                    best_radii = trial_radii.copy()
                    best_sum = trial_sum
                    improved_this_circle = True

        if it % n == n - 1:
            step *= 0.88

    return best_centers, best_radii, best_sum


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