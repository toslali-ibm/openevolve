# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    np.random.seed(42)
    # Try hex grids with rows summing to 26
    configs = [[5,6,5,6,4],[6,5,6,5,4],[5,5,6,5,5],[4,5,4,5,4,4],[5,4,5,4,5,3]]
    best_sum = 0
    best_c = None
    best_r = None
    for rows in configs:
        if sum(rows) != n:
            continue
        r_est = 0.5 / max(rows)
        cl = []
        nr = len(rows)
        ysp = 1.0 / (nr + 0.5)
        for ri, nc in enumerate(rows):
            y = ysp * (ri + 0.75)
            xsp = 1.0 / (nc + 0.5)
            for ci in range(nc):
                cl.append([xsp * (ci + 0.5), y])
        centers = np.array(cl[:n])
        centers = np.clip(centers, 0.01, 0.99)
        radii = compute_radii(centers)
        s = np.sum(radii)
        if s > best_sum:
            best_sum = s
            best_c = centers.copy()
            best_r = radii.copy()
    # Local search optimization
    centers = best_c
    for it in range(3000):
        trial = centers.copy()
        idx = it % n
        step = 0.025 * (1.0 - it / 3000)
        trial[idx, 0] = np.clip(trial[idx, 0] + np.random.uniform(-step, step), 0.005, 0.995)
        trial[idx, 1] = np.clip(trial[idx, 1] + np.random.uniform(-step, step), 0.005, 0.995)
        tr = compute_radii(trial)
        ts = np.sum(tr)
        if ts > best_sum:
            centers = trial
            best_sum = ts
            best_r = tr
    return centers, best_r, best_sum


def compute_radii(centers):
    n = len(centers)
    wall = np.min(np.column_stack([centers[:,0], centers[:,1], 1-centers[:,0], 1-centers[:,1]]), axis=1)
    dists = np.full((n, n), np.inf)
    for i in range(n):
        for j in range(i+1, n):
            d = np.linalg.norm(centers[i] - centers[j])
            dists[i,j] = d
            dists[j,i] = d
    radii = wall.copy()
    for _ in range(80):
        changed = False
        for i in range(n):
            mr = wall[i]
            for j in range(n):
                if i != j:
                    mr = min(mr, dists[i,j] - radii[j])
            mr = max(mr, 0.0)
            if abs(radii[i] - mr) > 1e-12:
                radii[i] = mr
                changed = True
        if not changed:
            break
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
