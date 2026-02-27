# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Generating the complete set of Type B candidates (vectors with four +/-1s and rest zeros) provides a richer pool for greedy selection, leading to a larger final set of points.
# MECHANISM-1: The previous code arbitrarily restricted the Type B candidate generation by fixing the sign of the first non-zero component (`s1=1`). This removed half of the symmetric points from consideration. Including all 2^4 * C(11,4) = 5280 possible points ensures that the greedy algorithm has access to the full shell of `norm^2=4` vectors with four non-zero entries, maximizing its chance to find a larger valid subset that satisfies the distance constraint.
# EXPECT-1: num_points > 230
# HYPOTHESIS-2: Applying a deterministic sorting order to the Type B candidates before greedy selection can improve the size of the resulting point set.
# MECHANISM-2: Greedy algorithms are sensitive to the order in which candidates are processed. A consistent, non-arbitrary sorting order (e.g., lexicographical) provides a structured way to explore the search space, potentially leading to a locally optimal solution that is larger than one found with an arbitrary or partial order. This helps ensure that "less conflicting" or "more central" points are considered earlier.
# EXPECT-2: num_points > 230

import numpy as np
from itertools import combinations, product

def kissing_number11() -> np.ndarray:
    """
    Constructs a set of points in Z^11 where the maximum L2 norm of any point 
    is less than or equal to the minimum pairwise L2 distance between any two points.
    
    Strategy: 
    The problem condition is max_i ||p_i|| <= min_{i!=j} ||p_i - p_j||.
    If we aim for a set where all points have ||p_i||^2 = 4, then max_i ||p_i|| = 2.
    This implies we need min_{i!=j} ||p_i - p_j|| >= 2, or min_{i!=j} ||p_i - p_j||^2 >= 4.

    1. We consider points in Z^11 with L2 norm squared equal to 4:
       - Type A: (+/-2, 0, ..., 0). These 2 * 11 = 22 points have norm^2 = 4.
       - Type B: (+/-1, +/-1, +/-1, +/-1, 0, ..., 0). These 2^4 * C(11, 4) = 5280 points have norm^2 = 4.
       (Points with norm^2 < 4, like (1,1,0,...) with norm^2=2, would conflict with Type A/B points
       by having dist^2 < 4, so they cannot be included if max_norm^2 = 4 and min_dist^2 = 4.)
    2. We use a greedy approach to select a maximal subset of these candidates such that
       all pairwise squared distances are >= 4. For any two points p1, p2 with ||p1||^2=4 and ||p2||^2=4,
       the condition ||p1-p2||^2 >= 4 simplifies to 8 - 2*<p1, p2> >= 4, which means <p1, p2> <= 2.
    """
    d = 11
    accepted_points_list = []

    # 1. Generate Type A candidates: (+/-2, 0, ..., 0)
    # These 22 points all have norm^2 = 4. They are mutually compatible (min_dist^2 >= 8).
    for i in range(d):
        for val in [2, -2]:
            vec = np.zeros(d, dtype=np.int64)
            vec[i] = val
            accepted_points_list.append(vec)

    # Initialize accepted_stack with Type A points for efficient dot product calculations
    if accepted_points_list:
        accepted_stack = np.array(accepted_points_list)
    else:
        accepted_stack = np.empty((0, d), dtype=np.int64)

    # 2. Generate Type B candidates: (+/-1, +/-1, +/-1, +/-1, 0, ..., 0)
    # This generates all 2^4 * C(11,4) = 5280 points of this type.
    potential_B_candidates = []
    for indices in combinations(range(d), 4):
        for signs in product([-1, 1], repeat=4):
            vec = np.zeros(d, dtype=np.int64)
            for i, idx in enumerate(indices):
                vec[idx] = signs[i]
            potential_B_candidates.append(vec)

    # HYPOTHESIS-2: Sort candidates to improve greedy selection
    # Lexicographical sort provides a deterministic and reproducible order.
    potential_B_candidates.sort(key=lambda x: tuple(x))

    # 3. Greedy filter for Type B candidates
    # Add points if they satisfy the distance constraint with all already accepted points.
    # The condition is <p_candidate, p_accepted> <= 2 for all p_accepted in accepted_stack.
    for p_candidate in potential_B_candidates:
        # If accepted_stack is empty, just add the point (should not happen as Type A points are added first)
        if accepted_stack.shape[0] == 0:
            accepted_points_list.append(p_candidate)
            accepted_stack = np.vstack([accepted_stack, p_candidate])
            continue

        # Check dot product condition with all currently accepted points
        dot_products = np.dot(accepted_stack, p_candidate)
        if np.all(dot_products <= 2):
            accepted_points_list.append(p_candidate)
            accepted_stack = np.vstack([accepted_stack, p_candidate])
            # No early break; maximize the set size.

    return np.array(accepted_points_list)

# EVOLVE-BLOCK-END