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
    centers = []
    
    # Define a grid that fills the square efficiently
    # For n=26, a 5-row pattern with alternating counts is effective.
    # [5, 6, 5, 6, 4] sums to 26. This setup from Program 1 proved effective.
    counts = [5, 6, 5, 6, 4] 
    
    # Vertical spacing for rows. Program 1 used 1.0 / 5.2.
    # This value seems to be tuned for the number of rows and desired density.
    dy_spacing_factor = 5.2 
    dy = 1.0 / dy_spacing_factor
    
    # Initial y-offset. Program 1 used 0.1.
    # Let's keep this as it's part of the empirically tuned grid.
    y_initial_offset = 0.1
    
    for r_idx, row_count in enumerate(counts):
        y = y_initial_offset + r_idx * dy
        
        # Horizontal spacing and staggering for hexagonal pattern.
        # These values from Program 1 implicitly handle centering and margins.
        dx = 1.0 / (row_count + 0.5)
        offset = dx * 0.5 if r_idx % 2 == 1 else dx * 0.25 # Staggering
        
        for c_idx in range(row_count):
            x = offset + c_idx * dx
            centers.append([x, y])
            
    centers = np.array(centers[:n]) # Ensure exactly n circles
    
    # --- Iterative Force-Directed Relaxation ---
    # This spreads circles out to maximize the minimum distance between them
    # and the boundaries, which indirectly maximizes the sum of radii.
    num_relaxation_iterations = 100 # Increased for better convergence
    
    # Target diameter for repulsion. This is a crucial parameter.
    # Based on AlphaEvolve target (2.635 / 26 = ~0.1013 average radius).
    target_diameter_repulsion = 0.20 
    
    # Strength of the repulsion force.
    repulsion_strength = 0.2 
    
    # Boundary clipping margin. Centers are kept within [margin, 1-margin].
    # This implicitly sets a minimum possible radius for all circles.
    # Consistent with target_diameter_repulsion / 2.
    boundary_clip_margin = 0.1 
    
    for it in range(num_relaxation_iterations):
        # Calculate all-pairs distances and apply repulsion
        forces = np.zeros_like(centers)
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                if dist < target_diameter_repulsion:
                    # Push circles apart if they are too close
                    # Force direction is (diff / dist), magnitude is proportional to overlap
                    force_magnitude = (target_diameter_repulsion - dist) * repulsion_strength
                    force = (diff / (dist + 1e-9)) * force_magnitude
                    forces[i] += force
                    forces[j] -= force # Apply opposite force to the other circle
        
        centers += forces
        
        # Boundary constraints: clip centers to keep them within the square, respecting margin
        centers[:, 0] = np.clip(centers[:, 0], boundary_clip_margin, 1.0 - boundary_clip_margin)
        centers[:, 1] = np.clip(centers[:, 1], boundary_clip_margin, 1.0 - boundary_clip_margin)

    # --- Compute maximum valid radii ---
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
    # This ensures no circle initially extends beyond the square.
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    
    # Iteratively resolve overlaps to satisfy r_i + r_j <= dist(i, j)
    # This greedy adjustment is stable and ensures validity while maximizing sum of radii.
    num_radii_resolution_iterations = 60 # Increased for better convergence
    for _ in range(num_radii_resolution_iterations):
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > d:
                    # If overlap, shrink both radii proportionally to their current size
                    # This helps maintain a balanced distribution of radii
                    shrinkage_factor = d / (radii[i] + radii[j])
                    radii[i] *= shrinkage_factor
                    radii[j] *= shrinkage_factor
    return radii

def run_packing():
    """Entry point for the evaluation script"""
    return construct_packing()

# EVOLVE-BLOCK-END