# EVOLVE-BLOCK-START
# HYPOTHESIS-1: A centrally clustered hexagonal initialization for 26 circles improves sum_radii.
# MECHANISM-1: Generating a larger hexagonal grid and selecting the 26 most central points creates a more balanced and dense initial configuration, reducing initial overlaps and providing a better starting point for relaxation compared to arbitrary grid slicing or layered construction.
# EXPECT-1: sum_radii > 1.6

# HYPOTHESIS-2: Increased relaxation iterations with linear spring forces and a slightly reduced learning rate improves convergence and final sum_radii.
# MECHANISM-2: More iterations allow the system to thoroughly explore the local energy landscape, while the linear spring forces (both boundary and inter-circle) provide stable and proportional adjustments, and a smaller learning rate prevents oscillations, leading to a more optimal, higher-density packing.
# EXPECT-2: target_ratio > 0.65

import numpy as np

def construct_packing():
    """
    Constructs an arrangement of 26 circles using a centrally-clustered hexagonal
    initialization and a force-directed relaxation algorithm.
    """
    n = 26
    
    # 1. Initial Placement: Centrally-clustered hexagonal grid
    # Generate a larger hexagonal grid and select the 26 most central points.
    
    # Approximate spacing based on typical circle packing density.
    # For n=26, a rough average radius is ~0.1, so center-to-center spacing ~0.2.
    base_spacing = 0.19 # Adjusted slightly to encourage initial overlap and outward push

    # Create a grid large enough to contain 26 circles centrally
    num_x_cells = 7 # Number of cells horizontally
    num_y_cells = 6 # Number of cells vertically
    
    all_grid_centers = []
    for r_idx in range(num_y_cells):
        # Calculate y-coordinate, accounting for hexagonal vertical spacing
        y = (r_idx + 0.5) * base_spacing * np.sqrt(3) / 2
        # Offset x-coordinate for every other row to create hexagonal stagger
        x_offset = (r_idx % 2) * base_spacing / 2
        for c_idx in range(num_x_cells):
            x = (c_idx + 0.5) * base_spacing + x_offset
            all_grid_centers.append([x, y])
            
    all_grid_centers = np.array(all_grid_centers)
    
    # Center and scale the generated grid to fit within [0.1, 0.9] of the unit square
    min_coords = all_grid_centers.min(axis=0)
    max_coords = all_grid_centers.max(axis=0)
    
    # Calculate scale factor to fit within a 0.8x0.8 region (0.1 to 0.9)
    # This helps keep circles from being too close to the boundary initially
    range_coords = max_coords - min_coords
    if range_coords[0] == 0 or range_coords[1] == 0: # Avoid division by zero for degenerate grids
        scale_factor = 1.0
    else:
        scale_factor = 0.8 / max(range_coords[0], range_coords[1])
    
    scaled_centered_grid = (all_grid_centers - min_coords) * scale_factor + 0.1
    
    # Select the 'n' most central circles from the scaled grid
    center_point = np.array([0.5, 0.5])
    distances_to_center = np.linalg.norm(scaled_centered_grid - center_point, axis=1)
    sorted_indices = np.argsort(distances_to_center)
    centers = scaled_centered_grid[sorted_indices[:n]]

    # 2. Force-directed relaxation
    steps = 250 # Increased iterations for better convergence
    learning_rate = 0.015 # Slightly reduced for stability

    for _ in range(steps):
        forces = np.zeros_like(centers)
        
        # Estimate an average radius for force calculations.
        # This helps in defining ideal separation and boundary distances.
        current_target_r = 1.0 / (2 * np.sqrt(n)) 

        # Apply boundary forces
        for i in range(n):
            for dim in range(2):
                # Linear spring force pushing away from boundaries if center is too close
                if centers[i, dim] < current_target_r:
                    forces[i, dim] += (current_target_r - centers[i, dim]) * 1.0
                elif centers[i, dim] > 1 - current_target_r:
                    forces[i, dim] -= (centers[i, dim] - (1 - current_target_r)) * 1.0
            
        # Apply inter-circle repulsion forces
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                
                # Ideal minimum distance between centers for non-overlap
                min_dist_ideal = 2 * current_target_r 
                
                if dist < min_dist_ideal:
                    # Linear force proportional to the degree of overlap
                    # Normalized overlap: 0 if no overlap, 1 if centers coincide
                    push_magnitude = (min_dist_ideal - dist) / min_dist_ideal
                    # Apply force in direction of 'diff' (away from each other)
                    # Divide by (dist + 1e-6) to get unit vector, scale by push_magnitude
                    # Apply half force to each circle for symmetry
                    force_vec = push_magnitude * (diff / (dist + 1e-6)) * 0.5
                    forces[i] += force_vec
                    forces[j] -= force_vec
                    
        # Update centers based on accumulated forces and learning rate
        centers += forces * learning_rate
        
        # Clip centers to ensure they remain within the unit square boundaries
        # The boundary forces should mostly prevent needing this, but it's a safeguard.
        centers = np.clip(centers, 0, 1)

    # 3. Compute maximum valid radii for the relaxed centers
    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)
    
    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Compute max radii such that circles are in [0,1]^2 and don't overlap.
    Uses an iterative proportional shrinkage method.
    """
    n = centers.shape[0]
    
    # Initialize radii based on distance to the closest boundary
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    
    # Iteratively resolve overlaps between circles
    # For any pair (i, j), the condition is r_i + r_j <= dist_ij.
    # If they overlap, shrink both radii proportionally to meet this condition.
    for _ in range(25): # Increased iterations for more robust overlap resolution
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.linalg.norm(centers[i] - centers[j])
                
                # Check for overlap
                if radii[i] + radii[j] > dist:
                    # Calculate shrinkage factor
                    total_r = radii[i] + radii[j]
                    if total_r > 1e-9: # Avoid division by zero for extremely small radii
                        shrinkage = dist / total_r
                        radii[i] *= shrinkage
                        radii[j] *= shrinkage
                    else: # If total_r is effectively zero, set both radii to zero
                        radii[i] = 0.0
                        radii[j] = 0.0

    # Ensure no radii are negative or infinitesimally small due to numerical issues
    radii = np.maximum(radii, 1e-9)
    return radii

def run_packing():
    """Required entry point for the evaluator."""
    return construct_packing()
# EVOLVE-BLOCK-END