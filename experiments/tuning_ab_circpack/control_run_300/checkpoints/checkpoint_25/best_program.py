# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    best_sum = 0
    best_centers = None
    best_radii = None

    # Layout 0: 5x5 grid + 1 extra (best from previous experiments)
    for layout in range(6):
        centers = []
        if layout == 0:
            for row in range(5):
                for col in range(5):
                    x = (col + 0.5) / 5.0
                    y = (row + 0.5) / 5.0
                    centers.append([x, y])
            centers.append([0.5, 0.95])
        elif layout == 1:
            # Hex grid: rows of 5,6,5,6,4
            row_counts = [5, 6, 5, 6, 4]
            ny = len(row_counts)
            dy = 1.0 / (ny + 0.5)
            for r, cnt in enumerate(row_counts):
                y = dy * (r + 0.75)
                dx = 1.0 / (cnt + 0.5)
                for c in range(cnt):
                    x = dx * (c + 0.75)
                    centers.append([x, y])
                    if len(centers) >= n:
                        break
                if len(centers) >= n:
                    break
        elif layout == 2:
            # Hex grid: 5,5,6,5,5
            row_counts = [5, 5, 6, 5, 5]
            ny = len(row_counts)
            dy = 1.0 / (ny + 0.5)
            for r, cnt in enumerate(row_counts):
                y = dy * (r + 0.75)
                dx = 1.0 / (cnt + 0.5)
                for c in range(cnt):
                    x = dx * (c + 0.75)
                    centers.append([x, y])
                    if len(centers) >= n:
                        break
                if len(centers) >= n:
                    break
        elif layout == 3:
            # 5x5 grid + 1 in center gap
            for row in range(5):
                for col in range(5):
                    x = (col + 0.5) / 5.0
                    y = (row + 0.5) / 5.0
                    centers.append([x, y])
            centers.append([0.5, 0.05])
        elif layout == 4:
            # Hex: 6,5,6,5,4
            row_counts = [6, 5, 6, 5, 4]
            ny = len(row_counts)
            h = np.sqrt(3) / 2
            dy = 1.0 / (ny * h + 1.0)
            for r, cnt in enumerate(row_counts):
                y = dy * (r * h + 0.5)
                dx = 1.0 / (cnt + 0.5)
                for c in range(cnt):
                    x = dx * (c + 0.75)
                    centers.append([x, y])
                    if len(centers) >= n:
                        break
                if len(centers) >= n:
                    break
        elif layout == 5:
            # Slightly adjusted 5x5+1 with extra at different position
            for row in range(5):
                for col in range(5):
                    x = (col + 0.5) / 5.0
                    y = (row + 0.5) / 5.0
                    centers.append([x, y])
            centers.append([0.9, 0.9])

        centers = np.array(centers[:n])
        centers = np.clip(centers, 0.01, 0.99)
        radii = compute_max_radii(centers)
        s = np.sum(radii)
        if s > best_sum:
            best_sum = s
            best_centers = centers.copy()
            best_radii = radii.copy()

    # Local optimization with adaptive step sizes
    centers = best_centers.copy()
    radii = best_radii.copy()
    current_sum = best_sum
    
    for step_size in [0.02, 0.01, 0.005, 0.002, 0.001]:
        improved_any = True
        while improved_any:
            improved_any = False
            for i in range(n):
                for dx, dy in [(step_size,0),(-step_size,0),(0,step_size),(0,-step_size),
                               (step_size*0.7,step_size*0.7),(-step_size*0.7,step_size*0.7),
                               (step_size*0.7,-step_size*0.7),(-step_size*0.7,-step_size*0.7)]:
                    new_c = centers.copy()
                    new_c[i, 0] = np.clip(centers[i, 0] + dx, 0.001, 0.999)
                    new_c[i, 1] = np.clip(centers[i, 1] + dy, 0.001, 0.999)
                    new_r = compute_max_radii(new_c)
                    ns = np.sum(new_r)
                    if ns > current_sum + 1e-10:
                        centers = new_c
                        radii = new_r
                        current_sum = ns
                        improved_any = True
                        break

    return centers, radii, float(current_sum)


def compute_max_radii(centers):
    n = centers.shape[0]
    dists = np.sqrt(((centers[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2))
    wall_dist = np.min(np.column_stack([centers[:, 0], centers[:, 1],
                                         1 - centers[:, 0], 1 - centers[:, 1]]), axis=1)
    radii = wall_dist.copy()
    for _ in range(50):
        changed = False
        for i in range(n):
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            max_r = max(max_r, 0.0)
            if abs(radii[i] - max_r) > 1e-12:
                radii[i] = max_r
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
