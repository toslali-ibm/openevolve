# HYPOTHESIS-1: Reverting to the proven [5,4,5,4,5,3] layout from Program 1 (score 0.9484) and adding multiple seed configurations with best-of selection will exceed 0.95 combined_score
# MECHANISM-1: The [5,4,5,4,4,4] layout scored only 0.9368 while [5,4,5,4,5,3] scored 0.9484; trying multiple seeds (different y-offsets and x-alignments) increases chance of finding better basin
# EXPECT-1: combined_score > 0.95
# RESULT-1: CONFIRMED (actual=0.9502888773130378)
# HYPOTHESIS-2: Using pure scalar loops for radii computation (no numpy broadcasting) is faster per call, allowing more optimization iterations within time budget
# MECHANISM-2: For n=26, scalar loops avoid numpy overhead of creating temporary arrays; this was confirmed by Program 1 achieving 2.499 with scalar loops vs 2.487 with vectorized
# EXPECT-2: sum_radii > 2.50
# RESULT-2: CONFIRMED (actual=2.5040111917198544)
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    
    best_sum = -1.0
    best_centers = None
    best_radii = None
    
    # Try multiple seed configurations
    seeds = []
    
    # Seed 0: Original Program 1 layout (proven best: 2.499)
    row_counts = [5, 4, 5, 4, 5, 3]
    r_est = 0.1
    rh = r_est * np.sqrt(3)
    c0 = []
    y = r_est
    for row_idx, nc in enumerate(row_counts):
        if row_idx % 2 == 0:
            xs = [(j + 0.5) / nc for j in range(nc)]
        else:
            xs = [(j + 1) / 5.0 for j in range(nc)]
        for x in xs:
            c0.append([x, y])
        y += rh
    seeds.append(np.array(c0[:n]))
    
    # Seed 1: Same layout but vertically centered
    total_h = 2 * r_est + 5 * rh
    y_off = (1.0 - total_h) / 2.0
    c1 = []
    y = r_est + y_off
    for row_idx, nc in enumerate(row_counts):
        if row_idx % 2 == 0:
            xs = [(j + 0.5) / nc for j in range(nc)]
        else:
            xs = [(j + 1) / 5.0 for j in range(nc)]
        for x in xs:
            c1.append([x, y])
        y += rh
    seeds.append(np.array(c1[:n]))
    
    # Seed 2: Slightly compressed vertically to give wall circles more room
    c2 = []
    rh2 = rh * 0.95
    y = r_est * 1.05
    for row_idx, nc in enumerate(row_counts):
        if row_idx % 2 == 0:
            xs = [(j + 0.5) / nc for j in range(nc)]
        else:
            xs = [(j + 1) / 5.0 for j in range(nc)]
        for x in xs:
            c2.append([x, y])
        y += rh2
    seeds.append(np.array(c2[:n]))
    
    for centers in seeds:
        # Clip to valid range
        centers = np.clip(centers, 0.001, 0.999)
        radii = _compute_radii(centers)
        
        # Multi-scale local optimization
        steps = [0.008, 0.005, 0.003, 0.002, 0.001, 0.0005]
        for step in steps:
            for _ in range(30):
                improved = False
                for i in range(n):
                    old_pos = centers[i].copy()
                    cur_sum = np.sum(radii)
                    for dx, dy in [(step,0),(-step,0),(0,step),(0,-step),
                                   (step*0.7,step*0.7),(step*0.7,-step*0.7),
                                   (-step*0.7,step*0.7),(-step*0.7,-step*0.7)]:
                        nx = old_pos[0] + dx
                        ny = old_pos[1] + dy
                        if nx < 0.001 or nx > 0.999 or ny < 0.001 or ny > 0.999:
                            continue
                        centers[i, 0] = nx
                        centers[i, 1] = ny
                        tr = _compute_radii(centers)
                        s = np.sum(tr)
                        if s > cur_sum + 1e-12:
                            radii = tr
                            cur_sum = s
                            improved = True
                            break
                        centers[i] = old_pos
                if not improved:
                    break
        
        s = float(np.sum(radii))
        if s > best_sum:
            best_sum = s
            best_centers = centers.copy()
            best_radii = radii.copy()
    
    return best_centers, best_radii, best_sum


def _compute_radii(centers):
    n = centers.shape[0]
    dists = np.zeros((n, n))
    for i in range(n):
        xi, yi = centers[i, 0], centers[i, 1]
        for j in range(i + 1, n):
            d = np.sqrt((xi - centers[j, 0])**2 + (yi - centers[j, 1])**2)
            dists[i, j] = d
            dists[j, i] = d
    
    wall = np.empty(n)
    for i in range(n):
        wall[i] = min(centers[i, 0], centers[i, 1], 1 - centers[i, 0], 1 - centers[i, 1])
    
    r = wall.copy()
    for _ in range(50):
        changed = False
        for i in range(n):
            mr = wall[i]
            for j in range(n):
                if i != j:
                    v = dists[i, j] - r[j]
                    if v < mr:
                        mr = v
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