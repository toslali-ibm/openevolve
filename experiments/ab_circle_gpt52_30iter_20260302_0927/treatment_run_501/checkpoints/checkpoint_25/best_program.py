# HYPOTHESIS-1: Reverting to the proven hex-grid + iterative radii from Program 1 with multi-scale local search will restore validity and exceed 0.95 combined_score
# MECHANISM-1: The force-based relaxation caused timeout/invalidity; Program 1's approach (score 0.9484) is proven fast and valid; adding swap-based moves explores more configurations
# EXPECT-1: combined_score > 0.95
# RESULT-1: REFUTED (actual=0.9491390203894613)
# HYPOTHESIS-2: Using row layout [5,4,5,4,5,3] with proper hex spacing and deterministic multi-step optimization pushes sum_radii above 2.5
# MECHANISM-2: This layout proven in Program 1 to give 2.499; tighter step schedule and more directions will find better local optimum
# EXPECT-2: sum_radii > 2.5
# RESULT-2: CONFIRMED (actual=2.50098131872623)
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    row_counts = [5, 4, 5, 4, 5, 3]
    r_est = 0.1
    rh = r_est * np.sqrt(3)
    centers = []
    y_start = r_est
    for row_idx, nc in enumerate(row_counts):
        y = y_start + row_idx * rh
        if row_idx % 2 == 0:
            sp = 1.0 / nc
            for j in range(nc):
                centers.append([sp * (j + 0.5), y])
        else:
            sp = 1.0 / 5
            for j in range(nc):
                centers.append([sp * (j + 1), y])
    centers = np.array(centers[:n])
    radii = _compute_radii(centers)
    best_sum = np.sum(radii)
    dirs = [(1,0),(-1,0),(0,1),(0,-1),(0.7,0.7),(0.7,-0.7),(-0.7,0.7),(-0.7,-0.7),
            (1,0.5),(-1,0.5),(0.5,1),(-0.5,1),(1,-0.5),(-1,-0.5),(0.5,-1),(-0.5,-1)]
    for step in [0.008, 0.005, 0.003, 0.002, 0.001, 0.0005, 0.0002]:
        for _ in range(30):
            improved = False
            for i in range(n):
                old = centers[i].copy()
                for d in dirs:
                    np_ = old + np.array(d) * step
                    if np_[0] < 0.001 or np_[0] > 0.999 or np_[1] < 0.001 or np_[1] > 0.999:
                        continue
                    centers[i] = np_
                    tr = _compute_radii(centers)
                    s = np.sum(tr)
                    if s > best_sum + 1e-12:
                        radii = tr
                        best_sum = s
                        improved = True
                        break
                    centers[i] = old
            if not improved:
                break
    return centers, radii, float(best_sum)


def _compute_radii(centers):
    n = centers.shape[0]
    dx = centers[:, 0:1] - centers[:, 0:1].T
    dy = centers[:, 1:2] - centers[:, 1:2].T
    dists = np.sqrt(dx*dx + dy*dy)
    np.fill_diagonal(dists, 1e10)
    wall = np.minimum(np.minimum(centers[:,0], 1-centers[:,0]),
                      np.minimum(centers[:,1], 1-centers[:,1]))
    r = wall.copy()
    for _ in range(50):
        changed = False
        for i in range(n):
            mr = wall[i]
            v = dists[i] - r
            v[i] = 1e10
            mn = np.min(v)
            if mn < mr:
                mr = mn
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