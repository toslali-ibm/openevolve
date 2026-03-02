# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using the first shell of the D_11 root lattice will result in a higher number of valid points.
# MECHANISM-1: The D_11 root lattice has structured points with minimal pairwise distances of sqrt(2), ensuring
#   that all points satisfy the condition max ||p|| <= min ||p_i - p_j||.
# EXPECT-1: num_points > 220

# HYPOTHESIS-2: Filtering the points from the second shell of the D_11 lattice by distance constraints will further
#   increase the number of valid points, as the second shell provides more candidates.
# MECHANISM-2: The second shell contains points at a higher norm, but selective filtering ensures the distance
#   constraint is satisfied while adding valid points.
# EXPECT-2: num_points > 300

# HYPOTHESIS-3: Leveraging symmetries of the D_11 lattice to generate additional points will lead to further
#   improvement by exploiting the inherent structure of the lattice.
# MECHANISM-3: Symmetries allow generation of equivalent points without recomputation, increasing the set size.
# EXPECT-3: combined_score > 0.6

import numpy as np
from scipy.spatial.distance import pdist, squareform

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm is smaller
    than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points, 11)
    """
    d = 11  # Dimension
    # Generate the first shell of the D_11 root lattice
    # D_11 root lattice points are of the form (±1, ±1, 0, ..., 0) with exactly two ±1s
    first_shell = []
    for i in range(d):
        for j in range(i + 1, d):
            point = np.zeros(d, dtype=int)
            point[i], point[j] = 1, 1
            first_shell.append(point)
            first_shell.append(-point)
    
    first_shell = np.array(first_shell)
    
    # Validate points: max norm <= min pairwise distance
    # For the first shell, all points have norm sqrt(2) and pairwise distances >= sqrt(2), so all are valid
    valid_points = first_shell.tolist()

    # Generate the second shell of the D_11 lattice
    # The second shell corresponds to points with 4 nonzero ±1 entries
    second_shell = []
    for i in range(d):
        for j in range(i + 1, d):
            for k in range(j + 1, d):
                for l in range(k + 1, d):
                    point = np.zeros(d, dtype=int)
                    point[i], point[j], point[k], point[l] = 1, 1, -1, -1
                    second_shell.append(point)
                    second_shell.append(-point)
    
    second_shell = np.array(second_shell)
    
    # Filter the second shell to ensure the distance constraint is met
    for point in second_shell:
        # Check if the new point satisfies the distance constraint with all existing valid points
        distances = np.linalg.norm(valid_points - point, axis=1)
        if np.min(distances) >= np.linalg.norm(point):
            valid_points.append(point.tolist())
    
    # Convert valid points back to a numpy array
    valid_points = np.array(valid_points)

    return valid_points


# EVOLVE-BLOCK-END