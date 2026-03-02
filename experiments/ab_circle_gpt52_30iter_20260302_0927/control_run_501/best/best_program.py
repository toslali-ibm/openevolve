# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np
from scipy.optimize import linprog


def construct_packing():
    np.random.seed(42)
    n = 26
    configs = [[5,6,5,6,4],[6,5,6,5,4],[5,5,6,5,5],[4,5,4,5,4,4],[5,4,5,4,5,3]]
    best_sum = 0.0
    best_c = None
    best_r = None
    for rows in configs:
        if sum(rows) != n:
            continue
        centers = make_hex_grid(rows)
        radii = compute_radii_lp(centers)
        s = float(np.sum(radii))
        if s > best_sum:
            best_sum, best_c, best_r = s, centers.copy(), radii.copy()
    # Multi-phase local search
    centers = best_c
    for phase in range(4):
        step_base = [0.04, 0.015, 0.005, 0.002][phase]
        n_iters = [500, 500, 400, 300][phase]
        for it in range(n_iters):
            trial = centers.copy()
            idx = np.random.randint(n)
            step = step_base * (1.0 - 0.5 * it / n_iters)
            trial[idx, 0] = np.clip(trial[idx, 0] + np.random.uniform(-step, step), 0.005, 0.995)
            trial[idx, 1] = np.clip(trial[idx, 1] + np.random.uniform(-step, step), 0.005, 0.995)
            tr = compute_radii_lp(trial)
            ts = float(np.sum(tr))
            if ts > best_sum:
                centers, best_r, best_sum = trial, tr, ts
    return centers, best_r, best_sum


def make_hex_grid(rows):
    n = sum(rows)
    nrows = len(rows)
    mx = max(rows)
    sp = 1.0 / (mx + 0.5)
    dy = sp * np.sqrt(3) / 2.0
    th = (nrows - 1) * dy
    y0 = (1.0 - th) / 2.0
    cl = []
    for ri, nc in enumerate(rows):
        y = y0 + ri * dy
        rw = (nc - 1) * sp
        x0 = (1.0 - rw) / 2.0
        for j in range(nc):
            cl.append([x0 + j * sp, y])
    return np.array(cl[:n])


def compute_radii_lp(centers):
    n = len(centers)
    c = -np.ones(n)
    A_rows = []
    b_rows = []
    for i in range(n):
        row = np.zeros(n); row[i] = 1.0
        A_rows.append(row)
        b_rows.append(min(centers[i,0], centers[i,1], 1-centers[i,0], 1-centers[i,1]))
    for i in range(n):
        for j in range(i+1, n):
            d = np.linalg.norm(centers[i] - centers[j])
            row = np.zeros(n); row[i] = 1.0; row[j] = 1.0
            A_rows.append(row); b_rows.append(d)
    res = linprog(c, A_ub=np.array(A_rows), b_ub=np.array(b_rows), bounds=[(0,None)]*n, method='highs')
    if res.success:
        return np.maximum(res.x, 0.0)
    return np.zeros(n)


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
