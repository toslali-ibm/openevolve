# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using the D_11 root system's first shell gives a higher number of valid points.
# MECHANISM-1: The D_n lattice's root system provides structured points with equal norm and large minimum distances due to its symmetry properties.
# EXPECT-1: num_points > 220

# HYPOTHESIS-2: Filtering the points from the D_11 first shell based on the kissing number condition improves the combined_score.
# MECHANISM-2: The condition max_i ||p_i|| <= min_{i!=j} ||p_i - p_j|| eliminates points that violate the sphere-packing constraints, ensuring the set is valid.
# EXPECT-2: combined_score > 0.5

import numpy as np
from itertools import permutations

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates
    such that their maximum norm is smaller than their minimum pairwise distance,
    aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points, 11)
    """
    d = 11  # Dimension
    # Generate the first shell of the D_11 root system
    # Points are of the form (±1, ±1, 0, ..., 0), with two non-zero entries ±1
    shell_points = []
    for i in range(d):
        for j in range(i+1, d):
            for signs in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                point = np.zeros(d, dtype=int)
                point[i] = signs[0]
                point[j] = signs[1]
                shell_points.append(point)
    
    # Convert to numpy array for efficient computation
    shell_points = np.array(shell_points)

    # Compute pairwise distances to filter valid points
    valid_points = []
    for point in shell_points:
        # Check the condition max_i ||p_i|| <= min_{i!=j} ||p_i - p_j|| for each point
        if all(np.linalg.norm(point) <= np.linalg.norm(point - other) for other in valid_points):
            valid_points.append(point)

    return np.array(valid_points)

# EVOLVE-BLOCK-END