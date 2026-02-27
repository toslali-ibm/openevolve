# EVOLVE-BLOCK-START
"""
Constructor-based circle packing for n=26 circles.
Uses a dense hexagonal-inspired grid with iterative relaxation 
and a proportional radius solver to maximize the sum of radii.
"""
import numpy as np

def construct_packing():
    """
    Constructs an arrangement of 26 circles in a unit square.
    """
    n = 26
    # Create a dense staggered grid (approx 5x5 + extras)
    centers = []
    rows = 5
    cols = 5
    
    # Generate a slightly compressed hexagonal grid
    for r in range(rows):
        for c in range(cols):
            x = (c + 0.5 * (r % 2)) / (cols - 0.5)
            y = r / (rows - 1)
            centers.append([x, y])
            
    # Add the 26th circle in a gap or center
    centers.append([0.5, 0.5])
    centers = np.array(centers[:n])
    
    # Map to [0.1, 0.9] to ensure they start inside
    centers = 0.1 + 0.8 * centers

    # Iterative relaxation (Force-directed placement)
    # This pushes circles apart to create more uniform spacing
    for _ in range(100):
        for i in range(n):
            # Boundary repulsion
            centers[i] = np.clip(centers[i], 0.05, 0.95)
            
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                target = 0.18 # Approximate ideal diameter
                if dist < target:
                    # Push away
                    push = (target - dist) * 0.2
                    move = (diff / (dist + 1e-9)) * push
                    centers[i] += move
                    centers[j] -= move
                    
    # Final clip to ensure validity
    centers = np.clip(centers, 0.01, 0.99)
    
    # Compute optimized radii
    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)

    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Computes maximum possible radii for the given centers.
    Uses a proportional balancing approach to ensure no overlaps.
    """
    n = centers.shape[0]
    # Initialize radii as distance to nearest wall
    radii = np.min(np.hstack([centers, 1 - centers]), axis=1)
    
    # Iteratively adjust radii to satisfy r_i + r_j <= dist_ij
    # We use multiple passes to balance the 'shrinkage' across circles
    for _ in range(20):
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > d:
                    # Adjust radii proportionally to their current size
                    # to prevent one circle from becoming zero
                    total_r = radii[i] + radii[j]
                    radii[i] = d * (radii[i] / total_r)
                    radii[j] = d * (radii[j] / total_r)
                    
    return radii

def run_packing():
    """Required entry point for the evaluator."""
    return construct_packing()

# EVOLVE-BLOCK-END