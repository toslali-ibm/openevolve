import numpy as np
from itertools import combinations, product
import random

def kissing_number11() -> np.ndarray:
    """
    Constructs a set of points in Z^11 such that max ||p_i|| <= min ||p_i - p_j||.

    Strategy:
    1. Identify all points in Z^11 with squared L2 norm 4. These are:
       a) Permutations of (+-2, 0, ..., 0)
       b) Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    2. For any two such points p_i, p_j, we have ||p_i||^2 = ||p_j||^2 = 4.
       The problem condition max ||p|| <= min ||p_i - p_j|| translates to:
       max ||p||^2 <= min ||p_i - p_j||^2
       4 <= 8 - 2 * (p_i . p_j)  (since ||p_i - p_j||^2 = ||p_i||^2 + ||p_j||^2 - 2 * (p_i . p_j))
       2 * (p_i . p_j) <= 4
       p_i . p_j <= 2

    3. We use a greedy algorithm to select a maximal subset of these points
       such that for any two selected points p_x, p_y, their dot product p_x . p_y <= 2.
       To improve the greedy result, we sort the candidate points deterministically
       based on a heuristic. We prioritize points with smaller L1 norm (sum of absolute coordinates)
       as they tend to be "simpler" or "sparser", potentially leading to fewer conflicts
       early in the greedy selection process.
    """
    d = 11
    # RANDOM_SEED is not directly used in the final greedy selection but is included
    # for consistency with previous programs if randomization were introduced.
    # The sorting key and deterministic iteration ensure reproducibility.
    RANDOM_SEED = 42 

    all_candidates = []

    # Type A: Permutations of (+-2, 0, ..., 0)
    # These 2 * d = 22 points have L1 norm 2 and squared L2 norm 4.
    for i in range(d):
        for val in [2, -2]:
            p = np.zeros(d, dtype=np.int64)
            p[i] = val
            all_candidates.append(p)

    # Type B: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    # These (d choose 4) * 2^4 = 330 * 16 = 5280 points have L1 norm 4 and squared L2 norm 4.
    for indices in combinations(range(d), 4):
        # Generate all 2^4 sign combinations for the 4 non-zero positions
        for signs in product([-1, 1], repeat=4):
            p = np.zeros(d, dtype=np.int64)
            for i, idx in enumerate(indices):
                p[idx] = signs[i]
            all_candidates.append(p)

    # Sort candidates deterministically based on L1 norm (sum of absolute coordinates) ascending.
    # This places Type A points (L1=2) before Type B points (L1=4).
    # Lexicographical sort (tuple(p)) is used for tie-breaking to ensure reproducibility.
    all_candidates.sort(key=lambda p: (np.sum(np.abs(p)), tuple(p)))

    selected_points_list = []
    # Initialize an empty 2D NumPy array to efficiently store selected points for dot product calculations.
    selected_np_array = np.empty((0, d), dtype=np.int64) 

    for p_candidate in all_candidates:
        # If no points have been selected yet, add the first candidate.
        if selected_np_array.shape[0] == 0:
            selected_points_list.append(p_candidate)
            selected_np_array = np.array([p_candidate], dtype=np.int64)
            continue

        # Calculate dot products between the candidate point and all currently selected points.
        # np.dot(selected_np_array, p_candidate) performs (N, D) . (D,) -> (N,) efficiently.
        dot_products = np.dot(selected_np_array, p_candidate)
        
        # Check if all dot products satisfy the condition (<= 2).
        if np.all(dot_products <= 2):
            selected_points_list.append(p_candidate)
            # Efficiently add p_candidate to selected_np_array using np.vstack.
            # This creates a new array, but only when a point is actually added,
            # which is more efficient than recreating the entire array in every loop iteration.
            selected_np_array = np.vstack([selected_np_array, p_candidate])

    return np.array(selected_points_list, dtype=np.int64)