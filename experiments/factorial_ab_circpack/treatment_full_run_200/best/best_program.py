# EVOLVE-BLOCK-START
# HYPOTHESIS-1: A hexagonal-like packing is more efficient than concentric rings for n=26.
# MECHANISM-1: Hexagonal arrangements maximize local density by ensuring most circles 
#   have 6 neighbors, reducing empty space compared to polar or square grid layouts.
# EXPECT-1: sum_radii > 1.8
# HYPOTHESIS-2: Iterative force-directed relaxation with radius equalization improves sum of radii.
# MECHANISM-2: By treating overlaps as repulsive forces and iteratively adjusting positions 
#   while keeping radii balanced, the packing converges to a more uniform and dense state.
# EXPECT-2: target_ratio > 0.6

import numpy as np

def construct_packing():
    """
    Constructs a 26-circle packing using a relaxed hexagonal-inspired grid.
    """
    n = 26
    # Create a 5x5 grid as a base (25 circles)
    side = 5
    x = np.linspace(0.1, 0.9, side)
    y = np.linspace(0.1, 0.9, side)
    xx, yy = np.meshgrid(x, y)
    centers = np.vstack([xx.ravel(), yy.ravel()]).T
    
    # Add the 26th circle at the center with a small offset
    extra_circle = np.array([[0.51, 0.49]])
    centers = np.vstack([centers, extra_circle])
    
    # Parameters for relaxation
    n_iterations = 100
    learning_rate = 0.02
    target_radius = 1.0 / (2 * np.sqrt(n)) # Heuristic starting point
    
    for _ in range(n_iterations):
        forces = np.zeros_like(centers)
        for i in range(n):
            # Boundary forces
            for dim in range(2):
                if centers[i, dim] < target_radius:
                    forces[i, dim] += (target_radius - centers[i, dim])
                elif centers[i, dim] > 1 - target_radius:
                    forces[i, dim] -= (centers[i, dim] - (1 - target_radius))
            
            # Inter-circle forces
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                min_dist = 2 * target_radius
                if dist < min_dist:
                    # Push circles apart if they overlap
                    push = (min_dist - dist) * 0.5
                    direction = diff / (dist + 1e-9)
                    forces[i] += direction * push
                    forces[j] -= direction * push
        
        centers += forces * learning_rate
        centers = np.clip(centers, 0.0, 1.0)

    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)
    
    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Computes radii by resolving overlaps and boundary constraints.
    Attempts to keep radii relatively uniform to maximize the sum.
    """
    n = centers.shape[0]
    # Initial radii: distance to nearest wall
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    
    # Iteratively shrink radii to resolve overlaps
    # We use a fair shrinkage to maximize the sum (sum is max when radii are equal)
    for _ in range(15):
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > dist:
                    # Adjust both radii to touch at the midpoint relative to current size
                    total = radii[i] + radii[j]
                    radii[i] = (radii[i] / total) * dist
                    radii[j] = (radii[j] / total) * dist
                    
    return radii

def run_packing():
    """Entry point for the evaluator"""
    return construct_packing()

# EVOLVE-BLOCK-END