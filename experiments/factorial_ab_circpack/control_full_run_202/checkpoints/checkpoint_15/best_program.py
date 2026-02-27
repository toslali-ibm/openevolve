# EVOLVE-BLOCK-START
"""
Constructor-based circle packing for n=26 circles.
This program aims to maximize the sum of radii by using a hexagonal-inspired grid
for initial placement, followed by an iterative force-directed relaxation
of circle centers, and a robust proportional radius solver.
"""
import numpy as np

def construct_packing():
    """
    Constructs an arrangement of 26 circles in a unit square.
    The process involves:
    1. Initial placement of centers in a staggered, hexagonal-like grid.
    2. Iterative relaxation of centers using repulsion forces to optimize spacing.
    3. A proportional radius solver to determine maximal non-overlapping radii.
    """
    n = 26
    centers = []
    
    # 1. Initial Placement: Generate a staggered grid for 25 circles
    # This hexagonal-inspired pattern helps achieve dense packing.
    rows = 5
    cols = 5 
    
    for r in range(rows):
        for c in range(cols):
            # X-coordinate is staggered based on row parity for hexagonal effect
            x = (c + 0.5 * (r % 2)) / (cols - 0.5) 
            y = r / (rows - 1) 
            centers.append([x, y])
            
    # Add the 26th circle at the center of the square.
    # This is a common strategy for odd counts or to fill central voids.
    centers.append([0.5, 0.5])
    centers = np.array(centers[:n]) # Ensure exactly n circles are used

    # Map initial center positions from [0,1] to [0.1, 0.9].
    # This provides an initial buffer from the container walls, allowing for
    # positive initial radii and preventing circles from being 'stuck' on edges.
    centers = 0.1 + 0.8 * centers
    
    # --- 2. Iterative Relaxation (Force-Directed Placement) ---
    # This process dynamically adjusts circle centers to reduce overlaps and
    # distribute circles more evenly, pushing them apart while respecting boundaries.
    
    # Compute initial radii. This is crucial for accurate boundary clipping
    # in the relaxation loop and for estimating circle sizes for repulsion.
    radii = compute_max_radii(centers) 
    
    num_relaxation_steps = 200 # Number of iterations for center adjustments
    relaxation_strength = 0.3 # How strongly circles are pushed apart per step
    # An approximate ideal diameter for circles, used as a target for repulsion.
    # For n=26 in a 1x1 square, average diameter is roughly 0.2.
    target_dist_factor = 0.2 
    
    for step in range(num_relaxation_steps):
        # Apply boundary repulsion: Ensure circles stay within the unit square.
        # The clip uses the current radius of each circle, preventing it from crossing walls.
        for i in range(n):
            centers[i, 0] = np.clip(centers[i, 0], radii[i], 1 - radii[i])
            centers[i, 1] = np.clip(centers[i, 1], radii[i], 1 - radii[i])

        # Apply inter-circle repulsion: Push overlapping or too-close circles apart.
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                
                # If circles are closer than the target distance, push them apart.
                if dist < target_dist_factor:
                    # Calculate how much to push. The further they are into overlap, the stronger the push.
                    push_amount = (target_dist_factor - dist) * relaxation_strength
                    
                    # Normalize the difference vector and apply push.
                    # Avoid division by zero if centers are identical (highly unlikely after initial setup).
                    if dist > 1e-9: 
                        move = (diff / dist) * push_amount
                        centers[i] += move
                        centers[j] -= move
        
        # Periodically recompute radii:
        # Recomputing radii during relaxation makes the force-directed layout more accurate,
        # as the repulsion forces can better adapt to the actual (changing) circle sizes.
        # This is a trade-off between computational cost and accuracy.
        if step % 10 == 0 or step == num_relaxation_steps - 1: # Recompute every 10 steps or at the very end
             radii = compute_max_radii(centers)
             # Immediately re-clip centers after radii update to respect new sizes.
             # This prevents circles from moving outside boundaries due to radius changes.
             for k in range(n):
                 centers[k, 0] = np.clip(centers[k, 0], radii[k], 1 - radii[k])
                 centers[k, 1] = np.clip(centers[k, 1], radii[k], 1 - radii[k])

    # 3. Final Computation of Optimized Radii:
    # After all center adjustments are complete, a final pass ensures the returned
    # radii are the maximal possible for the final center configuration.
    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)

    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Computes maximum possible radii for the given centers such that no circles overlap
    and all circles stay within the unit square.
    Uses an iterative proportional shrinking method to resolve overlaps.
    """
    n = centers.shape[0]
    
    # Initialize radii: Each circle's radius is limited by its distance to the nearest wall.
    # This ensures all circles are initially within the container boundaries.
    radii = np.min(np.hstack([centers, 1 - centers]), axis=1)
    
    num_radius_iterations = 75 # Number of iterations to resolve overlaps
    
    for _ in range(num_radius_iterations):
        for i in range(n):
            # Explicitly ensure radius does not exceed boundary based on current center position.
            # This handles cases where a center might have moved very close to a wall.
            radii[i] = min(radii[i], centers[i,0], 1-centers[i,0], centers[i,1], 1-centers[i,1])
            
            for j in range(i + 1, n):
                d = np.linalg.norm(centers[i] - centers[j])
                
                # If the sum of current radii is greater than the distance between centers, they overlap.
                if radii[i] + radii[j] > d:
                    # Adjust radii proportionally to their current sizes.
                    # This method distributes the necessary shrinkage based on existing radii,
                    # which tends to be more equitable and preserve larger circles better
                    # compared to shrinking both equally.
                    total_r_before_adjust = radii[i] + radii[j]
                    
                    # Handle cases where total_r_before_adjust is very small to avoid division by zero.
                    if total_r_before_adjust < 1e-9: 
                        # If both are tiny, assign half the distance to each to resolve overlap minimally.
                        radii[i] = d / 2
                        radii[j] = d / 2
                    else:
                        # Proportional adjustment based on the required reduction.
                        radii[i] = d * (radii[i] / total_r_before_adjust)
                        radii[j] = d * (radii[j] / total_r_before_adjust)
        
        # Ensure all radii remain positive, with a very small minimum value.
        # This prevents circles from disappearing or having zero area in the output.
        radii = np.maximum(radii, 1e-7) 

    return radii

def run_packing():
    """Required entry point for the evaluator."""
    return construct_packing()

# EVOLVE-BLOCK-END