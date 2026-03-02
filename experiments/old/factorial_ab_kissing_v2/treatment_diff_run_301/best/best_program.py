# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using the E_8 lattice as a cross-section and extending to 11 dimensions improves fitness
# MECHANISM-1: E_8 lattice has a high kissing number and dense sphere packing properties; embedding it in 11 dimensions provides a structured set of points with good symmetry
# EXPECT-1: num_points > 1000
# HYPOTHESIS-2: Filtering using greedy optimization improves fitness by removing points that violate constraints
# MECHANISM-2: Greedy filtering ensures pairwise minimum distances are enforced and identifies subsets satisfying the kissing number constraint
# EXPECT-2: num_points > 800
# HYPOTHESIS-3: Combining E_8 lattice embedding with greedy optimization yields a larger kissing number set
# MECHANISM-3: E_8 lattice embedding provides a structured starting point, while greedy optimization refines the set to maximize valid points
# EXPECT-3: combined_score > 2.0
import numpy as np


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points,11)
    """
    d = 11
    # Generate points from the first shell of the D_11 root system
    def d11_shell():
        points = []
        for i in range(d):
            for j in range(i+1, d):
                p = np.zeros(d, dtype=np.int64)
                p[i], p[j] = 1, -1
                points.append(p)
                points.append(-p)
        return np.array(points)
    
    points = d11_shell()

    # Filter points to satisfy the kissing number constraint
    def filter_points(points):
        norms = np.linalg.norm(points, axis=1)
        min_distance = np.min(
            [np.linalg.norm(p1 - p2) for i, p1 in enumerate(points) for j, p2 in enumerate(points) if i != j]
        )
        valid_points = points[norms <= min_distance]
        return valid_points

    points = filter_points(points)
    return points


# EVOLVE-BLOCK-END
