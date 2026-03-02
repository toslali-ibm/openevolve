# HYPOTHESIS-1: Using multiple hex configs with LP radii and greedy coordinate descent will recover and exceed the 0.9439 best score
# MECHANISM-1: LP gives optimal radii for fixed centers; testing many configs finds good starting points; coordinate descent improves locally
# EXPECT-1: combined_score > 0.94
# RESULT-1: CONFIRMED (actual=0.9525343154712425)
# HYPOTHESIS-2: Adding configs where circles touch walls (height-binding r=1/(2+4*sqrt(3))) produces denser packings
# MECHANISM-2: Wall-touching circles maximize their own radius contribution; LP then optimally distributes remaining space
# EXPECT-2: sum_radii > 2.48
# RESULT-2: CONFIRMED (actual=2.5099279212667236)
# HYPOTHESIS-3: Keeping eval_time reasonable by limiting local search iterations to ~10 full passes with 8 directions
# MECHANISM-3: Previous best (0.9439) used 300 iters with LP which took ~4s; we use similar budget
# EXPECT-3: eval_time < 8.0
# RESULT-3: CONFIRMED (actual=4.7104668617248535)
"""Constructor-based circle packing for n=26 circles"""
import numpy as np
from scipy.optimize import linprog


def construct_packing():
    n = 26
    best_sum = 0
    best_centers = None
    best_radii = None

    candidates = []

    # Generate hex grid candidates with various row configs
    row_configs = [
        [5, 6, 5, 6, 4], [6, 5, 6, 5, 4], [5, 5, 6, 5, 5],
        [4, 5, 4, 5, 4, 4], [5, 4, 5, 4, 5, 3],
        [4, 5, 5, 5, 4, 3], [3, 5, 5, 5, 5, 3],
        [5, 5, 5, 5, 6], [6, 5, 5, 5, 5],
    ]
    for rc in row_configs:
        if sum(rc) != n:
            continue
        c = gen_hex(rc)
        if c is not None:
            candidates.append(c)

    # Height-binding configs with r = 1/(2 + (nrows-1)*sqrt(3))
    for rc in [[5, 5, 6, 5, 5], [5, 6, 5, 6, 4], [6, 5, 6, 5, 4], [4, 5, 4, 5, 4, 4]]:
        if sum(rc) != n:
            continue
        c = gen_hex_tight(rc)
        if c is not None:
            candidates.append(c)

    # Hardcoded good config from Program 2
    candidates.append(np.array([
        [0.099655,0.099655],[0.298965,0.099655],[0.500000,0.099655],[0.701035,0.099655],[0.900345,0.099655],
        [0.199310,0.272188],[0.399620,0.272188],[0.600380,0.272188],[0.800690,0.272188],
        [0.099655,0.444721],[0.298965,0.444721],[0.500000,0.444721],[0.701035,0.444721],[0.900345,0.444721],
        [0.199310,0.617254],[0.399620,0.617254],[0.600380,0.617254],[0.800690,0.617254],
        [0.099655,0.789787],[0.298965,0.789787],[0.500000,0.789787],[0.701035,0.789787],[0.900345,0.789787],
        [0.298965,0.962320],[0.500000,0.962320],[0.701035,0.962320]]))

    for centers in candidates:
        if centers is None or len(centers) != n:
            continue
        radii = lp_radii(centers)
        if radii is not None:
            s = float(np.sum(radii))
            if s > best_sum:
                best_sum = s
                best_centers = centers.copy()
                best_radii = radii.copy()

    # Greedy coordinate descent local optimization
    if best_centers is not None:
        best_centers, best_radii, best_sum = local_opt(best_centers, best_radii, best_sum, n)

    return best_centers, best_radii, best_sum


def gen_hex(row_config):
    nr = len(row_config)
    dy = 1.0 / (nr + 1)
    centers = []
    for ri, nc in enumerate(row_config):
        y = dy * (ri + 1)
        dx = 1.0 / (nc + 1)
        off = dx * 0.5 if ri % 2 == 1 else 0.0
        for ci in range(nc):
            x = dx * (ci + 1) + off
            centers.append([np.clip(x, 0.01, 0.99), np.clip(y, 0.01, 0.99)])
    return np.array(centers) if len(centers) == sum(row_config) else None


def gen_hex_tight(row_config):
    nr = len(row_config)
    r_h = 1.0 / (2.0 + (nr - 1) * np.sqrt(3))
    rh = r_h * np.sqrt(3)
    yo = r_h
    centers = []
    for ri, nc in enumerate(row_config):
        y = yo + ri * rh
        rw = 2 * r_h * nc
        xo = (1.0 - rw) / 2.0 + r_h
        for ci in range(nc):
            centers.append([np.clip(xo + ci * 2 * r_h, 0.005, 0.995), np.clip(y, 0.005, 0.995)])
    return np.array(centers) if len(centers) == sum(row_config) else None


def lp_radii(centers):
    n = len(centers)
    c = -np.ones(n)
    diff = centers[:, None, :] - centers[None, :, :]
    dists = np.sqrt((diff * diff).sum(axis=2))
    wall = np.min(np.column_stack([centers[:, 0], centers[:, 1], 1 - centers[:, 0], 1 - centers[:, 1]]), axis=1)
    rows, b = [], []
    for i in range(n):
        for j in range(i + 1, n):
            row = np.zeros(n); row[i] = 1.0; row[j] = 1.0
            rows.append(row); b.append(dists[i, j])
    A_ub = np.vstack([np.array(rows), np.eye(n)]) if rows else np.eye(n)
    b_ub = np.concatenate([np.array(b), wall]) if rows else wall
    try:
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=[(0, None)] * n, method='highs')
        if res.success:
            return res.x
    except:
        pass
    return None


def local_opt(centers, radii, best_sum, n):
    bc, br, bs = centers.copy(), radii.copy(), best_sum
    step = 0.015
    dirs = [(1,0),(-1,0),(0,1),(0,-1),(0.707,0.707),(-0.707,0.707),(0.707,-0.707),(-0.707,-0.707)]
    for outer in range(12):
        improved = False
        for i in range(n):
            for dx, dy in dirs:
                tc = bc.copy()
                tc[i, 0] = np.clip(tc[i, 0] + dx * step, 0.001, 0.999)
                tc[i, 1] = np.clip(tc[i, 1] + dy * step, 0.001, 0.999)
                tr = lp_radii(tc)
                if tr is not None:
                    ts = float(np.sum(tr))
                    if ts > bs + 1e-10:
                        bc, br, bs = tc, tr, ts
                        improved = True
        step *= 0.8
        if not improved:
            break
    return bc, br, bs


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