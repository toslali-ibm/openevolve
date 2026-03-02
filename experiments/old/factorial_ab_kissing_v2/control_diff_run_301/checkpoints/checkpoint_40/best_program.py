# EVOLVE-BLOCK-START
import numpy as np


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points,11)
    """
    d = 11
    # Generate points from the D_11 lattice with norm-squared equal to 4
    d = 11
    radius_squared = 4
    candidate_points = []
    
    # Generate all integer points with sum of squares equal to radius_squared
    for x in range(-2, 3):  # Symmetry reduces the range we need to iterate over
        for y in range(-2, 3):
            for z in range(-2, 3):
                # Extend to all 11 dimensions
                point = np.array([x, y, z] + [0] * (d - 3))
                if np.sum(point ** 2) == radius_squared and np.sum(point) % 2 == 0:
                    candidate_points.append(point)
    
    # Convert to numpy array
    candidate_points = np.array(candidate_points, dtype=np.int64)
    
    # Filter points to satisfy the kissing number constraint
    filtered_points = []
    for p1 in candidate_points:
        valid = True
        for p2 in filtered_points:
            if np.linalg.norm(p1 - p2) < np.linalg.norm(p1):
                valid = False
                break
        if valid:
            filtered_points.append(p1)
    
    # Convert filtered points to numpy array
    points = np.array(filtered_points, dtype=np.int64)

    return points


# EVOLVE-BLOCK-END
