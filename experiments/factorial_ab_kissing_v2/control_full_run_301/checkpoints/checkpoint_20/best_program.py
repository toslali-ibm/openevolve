# EVOLVE-BLOCK-START
import numpy as np
from itertools import combinations, product


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm
    is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points, 11)
    """
    d = 11  # Dimension
    max_norm_sq = 2  # Target maximum squared L2 norm (||p_i||^2)

    # Generate points in the D_11 lattice with ||p||^2 = max_norm_sq
    # D_n lattice: Points in Z^n where the sum of coordinates is even
    points = []
    for indices in combinations(range(d), 2):  # Choose 2 nonzero coordinates
        for signs in product([-1, 1], repeat=2):  # Assign ±1 to the chosen coordinates
            point = np.zeros(d, dtype=int)
            point[indices[0]] = signs[0]
            point[indices[1]] = signs[1]
            points.append(point)
    
    points = np.array(points)

    # Filter points to satisfy the condition max_i ||p_i|| <= min_{i!=j} ||p_i - p_j||
    valid_points = []
    for i, p_i in enumerate(points):
        is_valid = True
        for j, p_j in enumerate(points):
            if i != j:
                # Compute ||p_i - p_j||^2
                distance_sq = np.sum((p_i - p_j) ** 2)
                if distance_sq < max_norm_sq:  # Ensure minimum pairwise distance
                    is_valid = False
                    break
        if is_valid:
            valid_points.append(p_i)
    
    return np.array(valid_points)


# EVOLVE-BLOCK-END