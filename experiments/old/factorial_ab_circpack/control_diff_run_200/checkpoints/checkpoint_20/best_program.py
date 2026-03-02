# EVOLVE-BLOCK-START
"""Constructor-based circle packing for n=26 circles"""
import numpy as np


def construct_packing():
    """
    Construct a specific arrangement of 26 circles in a unit square
    that attempts to maximize the sum of their radii.

    Returns:
        Tuple of (centers, radii, sum_of_radii)
        centers: np.array of shape (26, 2) with (x, y) coordinates
        radii: np.array of shape (26) with radius of each circle
        sum_of_radii: Sum of all radii
    """
    # Initialize arrays for 26 circles
    n = 26
    centers = np.zeros((n, 2))

    # Place circles in a hexagonal pattern for N=26 (6-5-6-5-4 rows)
    idx = 0
    
    rows_layout = [6, 5, 6, 5, 4] # Number of circles in each of the 5 rows
    num_total_rows = len(rows_layout)
    
    # Calculate base radius assuming 6 circles tightly packed horizontally
    r_val = 1.0 / 12.0 # r = 1 / (2 * num_circles_in_densest_row)
    
    # Calculate horizontal and vertical spacing for hexagonal packing
    x_spacing = 2 * r_val # Distance between centers in x
    y_spacing = np.sqrt(3) * r_val # Distance between centers in y
    
    # Calculate total height of the packing to center it vertically
    total_packing_height = (num_total_rows - 1) * y_spacing + 2 * r_val
    y_start_pos = (1.0 - total_packing_height) / 2.0 + r_val
    
    current_y = y_start_pos
    
    # Iterate through rows and place circles
    for r_idx, num_circles_in_row in enumerate(rows_layout):
        # Calculate horizontal offset to center the current row
        # relative to the widest possible row (6 circles)
        x_row_centering_offset = (max(rows_layout) - num_circles_in_row) * x_spacing / 2.0
        
        # Apply the base x-start for the widest row and then the centering offset
        current_x = r_val + x_row_centering_offset
        
        # Apply hexagonal shift for alternating rows
        # Odd-indexed rows are shifted by half the horizontal spacing (r_val)
        if r_idx % 2 == 1:
            current_x += r_val
            
        # Place circles in the current row
        for c_idx in range(num_circles_in_row):
            if idx < n:
                centers[idx] = [current_x, current_y]
                current_x += x_spacing
                idx += 1
        current_y += y_spacing # Move to the next row's y position
    
    # Simple iterative relaxation to improve spacing and keep centers within bounds
    # This step pushes overlapping circles apart and clips them to stay within the square.
    # The constants 0.19 (target separation) and 0.09/0.91 (clipping bounds) are heuristics
    # found to be effective in previous high-performing programs.
    for _ in range(50): # Number of relaxation iterations
        for i in range(n):
            for j in range(i + 1, n): # Iterate unique pairs for efficiency
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                
                # If circles are too close (closer than the target separation of 0.19)
                if dist < 0.19:
                    # Calculate push vector to separate them
                    push_amount = (0.19 - dist) * 0.5 # Half the 'overlap' with target distance
                    push_vector = (diff / dist) * push_amount
                    
                    centers[i] += push_vector
                    centers[j] -= push_vector
            
            # Clip centers to ensure they stay within the square (with a margin for radius)
            # 0.09 and 0.91 correspond to centers being at least 0.09 from the edge,
            # implying a max radius of ~0.09 for boundary circles.
            centers[i] = np.clip(centers[i], 0.09, 0.91)

    # Compute maximum valid radii for this configuration
    radii = compute_max_radii(centers)

    # Calculate the sum of radii
    sum_radii = np.sum(radii)

    return centers, radii, sum_radii


def compute_max_radii(centers):
    """
    Compute the maximum possible radii for each circle position
    such that they don't overlap and stay within the unit square.

    Args:
        centers: np.array of shape (n, 2) with (x, y) coordinates

    Returns:
        np.array of shape (n) with radius of each circle
    """
    n = centers.shape[0]
    radii = np.ones(n) # Initialize with a large radius (e.g., 1.0)

    # First, limit by distance to square borders
    for i in range(n):
        x, y = centers[i]
        # Distance to borders
        radii[i] = min(x, y, 1 - x, 1 - y)

    # Limit by distance to other circles iteratively
    # This iterative refinement allows radii to settle into a stable,
    # non-overlapping configuration where radii are maximized.
    for _ in range(10): # Iterative refinement for radius balancing
        for i in range(n):
            for j in range(n):
                if i == j: continue # Don't compare a circle to itself
                dist = np.linalg.norm(centers[i] - centers[j])
                
                # If circles overlap or are about to overlap
                if radii[i] + radii[j] > dist:
                    # Adjust radii to be exactly touching
                    # This specific adjustment logic was found to be effective
                    avg = (radii[i] + radii[j])
                    radii[i] = (radii[i] / avg) * dist * 0.5 + radii[i] * 0.5
                    radii[j] = dist - radii[i] # The other radius takes the remainder
                    
                    # Ensure radii don't become negative (can happen if initial radii are too large)
                    radii[i] = max(0.0, radii[i])
                    radii[j] = max(0.0, radii[j])

    return radii


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
def run_packing():
    """Run the circle packing constructor for n=26"""
    centers, radii, sum_radii = construct_packing()
    return centers, radii, sum_radii


def visualize(centers, radii):
    """
    Visualize the circle packing

    Args:
        centers: np.array of shape (n, 2) with (x, y) coordinates
        radii: np.array of shape (n) with radius of each circle
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    fig, ax = plt.subplots(figsize=(8, 8))

    # Draw unit square
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.grid(True)

    # Draw circles
    for i, (center, radius) in enumerate(zip(centers, radii)):
        circle = Circle(center, radius, alpha=0.5)
        ax.add_patch(circle)
        ax.text(center[0], center[1], str(i), ha="center", va="center")

    plt.title(f"Circle Packing (n={len(centers)}, sum={sum(radii):.6f})")
    plt.show()


if __name__ == "__main__":
    centers, radii, sum_radii = run_packing()
    print(f"Sum of radii: {sum_radii}")
    # AlphaEvolve improved this to 2.635

    # Uncomment to visualize:
    visualize(centers, radii)
