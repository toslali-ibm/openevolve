# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using a hexagonal-patterned initialization will significantly improve sum_radii.
# MECHANISM-1: Hexagonal packing is theoretically denser than square packing. Starting with a more efficient initial layout minimizes wasted space, providing a better foundation for the relaxation algorithm to maximize radii.
# EXPECT-1: sum_radii > 1.8

# HYPOTHESIS-2: Adopting a more robust force-directed relaxation, based on estimated optimal radii, will increase target_ratio.
# MECHANISM-2: By using a `target_r` (estimated average radius) to define both boundary repulsion and inter-circle repulsion thresholds, the relaxation process guides circles to a more balanced and optimal spacing, leading to a higher overall sum of radii.
# EXPECT-2: target_ratio > 0.6

# HYPOTHESIS-3: Increasing the number of relaxation steps and adjusting the learning rate will allow for better convergence to a local optimum.
# MECHANISM-3: More steps provide the system with more opportunities to adjust positions and escape minor local minima. A carefully chosen learning rate prevents overshooting while ensuring sufficient movement.
# EXPECT-3: combined_score > 0.65

import numpy as np

def construct_packing():
    """
    Constructs an arrangement of 26 circles using a hexagonal initialization
    and a force-directed relaxation algorithm.
    """
    n = 26
    
    # HYPOTHESIS-1 implementation: Hexagonal initialization
    # Initialize with a slightly jittered hexagonal-ish grid
    # For 26 circles, use a 5x6 grid and take the first 26 circles.
    cols = 5
    rows = 6 
    
    centers = []
    for i in range(n):
        r_idx = i // cols
        c_idx = i % cols
        # Offset every other row for hexagonal structure
        x = (c_idx + 0.5 * (r_idx % 2)) / (cols)
        y = r_idx / (rows - 1)
        centers.append([x, y])
    
    centers = np.array(centers)
    # Scale to fit better initially, leaving a small margin from the edges.
    # Adjusted scaling slightly to give relaxation more room.
    centers = 0.08 + 0.84 * centers 
    
    # Relaxation parameters
    # HYPOTHESIS-3 implementation: Increased steps and adjusted learning rate
    steps = 200 # Increased from 100 for better convergence
    learning_rate = 0.015 # Slightly adjusted from 0.02 for stability with more steps
    
    # HYPOTHESIS-2 implementation: Robust force-directed relaxation
    for _ in range(steps):
        forces = np.zeros_like(centers)
        
        # Estimate a target radius for forces. This helps guide the repulsion.
        # This is an average radius if all circles were equal and packed.
        # A slightly larger target radius for forces might help prevent premature compaction,
        # allowing for overall larger final radii.
        target_r_est = (1.0 / (2 * np.sqrt(n))) * 1.1 
        
        for i in range(n):
            # 1. Boundary forces (keep inside [r, 1-r])
            # Push away from boundaries if too close (closer than target_r_est)
            for dim in range(2):
                if centers[i, dim] < target_r_est:
                    forces[i, dim] += (target_r_est - centers[i, dim]) * 2 # Stronger push from boundaries
                elif centers[i, dim] > 1 - target_r_est:
                    forces[i, dim] -= (centers[i, dim] - (1 - target_r_est)) * 2
            
            # 2. Inter-circle repulsion
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                
                # Minimum distance for two circles of target_r_est not to overlap
                min_dist_for_repulsion = 2 * target_r_est
                
                if dist < min_dist_for_repulsion:
                    # Push away proportional to overlap. Force strength increases with overlap.
                    push_magnitude = (min_dist_for_repulsion - dist) / min_dist_for_repulsion
                    push = push_magnitude * (diff / (dist + 1e-9)) # Add epsilon for numerical stability
                    forces[i] += push
                    forces[j] -= push
                    
        # Apply forces and clip centers to ensure they stay within [0,1]
        centers += forces * learning_rate
        centers = np.clip(centers, 0.0, 1.0) # Ensure centers are within the unit square

    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)
    
    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Compute max radii such that circles are in [0,1]^2 and don't overlap.
    Uses a greedy proportional shrinkage.
    """
    n = centers.shape[0]
    # Initialize radii to boundary distance
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    
    # Limit by neighbors
    # We solve this by ensuring r_i + r_j <= dist_ij
    # Iterative approach to stabilize the radii sum.
    # Increased iterations for potentially better convergence of radii.
    for _ in range(20): 
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.linalg.norm(centers[i] - centers[j])
                
                # Handle cases where centers are virtually identical to avoid division by zero
                if dist < 1e-9: 
                    radii[i] = 0.0
                    radii[j] = 0.0
                    continue

                if radii[i] + radii[j] > dist:
                    # Shrink both proportionally to their current sizes.
                    # This method aims to maintain the relative size of overlapping circles.
                    shrinkage_factor = dist / (radii[i] + radii[j])
                    radii[i] *= shrinkage_factor
                    radii[j] *= shrinkage_factor
    
    # Ensure no radii are negative due to floating point inaccuracies
    radii = np.maximum(radii, 0.0)
    return radii

def run_packing():
    """Required entry point for the evaluator."""
    return construct_packing()

# EVOLVE-BLOCK-END