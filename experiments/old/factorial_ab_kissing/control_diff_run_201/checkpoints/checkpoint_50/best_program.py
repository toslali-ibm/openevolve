# EVOLVE-BLOCK-START
import numpy as np


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points,11)
    """
    d = 11
    # We seek a set S where max ||p||^2 <= min ||p_i - p_j||^2.
    # Let's target norm squared 4. Then we need pairwise distance squared >= 4.
    # The shell of the D_11 lattice with norm squared 4 consists of:
    # 1. Permutations of (+-2, 0, ..., 0) -> 2 * 11 = 22 points.
    # 2. Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0) -> 2^4 * binom(11, 4) = 5280 points.
    
    # To satisfy dist^2 >= 4, we observe that for any two points x, y with ||x||^2=||y||^2=4:
    # ||x-y||^2 = ||x||^2 + ||y||^2 - 2<x,y> = 8 - 2<x,y>.
    # We need 8 - 2<x,y> >= 4  =>  2<x,y> <= 4  =>  <x,y> <= 2.
    
    # A known optimal configuration for this is the set of vectors in {0, 1}^11 
    # with exactly four 1s (weight 4) such that they form a constant weight code.
    # However, to maximize count, we use the vectors of the form (+-1, +-1, +-1, +-1, 0...)
    # but restricted to a specific structure to ensure <x, y> <= 2.
    
    # Fixed seed for reproducibility
    np.random.seed(42) 
    import random
    random.seed(42)

    points_list = [] 

    # Type 1: (+-2, 0, ..., 0)
    # These have norm squared 4.
    for i in range(d):
        p1 = np.zeros(d, dtype=np.int64)
        p2 = np.zeros(d, dtype=np.int64)
        p1[i] = 2
        p2[i] = -2
        points_list.append(p1)
        points_list.append(p2)
        
    # Convert to numpy array for efficient operations
    current_points_array = np.array(points_list, dtype=np.int64)
    
    # Type 2: Permutations of (+-1, +-1, +-1, +-1, 0, ...)
    # These also have norm squared 4.
    # We need <x,y> <= 2 for any two points x,y in the final set.
    
    import itertools
    candidate_indices = list(itertools.combinations(range(d), 4))
    
    # Shuffle candidates to improve greedy selection diversity
    random.shuffle(candidate_indices) # Use random.shuffle for lists

    for idxs in candidate_indices:
        # Iterate over all 2^4 sign combinations (removing the heuristic)
        for signs_tuple in itertools.product([1, -1], repeat=4):
            p = np.zeros(d, dtype=np.int64)
            p[list(idxs)] = signs_tuple # Assign signs to selected indices
            
            # Check against all existing points in current_points_array
            # Condition: <x,y> <= 2
            dot_products = np.dot(current_points_array, p)
            
            # If any dot product is > 2, the point is not valid
            if np.any(dot_products > 2):
                continue # Skip this candidate point
            
            # If all dot products are <= 2, the point is valid, add it
            current_points_array = np.vstack([current_points_array, p])
            
    return current_points_array


# EVOLVE-BLOCK-END
