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

    # Place circles in a structured pattern
    # This is a simple pattern - evolution will improve this

    # Place circles in a hexagonal-like grid for n=26 (5+6+5+6+4 pattern)
    r_base_guess = 0.08 # Initial guess for approximate radius
    dx = 2 * r_base_guess
    dy = np.sqrt(3) * r_base_guess

    row_counts = [5, 6, 5, 6, 4] # Defines the number of circles in each of the 5 rows
    
    current_idx = 0
    
    # Calculate overall vertical offset to center the entire block of circles
    total_block_height = (len(row_counts) - 1) * dy + 2 * r_base_guess
    y_overall_offset = (1.0 - total_block_height) / 2.0

    for r_idx, count in enumerate(row_counts):
        # Calculate horizontal offset for staggering
        x_stagger_offset = 0.0
        if r_idx % 2 == 1: # Odd rows are shifted by r_base_guess for hexagonal packing
            x_stagger_offset = r_base_guess
        
        # Calculate row width and horizontal margin to center each row
        row_actual_width = (count - 1) * dx + 2 * r_base_guess
        margin_x = (1.0 - row_actual_width) / 2.0

        # Calculate vertical position for the current row
        y = y_overall_offset + r_base_guess + r_idx * dy

        for c_idx in range(count):
            if current_idx < n:
                x = margin_x + r_base_guess + c_idx * dx + x_stagger_offset
                centers[current_idx] = [x, y]
                current_idx += 1

    # Simple iterative relaxation to improve spacing
    for _ in range(50):
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                if dist < 0.18: # Target diameter
                    push = (0.18 - dist) * 0.5 * (diff / (dist + 1e-9))
                    centers[i] += push
                    centers[j] -= push
            # Keep within bounds
            centers[i] = np.clip(centers[i], 0.05, 0.95)

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
    radii = np.ones(n)

    # Initialize radii to a small value or based on wall distances
    # Iteratively grow radii to their maximum possible size without overlap
    radii = np.zeros(n)
    
    # Pre-calculate wall distances for each center (these don't change during radii calculation)
    wall_limits = np.array([min(c[0], c[1], 1 - c[0], 1 - c[1]) for c in centers])

    # Iteratively grow radii
    # Increased iterations for better convergence, especially for tightly packed configurations
    for iteration in range(200): 
        prev_radii = np.copy(radii) # Keep track of previous radii for convergence check
        for i in range(n):
            # Start with the wall limit for circle i
            max_r_i = wall_limits[i]

            # Consider limits from other circles
            for j in range(n):
                if i == j: continue # Skip self-comparison
                dist = np.linalg.norm(centers[i] - centers[j])
                # The maximum radius for circle i is limited by (distance to j - radius of j)
                # Ensure the result is non-negative to avoid issues if circles are very close or overlapping
                max_r_i = min(max_r_i, max(0.0, dist - radii[j])) 
            
            radii[i] = max_r_i # Update radius for circle i
        
        # Check for convergence: if radii haven't changed significantly, we can stop early
        if np.allclose(radii, prev_radii, atol=1e-7): # Increased precision for convergence
            break
            
    # Ensure all radii are strictly positive to avoid numerical issues or zero-radius circles
    radii = np.maximum(radii, 1e-7) # Small positive value to prevent zero radii

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
