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
    
    # Try multiple layout strategies and keep the best
    layouts = []
    
    # Layout 1: 5x5 grid + 1 extra
    c1 = []
    for i in range(5):
        for j in range(5):
            c1.append([(j + 0.5) / 5.0, (i + 0.5) / 5.0])
    c1.append([0.5, 0.5])  # 26th at center (will be pushed)
    layouts.append(np.array(c1))
    
    # Layout 2: hex grid 5,4,5,4,4,4
    c2 = []
    counts2 = [5, 4, 5, 4, 4, 4]
    dy2 = 1.0 / len(counts2)
    for ri, cnt in enumerate(counts2):
        y = (ri + 0.5) * dy2
        dx = 1.0 / cnt
        off = dx / 2.0
        for ci in range(cnt):
            c2.append([off + ci * dx, y])
    layouts.append(np.array(c2[:n]))
    
    # Layout 3: hex grid 4,5,4,5,4,4
    c3 = []
    counts3 = [4, 5, 4, 5, 4, 4]
    dy3 = 1.0 / len(counts3)
    for ri, cnt in enumerate(counts3):
        y = (ri + 0.5) * dy3
        dx = 1.0 / cnt
        off = dx / 2.0
        for ci in range(cnt):
            c3.append([off + ci * dx, y])
    layouts.append(np.array(c3[:n]))
    
    # Layout 4: hex grid 5,5,4,4,4,4
    c4 = []
    counts4 = [5, 5, 4, 4, 4, 4]
    dy4 = 1.0 / len(counts4)
    for ri, cnt in enumerate(counts4):
        y = (ri + 0.5) * dy4
        dx = 1.0 / cnt
        off = dx / 2.0
        for ci in range(cnt):
            c4.append([off + ci * dx, y])
    layouts.append(np.array(c4[:n]))
    
    # Layout 5: proper hex with sqrt(3)/2 vertical spacing
    c5 = []
    counts5 = [5, 4, 5, 4, 5, 3]
    r5 = 0.1
    dy5 = r5 * np.sqrt(3)
    th = (len(counts5) - 1) * dy5
    y0_5 = (1.0 - th) / 2.0
    for ri, cnt in enumerate(counts5):
        y = y0_5 + ri * dy5
        dx = 1.0 / cnt
        off = dx / 2.0
        for ci in range(cnt):
            c5.append([off + ci * dx, y])
    layouts.append(np.array(c5[:n]))
    
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
    """Fast vectorized fixed-point iteration for max radii."""
    n = centers.shape[0]
    diff = centers[:, None, :] - centers[None, :, :]
    dists = np.sqrt((diff ** 2).sum(axis=2))
    np.fill_diagonal(dists, np.inf)
    wall = np.minimum(np.minimum(centers[:, 0], centers[:, 1]),
                      np.minimum(1.0 - centers[:, 0], 1.0 - centers[:, 1]))
    r = wall.copy()
    for _ in range(100):
        cand = np.min(dists - r[None, :], axis=1)
        newr = np.clip(np.minimum(wall, cand), 0.0, None)
        if np.max(np.abs(newr - r)) < 1e-14:
            break
        r = 0.5 * newr + 0.5 * r
    # Final grow pass
    for _ in range(30):
        changed = False
        for i in range(n):
            mx = wall[i]
            for j in range(n):
                if j != i:
                    mx = min(mx, dists[i, j] - r[j])
            if mx > r[i] + 1e-14:
                r[i] = mx
                changed = True
        if not changed:
            break
    return r


def local_optimize(centers, radii, current_sum):
    """Multi-scale local search with greedy updates."""
    n = centers.shape[0]
    best_c = centers.copy()
    best_r = radii.copy()
    best_s = current_sum
    moves = [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1),
             (0.5,1),(0.5,-1),(-0.5,1),(-0.5,-1),(1,0.5),(-1,0.5),(1,-0.5),(-1,-0.5)]
    for trial in range(15):
        step = 0.04 / (1 + trial * 0.4)
        improved = False
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
                    ci = best_c[i].copy()
                    improved = True
        if not improved and trial > 3:
            break
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
