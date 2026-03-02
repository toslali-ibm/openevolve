# EVOLVE-BLOCK-START
"""
Constructor-based circle packing for n=26 circles.
Uses a dense hexagonal grid base with iterative force-directed refinement 
and a proportional radius expansion to maximize the sum of radii.
"""
import numpy as np

def construct_packing():
    """
    Constructs a 26-circle packing using a staggered hexagonal-like grid.
    Refines positions using a repulsion model to maximize space utilization.
    """
    n = 26
    # 1. Initial Placement: Hexagonal grid (approx 5x5 or 5x6)
    centers = []
    rows = 5
    cols = 5
    # Use slightly smaller spacing to allow the 26th circle to fit
    dx = 1.0 / (cols + 0.5)
    dy = 1.0 / (rows + 0.5)
    
    for r in range(rows):
        for c in range(cols):
            x = (c + 0.5) * dx
            y = (r + 0.5) * dy
            if r % 2 == 1:
                x += dx * 0.3
            centers.append([x, y])
    
    # Add the 26th circle in the largest remaining gap
    centers.append([0.9, 0.9])
    centers = np.array(centers[:n])
    
    # 2. Iterative Force-Directed Refinement
    # We treat circles as particles that repel each other and are contained by walls
    learning_rate = 0.02
    for _ in range(100):
        # Calculate current max radii to determine "collision"
        radii = compute_max_radii(centers)
        
        forces = np.zeros_like(centers)
        # Repulsion between circles
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                target_dist = radii[i] + radii[j]
                if dist < target_dist * 1.05: # Slight pressure
                    force = (diff / (dist + 1e-6)) * (target_dist * 1.05 - dist)
                    forces[i] += force
                    forces[j] -= force
        
        centers += forces * learning_rate
        # Keep centers inside the unit square with margin for a typical radius
        centers = np.clip(centers, 0.04, 0.96)

    # 3. Final Radii Computation
    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)

    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Computes maximal radii for given centers such that circles do not overlap
    and stay within the unit square.
    """
    n = centers.shape[0]
    # Initialize with distance to boundaries
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    
    # Solve constraints: r_i + r_j <= dist_ij
    # Iterative shrinkage to satisfy all pairwise constraints
    for _ in range(40):
        for i in range(n):
            for j in range(i + 1, n):
                d_vec = centers[i] - centers[j]
                dist = np.linalg.norm(d_vec)
                if radii[i] + radii[j] > dist:
                    # Shrink both proportionally
                    shrink = (radii[i] + radii[j]) - dist
                    ratio = radii[i] / (radii[i] + radii[j])
                    radii[i] -= shrink * ratio
                    radii[j] -= shrink * (1 - ratio)
    return radii

def run_packing():
    """Entry point for the evaluation system."""
    return construct_packing()

# EVOLVE-BLOCK-END