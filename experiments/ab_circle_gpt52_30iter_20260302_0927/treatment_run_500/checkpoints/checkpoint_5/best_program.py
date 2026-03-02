# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using known optimal/near-optimal coordinates for 26 equal circles in a square will dramatically improve sum_radii
# MECHANISM-1: The Packomania database has verified optimal packings; using those coordinates ensures circles are well-separated and space is used efficiently
# EXPECT-1: sum_radii > 2.4
# RESULT-1: REFUTED (actual=2.2645022623955384)
# HYPOTHESIS-2: Iterative force-based relaxation after initial placement will push circles apart and allow larger radii
# MECHANISM-2: Repulsive forces between overlapping circles and attractive forces toward center create equilibrium configurations with better space utilization
# EXPECT-2: combined_score > 0.9
# RESULT-2: REFUTED (actual=0.8593936479679464)
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    n = 26
    # Use a hexagonal-style grid packing optimized for 26 circles
    # Layout: rows of 5,5,5,5,3,3 or similar hex patterns
    # Try 6 rows in hex pattern: 5,5,5,5,3,3 = 26
    
    # Best known packing for 26 equal circles has r ≈ 0.09609 (diameter ratio)
    # but we want to maximize SUM of radii, not necessarily equal circles.
    
    # Strategy: place circles on a good grid, then use optimization
    # to find best radii assignment
    
    # Start with known good positions from hexagonal packing
    centers_list = []
    
    # Hex grid with rows offset
    # For 26 circles, use rows: 5, 6, 5, 6, 4 (= 26)
    row_counts = [5, 6, 5, 6, 4]
    n_rows = len(row_counts)
    
    # Vertical spacing
    total_h = 1.0
    dy = total_h / (n_rows + 1)
    
    for row_idx, count in enumerate(row_counts):
        y = dy * (row_idx + 1)
        dx = 1.0 / (count + 1)
        offset = 0.0
        for col_idx in range(count):
            x = dx * (col_idx + 1)
            centers_list.append([x, y])
    
    centers = np.array(centers_list[:n])
    
    # Now run force-directed optimization to improve positions
    centers = optimize_positions(centers, iterations=500)
    
    # Compute radii using LP-like approach (equal radii first, then optimize)
    radii = compute_optimal_radii(centers)
    
    sum_radii = np.sum(radii)
    return centers, radii, sum_radii


def optimize_positions(centers, iterations=500):
    """Force-directed optimization to spread circles apart."""
    n = len(centers)
    lr = 0.001
    
    for it in range(iterations):
        forces = np.zeros_like(centers)
        
        # Repulsive forces between circles
        for i in range(n):
            for j in range(i+1, n):
                diff = centers[i] - centers[j]
                dist = np.sqrt(np.sum(diff**2))
                if dist < 1e-10:
                    diff = np.random.randn(2) * 0.001
                    dist = np.sqrt(np.sum(diff**2))
                # Repulsive force inversely proportional to distance
                force_mag = 1.0 / (dist * dist)
                force_dir = diff / dist
                forces[i] += force_dir * force_mag
                forces[j] -= force_dir * force_mag
        
        # Wall forces - push away from boundaries
        for i in range(n):
            x, y = centers[i]
            wall_strength = 0.5
            forces[i, 0] += wall_strength / max(x, 0.001)**2
            forces[i, 0] -= wall_strength / max(1-x, 0.001)**2
            forces[i, 1] += wall_strength / max(y, 0.001)**2
            forces[i, 1] -= wall_strength / max(1-y, 0.001)**2
        
        # Normalize and apply
        max_force = np.max(np.sqrt(np.sum(forces**2, axis=1)))
        if max_force > 0:
            centers += forces / max_force * lr
        
        # Clip to stay in bounds
        centers = np.clip(centers, 0.005, 0.995)
        
        # Decay learning rate
        lr *= 0.998
    
    return centers


def compute_optimal_radii(centers):
    """Compute radii that maximize sum using iterative approach."""
    n = len(centers)
    
    # Compute pairwise distances
    dists = np.zeros((n, n))
    for i in range(n):
        for j in range(i+1, n):
            d = np.sqrt(np.sum((centers[i] - centers[j])**2))
            dists[i, j] = d
            dists[j, i] = d
    
    # Wall distances
    wall_dist = np.zeros(n)
    for i in range(n):
        x, y = centers[i]
        wall_dist[i] = min(x, y, 1-x, 1-y)
    
    # Initialize radii to wall distance limits
    radii = wall_dist.copy()
    
    # Iteratively adjust - grow radii as much as possible
    for iteration in range(100):
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
    
    # Try to grow each circle greedily in order of potential gain
    for _ in range(50):
        for i in np.argsort(-wall_dist):  # Start with circles that have most room
            max_r = wall_dist[i]
            for j in range(n):
                if i != j:
                    max_r = min(max_r, dists[i, j] - radii[j])
            radii[i] = max(max_r, 0.0)
    
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