# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Reverting to the deterministic greedy selection strategy with conflict-degree sorting will restore the program's fitness to its previous peak.
# MECHANISM-1: The deterministic greedy approach, which prioritizes Type A vectors and sorts Type B vectors by their pre-calculated conflict degrees, is a proven heuristic for this type of Maximum Independent Set problem. It consistently outperformed randomized greedy approaches in previous attempts (scoring 403 vs 301 points), indicating its robustness in finding a large local optimum.
# EXPECT-1: num_points > 400

# HYPOTHESIS-2: When sorting Type B candidates by their conflict degree, using a secondary sorting key based on their aggregate compatibility (sum of absolute dot products) with Type A points will improve the selection order and potentially yield a larger set.
# MECHANISM-2: The primary sort by conflict degree (among Type B candidates) is a strong heuristic. However, for candidates with identical primary degrees, a secondary sort based on the sum of absolute dot products with Type A vectors (preferring lower sums) will select candidates that are "more orthogonal" or "less aligned" with the initial Type A basis, potentially leaving more "room" for subsequent Type B selections and leading to a denser packing.
# EXPECT-2: num_points > 403

# HYPOTHESIS-3: Maintaining efficient NumPy array operations, particularly pre-allocation and view usage, will ensure that the more complex sorting logic and larger candidate pool can be processed within practical time limits.
# MECHANISM-3: Avoiding dynamic array resizing (`np.vstack`) and ensuring that `current_accepted_view` is indeed a view (not a copy) for dot product calculations prevents performance degradation. This efficiency is critical for allowing sophisticated sorting heuristics without exceeding execution time constraints.
# EXPECT-3: eval_time < 0.25

import numpy as np
import itertools

def kissing_number11() -> np.ndarray:
    """
    Constructs a set of points in Z^11 where the maximum L2 norm of any point 
    is less than or equal to the minimum pairwise L2 distance between any two points.
    
    Strategy: 
    1. Identify candidate points in Z^11 with L2 norm squared equal to 4 (R=2).
       This implies the condition `max_i ||p_i|| = 2` and requires `min_{i!=j} ||p_i - p_j|| >= 2`.
       Which means `min_{i!=j} ||p_i - p_j||^2 >= 4`.
    2. For points with `||p||^2 = 4`, the condition `||p_i - p_j||^2 >= 4` simplifies to
       `8 - 2<p_i, p_j> >= 4`, or `<p_i, p_j> <= 2`.
    3. Generate all such candidates:
       - Type A: Vectors with one coordinate `+/-2` and others `0`. (2 * 11 = 22 points).
       - Type B: Vectors with four coordinates `+/-1` and others `0`. (16 * C(11, 4) = 5280 points).
    4. Implement a deterministic greedy approach:
       - Start with all Type A points.
       - Filter Type B points that are incompatible with any Type A points.
       - Calculate conflict degrees for the remaining Type B points (conflicts among themselves).
       - Calculate an aggregate compatibility score with Type A points for tie-breaking.
       - Sort these Type B points first by conflict degree (ascending), then by Type A compatibility score (ascending).
       - Greedily add sorted Type B points if compatible with the current accepted set.
    """
    d = 11
    
    # --- 1. Generate all candidates with L2 norm squared = 4 ---
    type_a_list = []
    # Type A: (+/-2, 0, ..., 0) - 22 points
    for i in range(d):
        for val in [2, -2]:
            vec = np.zeros(d, dtype=np.int64)
            vec[i] = val
            type_a_list.append(vec)
    type_a_arr = np.array(type_a_list, dtype=np.int64)

    type_b_list = []
    # Type B: (+/-1, +/-1, +/-1, +/-1, 0, ..., 0) - 5280 points
    for indices in itertools.combinations(range(d), 4):
        for signs in itertools.product([-1, 1], repeat=4):
            vec = np.zeros(d, dtype=np.int64)
            for i, idx in enumerate(indices):
                vec[idx] = signs[i]
            type_b_list.append(vec)
    type_b_arr = np.array(type_b_list, dtype=np.int64)

    # --- 2. Initialize accepted set with all Type A points ---
    # Max possible points is num_type_a + num_type_b = 22 + 5280 = 5302
    # Using a capacity of 1200, which is more than enough for observed results (403 points)
    # and leaves room for improvement, while being less than total candidates for memory efficiency.
    MAX_ACCEPTED_CAPACITY = 1200 
    accepted_points_storage = np.zeros((MAX_ACCEPTED_CAPACITY, d), dtype=np.int64)
    num_accepted = 0

    # Add all Type A points first
    for p_a in type_a_arr:
        accepted_points_storage[num_accepted] = p_a
        num_accepted += 1

    # --- 3. Filter Type B candidates for compatibility with Type A ---
    # Calculate dot products of all Type B with all Type A
    # Resulting matrix `dot_b_a` has shape (num_type_b, num_type_a)
    dot_b_a = type_b_arr @ type_a_arr.T
    
    # A Type B point is compatible with Type A if all its dot products with Type A are <= 2
    mask_b_compatible_with_a = np.all(dot_b_a <= 2, axis=1)
    filtered_b_candidates = type_b_arr[mask_b_compatible_with_a]
    
    # Also filter the dot_b_a matrix to match filtered_b_candidates for secondary sort key
    filtered_dot_b_a = dot_b_a[mask_b_compatible_with_a]

    # --- 4. Calculate conflict degrees for filtered Type B candidates ---
    # Calculate dot products among the filtered Type B candidates
    # Resulting matrix `dot_b_b` has shape (num_filtered_b, num_filtered_b)
    dot_b_b = filtered_b_candidates @ filtered_b_candidates.T
    
    # Conflict degree (primary sort key): number of other filtered Type B candidates it conflicts with
    # A point always has a dot product of 4 with itself (which is > 2), so subtract 1
    # to count only conflicts with *other* distinct points.
    # `degrees` has shape (num_filtered_b,)
    degrees = np.sum(dot_b_b > 2, axis=1) - 1 

    # --- 5. Calculate secondary sort key: aggregate compatibility with Type A points ---
    # Sum of absolute dot products with all Type A points. Lower sum indicates "more orthogonal" to Type A.
    # `sum_abs_dot_b_a` has shape (num_filtered_b,)
    sum_abs_dot_b_a = np.sum(np.abs(filtered_dot_b_a), axis=1)

    # --- 6. Sort filtered Type B candidates by their conflict degree (ascending), then by sum_abs_dot_b_a (ascending) ---
    # np.lexsort sorts by the last array in the tuple first, then the second to last, etc.
    sorted_indices = np.lexsort((sum_abs_dot_b_a, degrees))
    sorted_filtered_b = filtered_b_candidates[sorted_indices]

    # --- 7. Greedily add sorted Type B candidates ---
    for p_b in sorted_filtered_b:
        # Check compatibility with all currently accepted points (Type A + already accepted Type B)
        # Use a view of the pre-allocated array for efficient dot product calculation.
        current_accepted_view = accepted_points_storage[:num_accepted]
        
        # Calculate dot products with all accepted points
        dot_products_with_accepted = current_accepted_view @ p_b
        
        # If compatible and capacity allows, add the point
        if np.all(dot_products_with_accepted <= 2):
            if num_accepted < MAX_ACCEPTED_CAPACITY: 
                accepted_points_storage[num_accepted] = p_b
                num_accepted += 1
            else:
                # If capacity is reached, stop adding points.
                break 
            
    # Return only the filled portion of the pre-allocated array
    return accepted_points_storage[:num_accepted]
# EVOLVE-BLOCK-END