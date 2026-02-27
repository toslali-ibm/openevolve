# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using the D_11 lattice's first shell will provide a structured set of points
#   with guaranteed minimum pairwise distances and high symmetry.
# MECHANISM-1: The D_n lattice is known to maximize sphere packing densities in dimensions
#   up to 24, and its first shell consists of points with uniform distance properties.
# EXPECT-1: num_points > 220

# HYPOTHESIS-2: Filtering lattice shell points by symmetry will reduce redundancy and improve
#   the effective number of points satisfying the kissing number condition.
# MECHANISM-2: Exploiting lattice symmetries ensures that the points are well-distributed
#   and avoids clusters that violate the minimum distance constraint.
# EXPECT-2: num_points > 300

# HYPOTHESIS-3: Including cross-sections of E_8 and D_11 lattices will increase the number
#   of valid points without violating constraints.
# MECHANISM-3: By combining high-density lattice structures, we can find points that satisfy
#   the distance condition while exploring more geometric configurations.
# EXPECT-3: num_points > 593

import numpy as np
from itertools import permutations

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points, 11)
    """
    # Dimension
    d = 11

    # Generate the D_11 lattice's first shell: points of squared norm 2
    shell_radius_squared = 2
    shell_points = []
    
    # Generate all permutations of (±1, ±1, 0,...,0) with exactly two nonzero entries
    base_vector = [0] * d
    for i in range(d):
        for j in range(i + 1, d):
            # Create vectors with ±1 at positions i and j
            for signs in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                vector = base_vector.copy()
                vector[i] = signs[0]
                vector[j] = signs[1]
                shell_points.append(tuple(vector))
    
    # Remove duplicates and convert to numpy array
    shell_points = np.unique(np.array(shell_points), axis=0)

    # Validate distances and norms
    points = []
    for point in shell_points:
        # Compute L2 norm of the point
        norm = np.linalg.norm(point)
        # Check if the point satisfies the kissing number condition
        if all(np.linalg.norm(point - other) >= norm for other in points):
            points.append(point)

    # Convert to numpy array
    points = np.array(points)

    return points


# EVOLVE-BLOCK-END