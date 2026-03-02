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
    2. These points constitute the shell of squared norm 4 in the D_11 lattice.
       For any two such points p_i, p_j, we have ||p_i||^2 = ||p_j||^2 = 4.
       The condition max ||p|| <= min ||p_i - p_j|| translates to:
       max ||p||^2 <= min ||p_i - p_j||^2
       4 <= 8 - 2 * (p_i . p_j)
       2 * (p_i . p_j) <= 4
       p_i . p_j <= 2

    3. We use a greedy algorithm to select a maximal subset of these points
       such that for any two selected points p_x, p_y, their dot product p_x . p_y <= 2.
       To ensure reproducibility and potentially a better greedy result, we shuffle
       the candidate points with a fixed random seed.
    """
    d = 11
    RANDOM_SEED = 42 # Fixed seed for reproducibility

    all_candidates = []

    # Type A: Permutations of (+-2, 0, ..., 0)
    # Total 2 * d = 22 points
    for i in range(d):
        for val in [2, -2]:
            p = np.zeros(d, dtype=np.int64)
            p[i] = val
            all_candidates.append(p)

    # Type B: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    # Total (d choose 4) * 2^4 = 330 * 16 = 5280 points
    for indices in combinations(range(d), 4):
        # Generate all 2^4 sign combinations for the 4 non-zero positions
        for signs in product([-1, 1], repeat=4):
            p = np.zeros(d, dtype=np.int64)
            for i, idx in enumerate(indices):
                p[idx] = signs[i]
            all_candidates.append(p)

    # Shuffle candidates to get a potentially better greedy selection
    random.seed(RANDOM_SEED)
    random.shuffle(all_candidates)

    selected_points = []
    
    # The first point is always valid
    if all_candidates:
        selected_points.append(all_candidates[0])
    
    for i in range(1, len(all_candidates)):
        p_candidate = all_candidates[i]
        
        # If no points have been selected yet (e.g., all_candidates was empty or first point was skipped)
        if not selected_points:
            selected_points.append(p_candidate)
            continue

        # Convert selected_points to a numpy array for efficient batched dot product calculation
        # This conversion happens repeatedly, but for a few hundreds of points, it's faster
        # than looping through Python lists and individual np.dot calls.
        selected_np_array = np.array(selected_points, dtype=np.int64)
        
        # Calculate dot products with all currently selected points
        # np.dot(selected_np_array, p_candidate) performs (N, D) . (D,) -> (N,)
        dot_products = np.dot(selected_np_array, p_candidate)
        
        # Check if all dot products satisfy the condition (<= 2)
        if np.all(dot_products <= 2):
            selected_points.append(p_candidate)

    return np.array(selected_points, dtype=np.int64)