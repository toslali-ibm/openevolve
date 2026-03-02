# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Restricting candidate points to a fixed squared L2 norm (e.g., 4) simplifies the problem by fixing the potential maximum norm, allowing efficient filtering for valid points.
# MECHANISM-1: Fixed norm ensures the condition max ||p|| <= min ||p_i - p_j|| becomes equivalent to max_norm <= min_distance, simplifying greedy selection and maximizing valid points.
# EXPECT-1: num_points > 220

# HYPOTHESIS-2: Including both types of D_11 lattice points with squared L2 norm 4, (±2,0,...,0) and (±1,±1,±1,±1,0,...,0), provides a dense candidate pool for filtering.
# MECHANISM-2: The dense configuration of points with the same norm allows for a larger valid set, as pairwise distances among these points are guaranteed to satisfy the condition.
# EXPECT-2: num_points > 593

# HYPOTHESIS-3: Using a strict greedy selection process based on global max-norm and minimum distance tracking ensures valid configurations and maximizes the size of the point set.
# MECHANISM-3: Explicit tracking of the maximum squared norm and minimum squared distance ensures all points satisfy the condition, allowing for incremental additions without violating constraints.
# EXPECT-3: combined_score > 1.0

import numpy as np
from itertools import combinations, product

def generate_d11_points_sqnorm_4(d: int = 11) -> np.ndarray:
    """
    Generates all D_11 lattice points with squared L2 norm 4.

    Args:
        d: Dimension of the space (default is 11).

    Returns:
        points: np.ndarray of shape (num_points, d), candidate points with squared L2 norm 4.
    """
    points = []

    # (±2, 0, ..., 0) type points
    for i in range(d):
        point = np.zeros(d, dtype=int)
        point[i] = 2
        points.append(point)
        points.append(-point)

    # (±1, ±1, ±1, ±1, 0, ..., 0) type points
    for indices in combinations(range(d), 4):  # Choose 4 indices for ±1 entries
        for signs in product([-1, 1], repeat=4):  # Permutations of ±1
            point = np.zeros(d, dtype=int)
            for idx, sign in zip(indices, signs):
                point[idx] = sign
            points.append(point)

    return np.array(points)

def greedy_filter(points: np.ndarray) -> np.ndarray:
    """
    Greedy selection of points to maximize the set size while ensuring the condition:
    max ||p||^2 <= min ||p_i - p_j||^2.

    Args:
        points: np.ndarray of shape (num_candidates, d), candidate points to filter.

    Returns:
        valid_points: np.ndarray of valid points satisfying the condition.
    """
    valid_points = []
    max_norm_sq = 0  # Maximum squared norm of any point in the set
    min_dist_sq = float('inf')  # Minimum squared pairwise distance between points

    for point in points:
        point_norm_sq = np.sum(point**2)  # Squared norm of the candidate point
        is_valid = True

        # Check pairwise distances with existing valid points
        for vp in valid_points:
            dist_sq = np.sum((point - vp)**2)  # Squared L2 distance
            if dist_sq < point_norm_sq or dist_sq < max_norm_sq:
                is_valid = False
                break

        if is_valid:
            valid_points.append(point)
            max_norm_sq = max(max_norm_sq, point_norm_sq)
            min_dist_sq = min(min_dist_sq, *(np.sum((vp - point)**2) for vp in valid_points))

    return np.array(valid_points)

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates
    such that their maximum L2 norm is less than or equal to their minimum
    pairwise L2 distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points, 11) containing the integer points.
    """
    d = 11  # Dimension
    candidate_points = generate_d11_points_sqnorm_4(d)  # Generate candidates with squared norm 4
    valid_points = greedy_filter(candidate_points)  # Filter points using greedy selection
    return valid_points

# Run the function and store the result for evaluation
points = kissing_number11()
num_points = points.shape[0]
combined_score = num_points / 593  # Benchmark

print(f"Number of points: {num_points}")
print(f"Combined score: {combined_score:.4f}")
# EVOLVE-BLOCK-END