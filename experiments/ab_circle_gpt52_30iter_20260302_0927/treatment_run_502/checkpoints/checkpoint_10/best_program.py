# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using scipy LP to optimally assign radii given centers, combined with carefully tuned hex positions and gradient-based center optimization, will push sum_radii above 2.55
# MECHANISM-1: LP maximizes sum of radii exactly (not heuristically) for fixed centers; better starting positions + optimization finds near-optimal geometry
# EXPECT-1: sum_radii > 2.50
# RESULT-1: REFUTED (actual=2.474479055967052)
# HYPOTHESIS-2: Using multiple well-tuned hex grid configurations with proper edge touching and LP-optimal radii will exceed 0.95 target ratio
# MECHANISM-2: Circles touching walls get maximum wall-distance radii; LP redistributes remaining space optimally among interior circles
# EXPECT-2: target_ratio > 0.95
# RESULT-2: REFUTED (actual=0.9390812356611203)
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
    configs = [
        [5, 4, 5, 4, 5, 3],
        [5, 6, 5, 6, 4],
        [6, 5, 6, 5, 4],
        [5, 5, 6, 5, 5],
        [4, 5, 4, 5, 4, 4],
        [3, 4, 5, 4, 5, 4, 1],
        [4, 5, 5, 5, 4, 3],
        [5, 5, 5, 5, 6],
        [6, 5, 5, 5, 5],
        [4, 5, 5, 4, 5, 3],
        [5, 4, 5, 5, 4, 3],
        [6, 5, 6, 4, 5],
    ]
    for rc in configs:
        if sum(rc) != n:
            continue
        for use_offset in [True, False]:
            c = gen_hex(rc, use_offset)
            if c is not None and len(c) == n:
                candidates.append(c)

    # Tight hex packing touching walls
    candidates.append(gen_tight_hex())
    # Packomania-inspired
    candidates.append(gen_packomania())
    # Optimized 5-4-5-4-5-3 layout
    candidates.append(gen_optimized_hex())

    for centers in candidates:
        if centers is None or len(centers) != n:
            continue
        radii = lp_radii(centers)
        if radii is not None:
            s = np.sum(radii)
            if s > best_sum:
                best_sum = s
                best_centers = centers.copy()
                best_radii = radii.copy()

    # Local optimization with LP radii
    if best_centers is not None:
        best_centers, best_radii, best_sum = local_opt(best_centers, best_radii, best_sum)

    return best_centers, best_radii, best_sum


def lp_radii(centers):
    """Use LP to maximize sum of radii subject to non-overlap and wall constraints."""
    n = len(centers)
    # Maximize sum(r_i) = minimize -sum(r_i)
    c = -np.ones(n)

    A_ub_rows = []
    b_ub_rows = []

    # Pairwise: r_i + r_j <= dist(i,j)
    for i in range(n):
        for j in range(i + 1, n):
            d = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))
            row = np.zeros(n)
            row[i] = 1.0
            row[j] = 1.0
            A_ub_rows.append(row)
            b_ub_rows.append(d)

    # Wall: r_i <= wall_dist(i)
    for i in range(n):
        x, y = centers[i]
        wd = min(x, y, 1.0 - x, 1.0 - y)
        row = np.zeros(n)
        row[i] = 1.0
        A_ub_rows.append(row)
        b_ub_rows.append(wd)

    A_ub = np.array(A_ub_rows)
    b_ub = np.array(b_ub_rows)

    bounds = [(0, None)] * n
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
    if res.success:
        return res.x
    return None


def gen_hex(row_config, offset_odd=True):
    n_rows = len(row_config)
    n = sum(row_config)
    dy = 1.0 / (n_rows + 1)
    centers = []
    for row_idx, n_cols in enumerate(row_config):
        y = dy * (row_idx + 1)
        dx = 1.0 / (n_cols + 1)
        offset = 0.0
        if offset_odd and row_idx % 2 == 1:
            offset = dx * 0.5
        elif not offset_odd and row_idx % 2 == 0:
            offset = dx * 0.5
        for col_idx in range(n_cols):
            x = dx * (col_idx + 1) + offset
            centers.append([np.clip(x, 0.005, 0.995), np.clip(y, 0.005, 0.995)])
    if len(centers) != n:
        return None
    return np.array(centers)


def gen_tight_hex():
    """Hex grid where edge circles touch walls."""
    n = 26
    # 5-4-5-4-5-3 = 26, 6 rows
    r = 0.1  # approximate radius
    sq3 = np.sqrt(3)
    centers = []
    row_counts = [5, 4, 5, 4, 5, 3]
    for row_idx, nc in enumerate(row_counts):
        y = r + row_idx * r * sq3
        for col_idx in range(nc):
            if row_idx % 2 == 0:
                x = r + col_idx * 2 * r
            else:
                x = 2 * r + col_idx * 2 * r
            centers.append([x, y])
    centers = np.array(centers[:n])
    # Scale to fit [0,1]
    for dim in range(2):
        mn, mx = centers[:, dim].min(), centers[:, dim].max()
        span = mx - mn
        if span > 0:
            # We want min at r_edge, max at 1-r_edge
            # Approximate: scale so that edge circles are at ~r from walls
            r_edge = 0.5 / (max(row_counts) + 0.5)
            centers[:, dim] = r_edge + (1 - 2 * r_edge) * (centers[:, dim] - mn) / span
    return centers


def gen_packomania():
    """Packomania-inspired coordinates for n=26."""
    r0 = 0.099655
    d = 2 * r0
    sq3r = r0 * np.sqrt(3)
    centers = []
    # 5-4-5-4-5-3 pattern
    rows = [
        (5, r0, r0),
        (4, r0 + r0, r0 + sq3r),
        (5, r0, r0 + 2 * sq3r),
        (4, r0 + r0, r0 + 3 * sq3r),
        (5, r0, r0 + 4 * sq3r),
        (3, r0 + r0, r0 + 5 * sq3r),
    ]
    for nc, x_start, y in rows:
        for i in range(nc):
            centers.append([x_start + i * d, y])
    centers = np.array(centers[:26])
    # Scale to unit square
    for dim in range(2):
        mn, mx = centers[:, dim].min(), centers[:, dim].max()
        if mx > mn:
            margin = 0.04
            centers[:, dim] = margin + (1 - 2 * margin) * (centers[:, dim] - mn) / (mx - mn)
    return centers


def gen_optimized_hex():
    """Hand-tuned hex grid for n=26 maximizing LP sum."""
    # Use equal-radius optimal positions but with better spacing
    # 5 rows of 5 + 1 extra = 26 doesn't work well
    # Try 6-5-6-5-4 = 26
    centers = []
    n_rows_config = [6, 5, 6, 5, 4]
    n_rows = len(n_rows_config)
    # Vertical spacing to fill square
    total_h = 1.0
    dy = total_h / (n_rows + 1)
    for row_idx, nc in enumerate(n_rows_config):
        y = dy * (row_idx + 1)
        dx = 1.0 / (nc + 1)
        offset = dx * 0.3 if row_idx % 2 == 1 else 0.0
        for i in range(nc):
            x = dx * (i + 1) + offset
            centers.append([np.clip(x, 0.01, 0.99), np.clip(y, 0.01, 0.99)])
    return np.array(centers[:26])


def local_opt(centers, radii, current_sum):
    """Gradient-free local optimization of center positions."""
    n = len(radii)
    best_c = centers.copy()
    best_r = radii.copy()
    best_s = current_sum

    # Multiple rounds with decreasing step
    for step in [0.03, 0.015, 0.007, 0.003, 0.001]:
        improved = True
        while improved:
            improved = False
            for i in range(n):
                for dx, dy in [(step, 0), (-step, 0), (0, step), (0, -step),
                               (step*0.7, step*0.7), (-step*0.7, -step*0.7),
                               (step*0.7, -step*0.7), (-step*0.7, step*0.7)]:
                    trial = best_c.copy()
                    trial[i, 0] = np.clip(trial[i, 0] + dx, 0.001, 0.999)
                    trial[i, 1] = np.clip(trial[i, 1] + dy, 0.001, 0.999)
                    tr = lp_radii(trial)
                    if tr is not None:
                        ts = np.sum(tr)
                        if ts > best_s + 1e-8:
                            best_c = trial.copy()
                            best_r = tr.copy()
                            best_s = ts
                            improved = True

    return best_c, best_r, best_s


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