# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    
    # Use a hex-grid based layout optimized for 26 circles in unit square
    # 6 rows with alternating 4 and 5 circles per row, offset for hex packing
    # Row counts: 4, 5, 4, 5, 4, 4 = 26
    row_counts = [4, 5, 4, 5, 4, 4]
    n_rows = len(row_counts)
    
    # Spacing
    r_approx = 1.0 / (2 * max(row_counts))  # ~0.1
    dy = np.sqrt(3) * r_approx  # hex vertical spacing
    
    # Adjust to fill the square better
    total_height = (n_rows - 1) * dy
    y_offset = (1.0 - total_height) / 2.0
    
    centers = []
    for row_idx, count in enumerate(row_counts):
        y = y_offset + row_idx * dy
        x_spacing = 1.0 / count
        x_offset = x_spacing / 2.0
        if count == 5:
            x_offset = x_spacing / 2.0
        for col_idx in range(count):
            x = x_offset + col_idx * x_spacing
            centers.append([x, y])
    
    centers = np.array(centers[:n])
    
    # Now optimize positions and radii using iterative improvement
    best_centers = centers.copy()
    best_radii = compute_max_radii_iterative(best_centers)
    best_sum = np.sum(best_radii)
    
    # Try multiple layout strategies and keep the best (small set, but higher quality)
    layouts = []

    def hex_layout(counts, shear=0.0):
        m = len(counts)
        # choose dy so top/bottom rows have similar wall slack as left/right
        dy = 1.0 / (m + 0.15)
        pts = []
        for ri, cnt in enumerate(counts):
            y = (ri + 0.5) * dy
            dx = 1.0 / cnt
            off = 0.5 * dx + (0.5 * dx if (ri & 1) else 0.0)
            for ci in range(cnt):
                x = off + ci * dx + shear * (y - 0.5)
                pts.append([x, y])
        return np.array(pts[:n])

    # baseline grids
    c1 = [[(j + 0.5) / 5.0, (i + 0.5) / 5.0] for i in range(5) for j in range(5)]
    c1.append([0.5, 0.5])
    layouts.append(np.array(c1))

    # a few hex row patterns + slight shear to better match square boundary effects
    for counts in ([5, 4, 5, 4, 4, 4], [4, 5, 4, 5, 4, 4], [5, 5, 4, 4, 4, 4], [6, 4, 5, 4, 4, 3]):
        for sh in (0.0, 0.06, -0.06):
            layouts.append(hex_layout(counts, shear=sh))
    
    for layout in layouts:
        layout_c = np.clip(layout, 0.001, 0.999)
        r = compute_max_radii_iterative(layout_c)
        s = np.sum(r)
        if s > best_sum:
            best_centers = layout_c.copy()
            best_radii = r.copy()
            best_sum = s
    
    # Local optimization: jitter centers to improve sum
    best_centers, best_radii, best_sum = local_optimize(best_centers, best_radii, best_sum)
    
    return best_centers, best_radii, best_sum


def compute_max_radii_iterative(centers):
    """Fast fixed-point update: r_i = min(wall_i, min_j(d_ij - r_j))."""
    n = centers.shape[0]
    dx = centers[:, 0][:, None] - centers[:, 0][None, :]
    dy = centers[:, 1][:, None] - centers[:, 1][None, :]
    dists = np.sqrt(dx * dx + dy * dy)
    np.fill_diagonal(dists, np.inf)

    wall = np.minimum.reduce([centers[:, 0], centers[:, 1], 1.0 - centers[:, 0], 1.0 - centers[:, 1]])

    r = wall.copy()
    for _ in range(80):
        # candidate from neighbors
        cand = np.min(dists - r[None, :], axis=1)
        newr = np.clip(np.minimum(wall, cand), 0.0, None)
        if np.max(np.abs(newr - r)) < 1e-12:
            r = newr
            break
        # mild damping improves stability and tends to increase sum after local moves
        r = 0.6 * newr + 0.4 * r
    return r


def local_optimize(centers, radii, current_sum):
    """Coordinate + pairwise repulsion search (cheap, many steps)."""
    n = centers.shape[0]
    best_c = centers.copy()
    best_r = radii.copy()
    best_s = current_sum

    # precomputed move set (kept small for speed)
    moves = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)]
    for trial in range(10):
        step = 0.03 / (1 + 0.7 * trial)

        improved = False
        # (A) single-point coordinate moves
        for i in range(n):
            ci = best_c[i].copy()
            for mx, my in moves:
                new_c = best_c.copy()
                new_c[i, 0] = np.clip(ci[0] + mx * step, 1e-3, 1 - 1e-3)
                new_c[i, 1] = np.clip(ci[1] + my * step, 1e-3, 1 - 1e-3)
                new_r = compute_max_radii_iterative(new_c)
                new_s = float(np.sum(new_r))
                if new_s > best_s:
                    best_c, best_r, best_s = new_c, new_r, new_s
                    improved = True
                    ci = best_c[i].copy()

        # (B) pairwise "unclogging": push closest pair apart a bit
        if not improved:
            dx = best_c[:, 0][:, None] - best_c[:, 0][None, :]
            dy = best_c[:, 1][:, None] - best_c[:, 1][None, :]
            d2 = dx * dx + dy * dy
            np.fill_diagonal(d2, np.inf)
            a, b = divmod(int(np.argmin(d2)), n)
            v = best_c[a] - best_c[b]
            norm = float(np.hypot(v[0], v[1])) + 1e-12
            v = v / norm
            new_c = best_c.copy()
            new_c[a] = np.clip(new_c[a] + 0.5 * step * v, 1e-3, 1 - 1e-3)
            new_c[b] = np.clip(new_c[b] - 0.5 * step * v, 1e-3, 1 - 1e-3)
            new_r = compute_max_radii_iterative(new_c)
            new_s = float(np.sum(new_r))
            if new_s > best_s:
                best_c, best_r, best_s = new_c, new_r, new_s

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
