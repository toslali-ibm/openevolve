import numpy as np
from itertools import combinations, product
import random

def kissing_number11() -> np.ndarray:
    """
    Constructs a set of points in Z^11 such that max ||p_i|| <= min ||p_i - p_j||.
    The strategy is to find a large subset of points from Z^11.

    Condition: max ||p_i||^2 <= min ||p_i - p_j||^2.
    We target points with squared L2 norm (||p||^2) equal to 4.
    For two such points p_i, p_j, the condition simplifies to:
    p_i . p_j <= 2.

    The algorithm proceeds as follows:
    1. Generate all candidate points in Z^11 with ||p||^2 = 4.
       These are of two types:
       - Permutations of (+-2, 0, ..., 0)
       - Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    2. Sort these candidate points lexicographically to ensure a deterministic greedy selection.
    3. Greedily add points to the `selected_points` set if they satisfy the dot product condition
       `p_new . p_existing <= 2` with all already selected points.
    """
    d = 11
    
    # Use a fixed random seed for reproducibility.
    random.seed(42) 
    # np.random.seed(42) is not strictly necessary for this implementation
    # as no NumPy random functions are directly used for shuffling or generation.

    selected_points = []
    
    # 1. Generate and add Type 1 points: Permutations of (+-2, 0, ..., 0)
    # These 22 points are mutually valid (dot products are 0 or -4).
    type1_points = []
    for i in range(d):
        p_pos = np.zeros(d, dtype=np.int64)
        p_neg = np.zeros(d, dtype=np.int64)
        p_pos[i] = 2
        p_neg[i] = -2
        type1_points.append(p_pos)
        type1_points.append(p_neg)
    
    # Sort Type 1 points lexicographically for deterministic order
    type1_points.sort(key=lambda p: tuple(p))
    selected_points.extend(type1_points)

    # 2. Generate Type 2 candidates: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    # These are C(11, 4) * 2^4 = 330 * 16 = 5280 points.
    type2_candidates = []
    for indices in combinations(range(d), 4):
        # Generate all 2^4 sign patterns for the 4 non-zero positions
        for signs in product([-1, 1], repeat=4):
            p = np.zeros(d, dtype=np.int64)
            for i, idx in enumerate(indices):
                p[idx] = signs[i]
            type2_candidates.append(p)
            
    # Sort Type 2 candidates lexicographically for deterministic greedy selection order.
    type2_candidates.sort(key=lambda p: tuple(p))

    # 3. Greedy selection for Type 2 candidates
    for p_new in type2_candidates:
        is_valid = True
        for p_existing in selected_points:
            # Check dot product condition: p_i . p_j <= 2
            if np.dot(p_new, p_existing) > 2:
                is_valid = False
                break
        
        if is_valid:
            selected_points.append(p_new)

    return np.array(selected_points)