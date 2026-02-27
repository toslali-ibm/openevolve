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
    # The (cols + 0.5) and (rows + 0.5) terms help distribute circles evenly
    # while leaving space near edges for their radii.
    dx = 1.0 / (cols + 0.5)
    dy = 1.0 / (rows + 0.5)
    
    for r in range(rows):
        for c in range(cols):
            x = (c + 0.5) * dx
            y = (r + 0.5) * dy
            # Stagger rows for a hexagonal pattern
            if r % 2 == 1:
                x += dx * 0.3 # Shift odd rows by a fraction of dx
            centers.append([x, y])
    
    # Add the 26th circle in a likely available corner or gap.
    # This position is a heuristic and can be further optimized by the refinement step.
    centers.append([0.9, 0.9])
    
    # Ensure we only take exactly 'n' circles
    centers = np.array(centers[:n])
    
    # 2. Iterative Force-Directed Refinement
    # Circles are treated as particles that repel each other and are contained by walls.
    # This process iteratively adjusts positions to maximize spacing.
    learning_rate = 0.02 # Step size for position adjustments
    num_refinement_iterations = 100 # Number of iterations for convergence

    for _ in range(num_refinement_iterations):
        # Calculate current max radii to determine "collision" distances for repulsion
        radii = compute_max_radii(centers)
        
        forces = np.zeros_like(centers)
        # Calculate repulsion forces between circles
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                target_dist = radii[i] + radii[j]
                
                # If circles are overlapping (or very close), apply a repulsive force.
                # The 1.05 factor creates a slight "pressure" to push circles
                # a bit further apart than just touching, aiming for tighter packing.
                if dist < target_dist * 1.05:
                    # Avoid division by zero if centers are identical
                    if dist < 1e-6: 
                        dist = 1e-6 
                    force_magnitude = (target_dist * 1.05 - dist) 
                    forces[i] += (diff / dist) * force_magnitude
                    forces[j] -= (diff / dist) * force_magnitude
        
        # Update center positions based on calculated forces
        centers += forces * learning_rate
        
        # Keep centers inside the unit square.
        # The 0.04 and 0.96 margins provide space for the circles' radii.
        centers = np.clip(centers, 0.04, 0.96)

    # 3. Final Radii Computation after refinement
    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)

    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Computes maximal radii for given centers such that circles do not overlap
    and stay within the unit square.
    This uses an iterative shrinkage method to resolve overlaps.
    """
    n = centers.shape[0]
    
    # Initialize radii with the maximum possible value based on distance to boundaries.
    # This ensures circles start within the square.
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    
    # Iteratively shrink radii to satisfy all pairwise non-overlap constraints.
    # Running multiple iterations ensures convergence for complex packing.
    num_shrink_iterations = 40 
    for _ in range(num_shrink_iterations):
        for i in range(n):
            for j in range(i + 1, n):
                d_vec = centers[i] - centers[j]
                dist = np.linalg.norm(d_vec)
                
                # If circles i and j overlap
                if radii[i] + radii[j] > dist:
                    # Calculate the amount of overlap
                    shrink_amount = (radii[i] + radii[j]) - dist
                    
                    # Shrink both radii proportionally to their current sizes.
                    # Add a small epsilon to the denominator to prevent division by zero
                    # if both radii are nearly zero (e.g., due to previous shrinking).
                    total_current_radii = radii[i] + radii[j]
                    if total_current_radii < 1e-9: # If both are effectively zero, no proportional shrink needed
                        continue
                    
                    ratio_i = radii[i] / total_current_radii
                    
                    radii[i] -= shrink_amount * ratio_i
                    radii[j] -= shrink_amount * (1 - ratio_i)
        
        # Ensure no radii become negative due to aggressive shrinking
        radii = np.maximum(0, radii)
        
    return radii

def run_packing():
    """Entry point for the evaluation system."""
    return construct_packing()

# EVOLVE-BLOCK-END