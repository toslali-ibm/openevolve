# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using a hex grid layout with iterative radius optimization will dramatically improve sum_radii from 0.96 to above 2.4
# MECHANISM-1: Hex grids maximize local packing density; iterative radius assignment avoids the cascading shrinkage of sequential pairwise scaling
# EXPECT-1: sum_radii > 2.4
# RESULT-1: CONFIRMED (actual=2.4148090442695973)
# HYPOTHESIS-2: Running multiple layout candidates (hex grid variants) and picking the best will find configurations closer to the 2.635 target
# MECHANISM-2: Different row configurations (5-6 alternating vs 6-5 etc.) utilize square corners differently; testing multiple finds the best fit
# EXPECT-2: target_ratio > 0.90
# RESULT-2: CONFIRMED (actual=0.916436069931536)
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    best_sum = 0
    best_centers = None
    best_radii = None

    # Try multiple layout strategies and pick the best
    candidates = []

    # Strategy 1: Hex grid with rows [5,5,5,5,6] or similar
    for row_config in [
        [5, 6, 5, 6, 4],  # 26
        [6, 5, 6, 5, 4],  # 26
        [5, 5, 6, 5, 5],  # 26
        [4, 5, 4, 5, 4, 4],  # 26
        [5, 4, 5, 4, 5, 3],  # 26
        [6, 5, 6, 5, 4],  # 26
        [4, 5, 4, 5, 4, 4],  # 26
        [3, 4, 5, 4, 5, 4, 1],  # 26
        [5, 6, 5, 6, 4],  # 26
    ]:
        if sum(row_config) != n:
            continue
        centers = generate_hex_grid(row_config)
        if centers is not None and len(centers) == n:
            candidates.append(centers)

    # Strategy 2: Regular grid 5x5 + 1 corner
    grid_centers = generate_grid_plus(n)
    if grid_centers is not None:
        candidates.append(grid_centers)

    # Strategy 3: Known good configuration from literature-inspired placement
    lit_centers = generate_literature_config()
    if lit_centers is not None:
        candidates.append(lit_centers)

    for centers in candidates:
        radii = compute_max_radii_iterative(centers)
        s = np.sum(radii)
        if s > best_sum:
            best_sum = s
            best_centers = centers.copy()
            best_radii = radii.copy()

    # Local optimization: jitter centers to improve sum
    if best_centers is not None:
        best_centers, best_radii, best_sum = local_optimize(best_centers, best_radii, best_sum)

    return best_centers, best_radii, best_sum


def generate_hex_grid(row_config):
    n_rows = len(row_config)
    n = sum(row_config)
    # Compute spacing
    max_cols = max(row_config)
    # Equal spacing vertically
    dy = 1.0 / (n_rows + 1)
    centers = []
    for row_idx, n_cols in enumerate(row_config):
        y = dy * (row_idx + 1)
        dx = 1.0 / (n_cols + 1)
        offset = 0.0
        # Hex offset for alternating rows
        if row_idx % 2 == 1:
            offset = dx * 0.5
        for col_idx in range(n_cols):
            x = dx * (col_idx + 1) + offset
            if 0.001 < x < 0.999 and 0.001 < y < 0.999:
                centers.append([x, y])
            else:
                centers.append([np.clip(x, 0.01, 0.99), np.clip(y, 0.01, 0.99)])
    if len(centers) != n:
        return None
    return np.array(centers)


def generate_grid_plus(n):
    # 5x5 grid = 25, plus one in best gap
    centers = []
    for i in range(5):
        for j in range(5):
            x = (j + 1) / 6.0
            y = (i + 1) / 6.0
            centers.append([x, y])
    # Add 26th circle in the largest gap
    centers.append([0.5 / 6.0, 0.5 / 6.0])
    return np.array(centers[:n])


def generate_literature_config():
    """Generate a configuration inspired by known good packings for n=26."""
    # Use a well-structured hex arrangement: rows of 6,5,6,5,4
    # with carefully tuned positions
    n = 26
    r_approx = 1.0 / (2 * 5.1)  # approximate radius for ~5 circles across
    centers = []

    # Row 1 (bottom): 5 circles
    y1 = r_approx
    for i in range(5):
        x = r_approx + i * 2 * r_approx * 1.02
        centers.append([x, y1])

    # Row 2: 6 circles, offset
    y2 = y1 + r_approx * np.sqrt(3)
    for i in range(6):
        x = i * 2 * r_approx * 1.02
        centers.append([x, y2])

    # Row 3: 5 circles
    y3 = y2 + r_approx * np.sqrt(3)
    for i in range(5):
        x = r_approx + i * 2 * r_approx * 1.02
        centers.append([x, y3])

    # Row 4: 6 circles, offset
    y4 = y3 + r_approx * np.sqrt(3)
    for i in range(6):
        x = i * 2 * r_approx * 1.02
        centers.append([x, y4])

    # Row 5: 4 circles
    y5 = y4 + r_approx * np.sqrt(3)
    for i in range(4):
        x = 2 * r_approx + i * 2 * r_approx * 1.02
        centers.append([x, y5])

    # Only take first 26
    centers = np.array(centers[:n])
    # Scale to fit in [0,1] x [0,1] with margins
    for dim in range(2):
        mn, mx = centers[:, dim].min(), centers[:, dim].max()
        if mx > mn:
            centers[:, dim] = 0.05 + 0.9 * (centers[:, dim] - mn) / (mx - mn)
        else:
            centers[:, dim] = 0.5
    return centers


def compute_max_radii_iterative(centers):
    """Iteratively compute maximum radii using LP-like approach."""
    n = centers.shape[0]
    # Compute all pairwise distances
    dists = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d = np.sqrt(np.sum((centers[i] - centers[j]) ** 2))
            dists[i, j] = d
            dists[j, i] = d

    # Wall distances
    wall_dist = np.zeros(n)
    for i in range(n):
        x, y = centers[i]
        wall_dist[i] = min(x, y, 1 - x, 1 - y)

    # Initialize radii to wall distance limits
    radii = wall_dist.copy()

    # Iteratively reduce radii to satisfy pairwise constraints
    for iteration in range(100):
        changed = False
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            max_r = max(max_r, 0.0)
            if abs(radii[i] - max_r) > 1e-10:
                radii[i] = max_r
                changed = True
        if not changed:
            break

    # One more pass: try to grow each radius
    for iteration in range(50):
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            radii[i] = max(max_r, 0.0)

    return radii


def local_optimize(centers, radii, current_sum, n_iters=200):
    """Jitter centers slightly to improve total sum of radii."""
    n = len(radii)
    best_centers = centers.copy()
    best_radii = radii.copy()
    best_sum = current_sum

    step = 0.02
    for it in range(n_iters):
        i = it % n
        for dx, dy in [(step, 0), (-step, 0), (0, step), (0, -step),
                        (step, step), (-step, -step), (step, -step), (-step, step)]:
            trial = best_centers.copy()
            trial[i, 0] = np.clip(trial[i, 0] + dx, 0.001, 0.999)
            trial[i, 1] = np.clip(trial[i, 1] + dy, 0.001, 0.999)
            trial_radii = compute_max_radii_iterative(trial)
            trial_sum = np.sum(trial_radii)
            if trial_sum > best_sum:
                best_centers = trial.copy()
                best_radii = trial_radii.copy()
                best_sum = trial_sum

        if it % n == n - 1:
            step *= 0.85

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