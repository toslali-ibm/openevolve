# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Correctly applying the minimum distance constraint to the D_11 shell of squared norm 4 will resolve the previous verification error and significantly increase the number of valid points.
# MECHANISM-1: The previous attempts incorrectly assumed that all pairs of points from the D_11 shell of squared norm 4 would automatically satisfy `min_dist^2 >= 4`. The D_11 lattice has minimum non-zero squared norm 2, meaning pairs exist with `||p_i - p_j||^2 = 2`. By explicitly filtering out such pairs using a greedy selection strategy that checks `||p_i - p_j||^2 >= 4`, we ensure the problem condition `max_norm <= min_dist` (which translates to `4 <= min_dist^2`) is met while maintaining `max_norm^2 = 4`.
# EXPECT-1: num_points > 22

# HYPOTHESIS-2: A greedy selection from the complete set of D_11 lattice points with squared norm 4 (Type 1 and Type 2) will yield a high number of points, potentially exceeding the benchmark.
# MECHANISM-2: The D_11 lattice shell of squared norm 4 is a well-structured and dense set of points within Z^11, containing a substantial number of candidates (5302 points). A greedy algorithm, specifically implemented with vectorized NumPy operations for efficiency, is a strong heuristic for selecting a large subset that satisfies the minimum distance constraint. This approach leverages the inherent packing efficiency of the D_11 lattice.
# EXPECT-2: combined_score > 0.8

import numpy as np
import itertools

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points in Z^11 such that 
    max(norm(p)) <= min(dist(p_i, p_j)).
    
    This strategy focuses on the D_11 lattice shell of squared L2 norm 4.
    For all points p in this set, ||p||^2 = 4, so max_i ||p_i|| = 2.
    Therefore, the condition becomes 2 <= min_{i!=j} ||p_i - p_j||,
    or equivalently, 4 <= min_{i!=j} ||p_i - p_j||^2.
    
    The D_11 lattice (points in Z^11 with an even coordinate sum) has a minimum 
    non-zero squared norm of 2 (e.g., (1,1,0,...)). It is crucial to filter out
    pairs of points whose difference has a squared norm of 2.
    """
    d = 11
    
    # Set a fixed random seed for reproducibility, though lexsort makes the greedy choice deterministic.
    np.random.seed(42) 

    # 1. Generate all candidate points with squared L2 norm = 4 that are in Z^11 and D_11.
    # D_11 is the set of points in Z^11 where the sum of coordinates is even.
    candidate_points_list = []

    # Type 1: Permutations of (+-2, 0, ..., 0)
    # Example: (2,0,0,0,0,0,0,0,0,0,0)
    # Squared L2 norm = 2^2 = 4.
    # Sum of coordinates is +-2, which is even. So these are in D_11.
    for i in range(d):
        p = np.zeros(d, dtype=np.int64)
        p[i] = 2
        candidate_points_list.append(p)
        p = np.zeros(d, dtype=np.int64)
        p[i] = -2
        candidate_points_list.append(p)
        
    # Type 2: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    # Example: (1,1,1,1,0,0,0,0,0,0,0)
    # Squared L2 norm = 1^2 * 4 = 4.
    # Sum of 4 coordinates, each being +-1: Let k be the number of -1s.
    # Sum = (4-k)*1 + k*(-1) = 4 - 2k. This is always an even number.
    # So, all these points are in D_11.
    for idx_set in itertools.combinations(range(d), 4):
        for signs in itertools.product([1, -1], repeat=4):
            p = np.zeros(d, dtype=np.int64)
            for i, s in zip(idx_set, signs):
                p[i] = s
            candidate_points_list.append(p)

    # Convert to NumPy array for efficient processing.
    candidate_points_np = np.array(candidate_points_list, dtype=np.int64)
    
    # Sort candidates for deterministic behavior of the greedy algorithm.
    # Lexicographical sort (sorting rows based on column values) ensures reproducibility.
    candidate_points_np = candidate_points_np[np.lexsort(candidate_points_np.T)]

    # 2. Greedy selection to satisfy the minimum distance constraint.
    # We need min_dist^2 >= 4.
    
    accepted_points_list = []

    for p_new in candidate_points_np:
        is_valid = True
        
        if len(accepted_points_list) > 0:
            # Convert current accepted points to a NumPy array for vectorized distance calculation.
            # This conversion happens in each iteration, but for up to ~600 points, it's feasible.
            current_accepted_np = np.array(accepted_points_list, dtype=np.int64)
            
            # Calculate squared Euclidean distances from p_new to all points already in the set.
            # (p_new - current_accepted_np) gives an array of differences (N_accepted, d).
            # Squaring and summing along axis=1 gives squared Euclidean distances (N_accepted,).
            sq_dists = np.sum((p_new - current_accepted_np)**2, axis=1)
            
            # If any squared distance is less than 4, p_new cannot be added to the set.
            if np.any(sq_dists < 4):
                is_valid = False
        
        if is_valid:
            accepted_points_list.append(p_new)

    return np.array(accepted_points_list, dtype=np.int64)

# EVOLVE-BLOCK-END