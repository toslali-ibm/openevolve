# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles using a hexagonal grid approach"""
import numpy as np

def construct_packing():
    """
    Constructs a 26-circle packing using a staggered hexagonal grid,
    iterative center relaxation, and a robust radius solver.
    This approach aims to maximize the sum of radii by leveraging
    the high density of hexagonal packing and adapting it to the square container.

    Returns:
        Tuple of (centers, radii, sum_of_radii)
        centers: np.array of shape (26, 2) with (x, y) coordinates
        radii: np.array of shape (26) with radius of each circle
        sum_of_radii: Sum of all radii
    """
    n = 26
    
    # Define a precise hexagonal pattern for 26 circles.
    # A common and effective arrangement for 26 circles in a hexagonal grid
    # within a square is a layered pattern, e.g., 6 rows with varying counts:
    # 5-4-5-4-5-3 circles per row, which sums to exactly 26.
    row_patterns = [5, 4, 5, 4, 5, 3]

    # Estimate an initial average radius. The AlphaEvolve target (2.635)
    # divided by 26 circles gives an average radius of ~0.1013.
    # We use a slightly larger value for initial spacing to allow for
    # boundary effects and relaxation adjustments. This is a critical parameter.
    r_initial_guess = 0.102 
    
    # Calculate horizontal and vertical step sizes for a perfect hexagonal pattern.
    # Horizontal distance between centers in a row (2 * radius).
    h_step = 2 * r_initial_guess         
    # Vertical distance between row centers (sqrt(3) * radius).
    v_step = np.sqrt(3) * r_initial_guess 

    raw_centers = []
    current_y_pos = 0.0 # Initial y-coordinate for the first row.

    # Determine the maximum row length to help with horizontal centering.
    max_row_len = max(row_patterns)

    # Generate the initial raw centers based on the hexagonal pattern.
    for i, num_circles_in_row in enumerate(row_patterns):
        # Calculate x-offset to center the current row horizontally relative
        # to the widest row's potential span.
        x_offset_centering = (max_row_len - num_circles_in_row) * h_step / 2.0
        
        # Stagger odd-indexed rows horizontally to create the hexagonal grid.
        if i % 2 == 1:
            x_offset_centering += h_step / 2.0
        
        for j in range(num_circles_in_row):
            x = x_offset_centering + j * h_step
            raw_centers.append([x, current_y_pos])
        
        current_y_pos += v_step # Move to the next row's y-coordinate.

    centers = np.array(raw_centers)

    # Scale and shift the entire generated pattern to fit optimally within the unit square.
    # The goal is for the outermost circles to effectively 'touch' the boundaries
    # with a radius equal to `r_initial_guess`. Thus, centers should span from
    # `r_initial_guess` to `1 - r_initial_guess`.
    min_x_raw, max_x_raw = np.min(centers[:,0]), np.max(centers[:,0])
    min_y_raw, max_y_raw = np.min(centers[:,1]), np.max(centers[:,1])
    
    desired_x_span = 1.0 - 2 * r_initial_guess
    desired_y_span = 1.0 - 2 * r_initial_guess
    
    actual_x_span = max_x_raw - min_x_raw
    actual_y_span = max_y_raw - min_y_raw
    
    # Calculate scale factors. Use the minimum to ensure the entire grid fits
    # without distortion and potentially shrinks if the initial guess was too large.
    scale_factor_x = desired_x_span / actual_x_span if actual_x_span > 1e-6 else 1.0
    scale_factor_y = desired_y_span / actual_y_span if actual_y_span > 1e-6 else 1.0
    
    scale_factor = min(scale_factor_x, scale_factor_y)
    
    # Apply scaling and re-center the grid within the unit square.
    centers = (centers - np.array([min_x_raw, min_y_raw])) * scale_factor + r_initial_guess
    
    # Iterative relaxation of centers (force-directed layout)
    # This process refines the initial positions by pushing overlapping circles apart
    # and pulling them towards a more uniform distribution.
    num_relaxation_iterations = 250 # Increased iterations for better convergence.
    learning_rate = 0.002 # Step size for center movement, reduced for stability.
    
    # Target separation for repulsion. Slightly less than 2*r_initial_guess
    # to encourage a tighter packing that the radius solver can then resolve.
    target_separation_dist = 2 * r_initial_guess * 0.98 
    
    for _ in range(num_relaxation_iterations):
        forces = np.zeros_like(centers)
        
        # Repulsion forces between circles: push circles apart if they are too close.
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                
                if dist < target_separation_dist:
                    # Magnitude of repulsion force, proportional to the overlap.
                    force_magnitude = (target_separation_dist - dist) * 0.1 
                    if dist > 1e-9: # Avoid division by zero for nearly identical centers.
                        forces[i] -= (diff / dist) * force_magnitude
                        forces[j] += (diff / dist) * force_magnitude
        
        # Boundary repulsion: gently push circles away from the container walls.
        wall_repulsion_strength = 0.005 # A small strength to allow some flexibility.
        for i in range(n):
            # Use an effective radius for boundary checks.
            effective_r = r_initial_guess 
            
            if centers[i, 0] < effective_r: 
                forces[i, 0] += wall_repulsion_strength * (effective_r - centers[i, 0])
            if centers[i, 0] > 1 - effective_r: 
                forces[i, 0] -= wall_repulsion_strength * (centers[i, 0] - (1 - effective_r))
            if centers[i, 1] < effective_r: 
                forces[i, 1] += wall_repulsion_strength * (effective_r - centers[i, 1])
            if centers[i, 1] > 1 - effective_r: 
                forces[i, 1] -= wall_repulsion_strength * (centers[i, 1] - (1 - effective_r))

        # Update centers based on the accumulated forces.
        centers += learning_rate * forces
        
        # Clip centers to ensure they remain within the unit square with a minimal buffer.
        # This buffer prevents issues where centers are exactly on the boundary, leading
        # to zero radius calculations.
        centers = np.clip(centers, 1e-5, 1.0 - 1e-5)

    # Compute maximum valid radii for this optimized center configuration.
    radii = compute_max_radii(centers)

    sum_radii = np.sum(radii)

    return centers, radii, sum_radii


def compute_max_radii(centers, num_iterations=300): 
    """
    Compute the maximum possible radii for each circle position such that
    they do not overlap and remain within the unit square.
    This function uses a robust iterative relaxation method (Gauss-Seidel like)
    to maximize radii.

    Args:
        centers: np.array of shape (n, 2) with (x, y) coordinates.
        num_iterations: Number of iterations for the radius adjustment process.

    Returns:
        np.array of shape (n) with the optimized radius for each circle.
    """
    n = centers.shape[0]
    radii = np.zeros(n)

    # Initialize radii to the distance to the nearest boundary.
    # This provides a tight upper bound for each circle's radius.
    for i in range(n):
        x, y = centers[i]
        radii[i] = min(x, y, 1 - x, 1 - y)
        radii[i] = max(radii[i], 1e-8) # Ensure radii are always positive (small epsilon).

    # Iteratively adjust radii to maximize them without overlap.
    for iter_step in range(num_iterations):
        max_change = 0.0 # Track the largest change in radius to check for convergence.
        for i in range(n):
            # Calculate the maximum possible radius for circle 'i', initially limited by boundaries.
            r_candidate = min(centers[i,0], centers[i,1], 1 - centers[i,0], 1 - centers[i,1])
            
            # Further limit 'r_candidate' by checking potential overlaps with all other circles 'j'.
            # The constraint is: r_i + r_j <= dist_ij  =>  r_i <= dist_ij - r_j.
            for j in range(n):
                if i == j: 
                    continue # Skip self-comparison.
                dist_ij = np.linalg.norm(centers[i] - centers[j])
                
                # Update r_candidate using the current radius of circle 'j' (Gauss-Seidel approach).
                r_candidate = min(r_candidate, max(0.0, dist_ij - radii[j]))
            
            # Update the radius for circle 'i' and track the change.
            change = abs(radii[i] - r_candidate)
            if change > max_change:
                max_change = change
            radii[i] = r_candidate
            radii[i] = max(radii[i], 1e-8) # Ensure radius remains positive.
        
        # If no significant changes occurred in an iteration, assume convergence and break early.
        if max_change < 1e-7 and iter_step > 0: # Stricter convergence criterion.
            break 
    
    # Final pass to resolve any remaining minor overlaps. This acts as a safety net
    # for numerical precision issues or complex interactions not fully resolved
    # by the primary iterative solver. Overlaps are resolved by distributing the excess equally.
    for _ in range(100): # More iterations for this final adjustment pass.
        changed_in_final_pass = False
        for i in range(n):
            for j in range(i + 1, n):
                dist_ij = np.linalg.norm(centers[i] - centers[j])
                # Check for overlap with a very small tolerance for floating-point precision.
                if radii[i] + radii[j] > dist_ij - 1e-10:
                    # If centers are practically identical, assign minimal radii to prevent issues.
                    if dist_ij < 1e-10: 
                        radii[i] = 1e-8
                        radii[j] = 1e-8
                        changed_in_final_pass = True
                        continue

                    overlap = (radii[i] + radii[j] - dist_ij) / 2.0
                    radii[i] = max(1e-8, radii[i] - overlap)
                    radii[j] = max(1e-8, radii[j] - overlap)
                    changed_in_final_pass = True
        if not changed_in_final_pass:
            break # If no changes, converged.
            
    return radii

# Required entry point for the evaluator.
def run_packing():
    """Required entry point for the evaluator."""
    return construct_packing()

# EVOLVE-BLOCK-END