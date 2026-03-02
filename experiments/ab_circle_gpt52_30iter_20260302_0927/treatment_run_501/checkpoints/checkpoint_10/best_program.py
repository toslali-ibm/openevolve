# HYPOTHESIS-1: Using a known near-optimal packing layout with hexagonal grid and iterative radius optimization will dramatically increase sum_radii from 0.96 to above 2.4
# MECHANISM-1: Equal-radius circles on a hex grid with 5-6 rows efficiently tile the square; iterative shrinking resolves overlaps while maximizing each radius
# EXPECT-1: sum_radii > 2.4
# RESULT-1: CONFIRMED (actual=2.485155193807655)

# HYPOTHESIS-2: Iterating radius assignment multiple times (assigning each radius as half min distance to neighbors/walls) converges to a valid high-density packing
# MECHANISM-2: Greedy single-pass radius assignment is order-dependent; multiple passes allow radii to stabilize to consistent non-overlapping values
# EXPECT-2: validity > 0.9
# RESULT-2: CONFIRMED (actual=1.0)

# HYPOTHESIS-3: A hex grid arrangement of 26 equal-sized circles (~r=0.1) yields sum > 2.5 since 26*0.1 = 2.6
# MECHANISM-3: Hex packing with offset rows fits ~5x6 circles efficiently in unit square with radius ~1/(2*cols)
# EXPECT-3: combined_score > 0.9
# RESULT-3: CONFIRMED (actual=0.9431329008757705)

"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Use known best packing coordinates for 26 circles in unit square
    # Based on Packomania-style optimal packings
    # Try hex grid: 5 columns, rows alternate 5 and 6 circles
    # Layout: rows of 5,5,5,5,6 or similar to get 26
    
    # Best approach: use a refined grid layout
    # 26 circles: try 6 rows, alternating 4 and 5 per row: 5+4+5+4+5+3 = 26
    # Or 5+5+5+5+3+3 = 26
    # Let's try rows of: 5, 5, 5, 5, 3, 3 with hex offset
    
    centers = []
    
    # Try a more systematic approach: 6 columns arrangement
    # Rows: 5,4,5,4,4,4 = 26? No. 
    # 5,5,5,5,6 = 26? Yes: 4 rows of 5 + 1 row of 6
    # Actually let's do 5 rows of 5 + 1 extra = 26
    
    # Hex grid parameters
    ncols_even = 5  # even rows (0,2,4)
    ncols_odd = 4   # odd rows (1,3) offset
    # 3 even rows * 5 + 2 odd rows * 4 = 15 + 8 = 23, need 3 more
    # Let's do: rows 0-4 with 5,5,5,5,6 pattern
    
    # Actually, simplest good approach: uniform grid
    # 26 = 5*5 + 1, or let's use hex with rows: 5,5,5,5,3,3
    
    # Let me use a well-tuned hex grid
    nrows = 6
    row_counts = [5, 4, 5, 4, 5, 3]  # sum = 26
    
    # Radius estimate: for 5 columns, r ~ 1/10 = 0.1
    r_est = 0.1
    row_height = r_est * np.sqrt(3)  # hex packing vertical spacing = 2r * sqrt(3)/2
    
    # Total height needed: (nrows-1)*row_height + 2*r_est
    total_h = (nrows - 1) * row_height + 2 * r_est
    # Scale to fit in unit square
    scale = min(1.0 / total_h, 1.0 / (2 * r_est * 5))
    
    r = r_est * scale
    rh = row_height * scale
    
    y_start = r
    
    for row_idx, nc in enumerate(row_counts):
        y = y_start + row_idx * rh
        if row_idx % 2 == 0:
            # No offset
            x_spacing = 1.0 / nc if nc > 0 else 1.0
            for j in range(nc):
                x = x_spacing * (j + 0.5)
                centers.append([x, y])
        else:
            # Offset by half spacing of even rows
            x_spacing_even = 1.0 / 5  # even rows have 5
            x_spacing = 1.0 / nc if nc > 0 else 1.0
            for j in range(nc):
                x = x_spacing_even * (j + 1)
                centers.append([x, y])
    
    centers = np.array(centers[:n])
    
    # Now optimize: iteratively compute radii
    radii = compute_max_radii_iterative(centers)
    
    # Local optimization: nudge centers to increase radii
    for iteration in range(200):
        improved = False
        for i in range(n):
            best_r = radii[i]
            best_pos = centers[i].copy()
            for dx, dy in [(0.002,0),(-0.002,0),(0,0.002),(0,-0.002),
                           (0.001,0.001),(0.001,-0.001),(-0.001,0.001),(-0.001,-0.001)]:
                new_pos = centers[i] + np.array([dx, dy])
                if new_pos[0] < 0.001 or new_pos[0] > 0.999 or new_pos[1] < 0.001 or new_pos[1] > 0.999:
                    continue
                centers[i] = new_pos
                test_radii = compute_max_radii_iterative(centers)
                if np.sum(test_radii) > np.sum(radii):
                    radii = test_radii
                    best_pos = new_pos.copy()
                    improved = True
                    break
                else:
                    centers[i] = best_pos
        if not improved:
            break
    
    return centers, radii, float(np.sum(radii))


def compute_max_radii_iterative(centers):
    n = centers.shape[0]
    
    # Compute all pairwise distances
    dists = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            d = np.sqrt(np.sum((centers[i] - centers[j])**2))
            dists[i, j] = d
            dists[j, i] = d
    
    # Wall distances
    wall_dist = np.array([min(c[0], c[1], 1-c[0], 1-c[1]) for c in centers])
    
    # Start with wall-limited radii
    radii = wall_dist.copy()
    
    # Iteratively reduce radii to resolve overlaps
    for iteration in range(50):
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