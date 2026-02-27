# EVOLVE-BLOCK-START
import numpy as np

# Fix random seed for reproducibility
np.random.seed(42)


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points,11)
    """
    d = 11
    # Target norm-squared for points in the set.
    # We aim to construct a set where all points have this norm-squared,
    # making max_i ||p_i||^2 = radius_squared.
    # The problem constraint max_i ||p_i|| <= min_{i!=j} ||p_i - p_j||
    # then simplifies to radius_squared <= min_{i!=j} ||p_i - p_j||^2.
    radius_squared = 4 
    candidate_points = []

    # Generate points in Z^d on the shell with squared norm `radius_squared`
    # and satisfying the D_n lattice condition (sum of coordinates is even).

    # Type 1: ( +-2, 0, ..., 0 ) and its permutations.
    # Sum of coordinates is +-2 (even). Squared norm is 4.
    for i in range(d):
        p_plus = np.zeros(d, dtype=np.int64)
        p_plus[i] = 2
        candidate_points.append(p_plus)
        
        p_minus = np.zeros(d, dtype=np.int64)
        p_minus[i] = -2
        candidate_points.append(p_minus)

    # Type 2: ( +-1, +-1, +-1, +-1, 0, ..., 0 ) and its permutations.
    # These points have 4 non-zero entries, each being +1 or -1.
    # Squared norm is 1^2 * 4 = 4.
    # The sum of coordinates (number of +1s - number of -1s) will always be even
    # if the total number of non-zero entries (k=4) is even.
    import itertools
    for indices in itertools.combinations(range(d), 4): # Choose 4 positions for non-zero entries
        for signs_tuple in itertools.product([-1, 1], repeat=4): # Generate all 2^4 sign combinations
            point = np.zeros(d, dtype=np.int64)
            for i, idx in enumerate(indices):
                point[idx] = signs_tuple[i]
            candidate_points.append(point)
    
    # Convert to numpy array for efficient calculations
    candidate_points = np.array(candidate_points, dtype=np.int64)
    
    # Sort candidate points for reproducible greedy selection.
    # Sorting by tuple representation ensures lexicographical order.
    # This makes the greedy selection deterministic.
    candidate_points = np.array(sorted([tuple(p) for p in candidate_points]), dtype=np.int64)

    # Greedy filtering of points based on the problem's constraint:
    # max_i ||p_i||^2 <= min_{i!=j} ||p_i - p_j||^2
    # Since all candidate points have ||p||^2 = `radius_squared` (4),
    # the condition becomes: `radius_squared` <= min_{i!=j} ||p_i - p_j||^2.
    # This means for any two distinct points p1, p2 in the final set,
    # their squared distance ||p1 - p2||^2 must be at least `radius_squared`.
    
    filtered_points = []
    for p1 in candidate_points:
        is_valid_point = True
        for p2 in filtered_points:
            diff = p1 - p2
            dist_sq = np.sum(diff * diff)
            if dist_sq < radius_squared: # Check if the distance squared is less than the required minimum
                is_valid_point = False
                break
        if is_valid_point:
            filtered_points.append(p1)
    
    points = np.array(filtered_points, dtype=np.int64)
    return points


# EVOLVE-BLOCK-END
