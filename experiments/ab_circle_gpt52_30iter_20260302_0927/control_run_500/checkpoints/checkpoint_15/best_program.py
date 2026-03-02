# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def make_grid_layout(row_counts):
    """Create a grid layout from row counts."""
    n = sum(row_counts)
    dy = 1.0 / len(row_counts)
    centers = []
    for row_idx, count in enumerate(row_counts):
        y = dy * (row_idx + 0.5)
        dx = 1.0 / count
        for col in range(count):
            centers.append([dx * (col + 0.5), y])
    return np.array(centers[:n])


def construct_packing():
    n = 26
    np.random.seed(42)
    
    # Try multiple layouts
    layouts = []
    
    # Layout: 5x5 grid + 1
    c1 = []
    for i in range(5):
        for j in range(5):
            c1.append([(j + 0.5) / 5.0, (i + 0.5) / 5.0])
    c1.append([0.5, 0.9])
    layouts.append(np.array(c1))
    
    # Various row configurations
    for rc in [[5,5,5,5,6], [4,5,4,5,4,4], [5,4,5,4,4,4],
               [4,5,5,5,4,3], [5,5,4,4,4,4], [4,4,5,4,5,4],
               [3,5,5,5,5,3], [4,5,4,5,4,4]]:
        if sum(rc) == n:
            layouts.append(make_grid_layout(rc))
    
    # Hex-offset layouts
    for rc in [[5,5,5,5,6], [4,5,4,5,4,4]]:
        if sum(rc) == n:
            dy = 1.0 / len(rc)
            centers = []
            for ri, cnt in enumerate(rc):
                y = dy * (ri + 0.5)
                dx = 1.0 / cnt
                off = dx * 0.25 if ri % 2 == 1 else 0.0
                for ci in range(cnt):
                    centers.append([dx * (ci + 0.5) + off, y])
            layouts.append(np.array(centers[:n]))
    
    best_c, best_r, best_s = None, None, -1
    for layout in layouts:
        c = np.clip(layout, 0.005, 0.995)
        r = compute_max_radii(c)
        s = np.sum(r)
        if s > best_s:
            best_c, best_r, best_s = c.copy(), r.copy(), s
    
    # Local optimization
    for trial in range(10):
        step = 0.025 / (1 + trial * 0.3)
        improved = False
        for i in range(n):
            for dx, dy in [(step,0),(-step,0),(0,step),(0,-step),
                           (step*0.7,step*0.7),(-step*0.7,step*0.7),
                           (step*0.7,-step*0.7),(-step*0.7,-step*0.7)]:
                tc = best_c.copy()
                tc[i,0] = np.clip(tc[i,0]+dx, 0.005, 0.995)
                tc[i,1] = np.clip(tc[i,1]+dy, 0.005, 0.995)
                tr = compute_max_radii(tc)
                ts = np.sum(tr)
                if ts > best_s:
                    best_c, best_r, best_s = tc, tr, ts
                    improved = True
        if not improved:
            break
    
    return best_c, best_r, best_s


def compute_max_radii(centers):
    n = centers.shape[0]
    diff = centers[:, None, :] - centers[None, :, :]
    dists = np.sqrt((diff**2).sum(axis=2))
    np.fill_diagonal(dists, 1e10)
    wall = np.minimum.reduce([centers[:,0], centers[:,1],
                               1-centers[:,0], 1-centers[:,1]])
    radii = wall.copy()
    # Shrink pass
    for _ in range(30):
        changed = False
        for i in range(n):
            for j in range(i+1, n):
                ov = radii[i] + radii[j] - dists[i,j]
                if ov > 1e-12:
                    t = radii[i] + radii[j]
                    radii[i] -= ov * radii[i] / t
                    radii[j] -= ov * radii[j] / t
                    changed = True
        if not changed:
            break
    # Grow pass
    for _ in range(20):
        for i in range(n):
            mr = wall[i]
            for j in range(n):
                if j != i:
                    mr = min(mr, dists[i,j] - radii[j])
            if mr > radii[i]:
                radii[i] = mr
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
