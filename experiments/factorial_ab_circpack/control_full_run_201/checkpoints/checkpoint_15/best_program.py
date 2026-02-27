# EVOLVE-BLOCK-START
"""
Constructor-based circle packing for n=26 circles.
Uses a dense hexagonal layering strategy with iterative relaxation 
to maximize the sum of radii in a unit square.
"""
import numpy as np

def construct_packing():
    """
    Constructs a packing of 26 circles using a hexagonal grid 
    arrangement optimized for a unit square.
    """
    n = 26
    # For n=26, we aim for a roughly 5x5 grid with offsets.
    # Hexagonal packing is denser than square packing.
    centers = []
    
    # Define a grid that fills the square efficiently
    # 5 rows, with alternating counts to reach 26
    counts = [5, 6, 5, 6, 4] 
    dy = 1.0 / 5.2
    for r, row_count in enumerate(counts):
        y = 0.1 + r * dy
        dx = 1.0 / (row_count + 0.5)
        offset = dx * 0.5 if r % 2 == 1 else dx * 0.25
        for c in range(row_count):
            x = offset + c * dx
            centers.append([x, y])
            
    centers = np.array(centers[:n])
    
    # Iterative Force-Directed Relaxation
    # This spreads circles out to maximize the minimum distance between them
    # and the boundaries, which indirectly maximizes the sum of radii.
    num_iterations = 60
    for it in range(num_iterations):
        # Calculate all-pairs distances
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                target = 0.19 # Approximate optimal diameter for n=26
                if dist < target:
                    # Push circles apart if they are too close
                    push = (target - dist) * 0.2 * (diff / (dist + 1e-9))
                    centers[i] += push
                    centers[j] -= push
        
        # Boundary constraints: keep centers away from edges
        # The margin 0.08 is a heuristic for the radius
        centers[:, 0] = np.clip(centers[:, 0], 0.08, 0.92)
        centers[:, 1] = np.clip(centers[:, 1], 0.08, 0.92)

    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)
    
    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Computes maximum radii for centers such that they stay within the 
    unit square and do not overlap.
    """
    n = centers.shape[0]
    # Initialize radii with distance to closest boundary
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    
    # Iteratively resolve overlaps to satisfy r_i + r_j <= dist(i, j)
    # This greedy adjustment is stable and ensures validity.
    for _ in range(30):
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > d:
                    # Adjust radii proportionally to current size
                    # to maintain a balanced distribution
                    shrinkage = d / (radii[i] + radii[j])
                    radii[i] *= shrinkage
                    radii[j] *= shrinkage
    return radii

def run_packing():
    """Entry point for the evaluation script"""
    return construct_packing()

# EVOLVE-BLOCK-END