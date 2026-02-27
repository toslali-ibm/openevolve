import numpy as np
from itertools import combinations, product
import random

def kissing_number11() -> np.ndarray:
    """
    Constructs a set of points in Z^11 where max ||p_i|| <= min ||p_i - p_j||.
    The strategy is to select points from the shell of squared L2 norm 4 (K=4)
    and use a greedy algorithm with randomized candidate selection.

    Condition derivation for K=4:
    Let S be the set of points. We require max_p in S ||p|| <= min_{p1, p2 in S, p1!=p2} ||p1 - p2||.
    If all points p in S have ||p||^2 = 4, then max ||p||^2 = 4.
    The condition becomes 4 <= min ||p1 - p2||^2.
    For any p1, p2 in S, ||p1 - p2||^2 = ||p1||^2 + ||p2||^2 - 2 * <p1, p2>
                                       = 4 + 4 - 2 * <p1, p2>
                                       = 8 - 2 * <p1, p2>.
    So, we need 4 <= 8 - 2 * <p1, p2>, which simplifies to 2 * <p1, p2> <= 4,
    or <p1, p2> <= 2.

    Returns:
        np.ndarray: An array of shape (num_points, 11) containing the selected points.
    """
    d = 11
    
    # Set fixed random seed for reproducibility
    random.seed(42) 

    candidate_points_list = []

    # Type 1: Permutations of (+-2, 0, ..., 0)
    # These points have squared L2 norm = 4.
    # Example: (2,0,0,0,0,0,0,0,0,0,0), (-2,0,0,0,0,0,0,0,0,0,0)
    for i in range(d):
        p_pos = np.zeros(d, dtype=np.int64)
        p_neg = np.zeros(d, dtype=np.int64)
        p_pos[i] = 2
        p_neg[i] = -2
        candidate_points_list.append(p_pos)
        candidate_points_list.append(p_neg)
    
    # Type 2: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    # These points also have squared L2 norm = 1^2 + 1^2 + 1^2 + 1^2 = 4.
    # We consider all combinations of 4 positions and all 2^4 = 16 sign patterns.
    # All these points are also in the D11 lattice (sum of coordinates is always even).
    for indices in combinations(range(d), 4):
        # Generate all 2^4 sign combinations for the 4 non-zero positions
        for signs_tuple in product([-1, 1], repeat=4):
            p = np.zeros(d, dtype=np.int64)
            for k, idx in enumerate(indices):
                p[idx] = signs_tuple[k]
            candidate_points_list.append(p)
            
    # Shuffle the candidate points to randomize the greedy selection order.
    # This helps in finding a larger set than a fixed order.
    random.shuffle(candidate_points_list)

    selected_points = []
    
    # Greedy selection: iterate through shuffled candidates and add if valid.
    for new_p in candidate_points_list:
        is_valid = True
        for existing_p in selected_points:
            # Check the dot product condition: <new_p, existing_p> <= 2
            if np.dot(new_p, existing_p) > 2:
                is_valid = False
                break
        
        if is_valid:
            selected_points.append(new_p)

    return np.array(selected_points, dtype=np.int64)