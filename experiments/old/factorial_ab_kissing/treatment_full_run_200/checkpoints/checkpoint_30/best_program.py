# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Prioritizing candidates with fewer conflicts will lead to a larger valid set.
# MECHANISM-1: A standard greedy algorithm for Maximum Independent Set problems often performs better when nodes with lower degrees (fewer conflicts) are considered first. By selecting points that are 'less constrained' by their neighbors in the conflict graph, we leave more room for subsequent points to be added, potentially leading to a larger overall set.
# EXPECT-1: num_points > 300

# HYPOTHESIS-2: Leveraging the structure of Type A points (higher sparsity) by placing them at the beginning of the selection sequence, followed by conflict-ordered Type B points, will improve the final count.
# MECHANISM-2: Type A points (e.g., (2,0,...)) have very specific and sparse non-zero elements, resulting in fewer potential conflicts with other points compared to denser Type B points. Placing them first ensures they are included, as they are often compatible with many other points, providing a strong foundation for the set.
# EXPECT-2: num_points > 350

# HYPOTHESIS-3: Increasing the `MAX_ACCEPTED_CAPACITY` will prevent premature termination and allow the greedy algorithm to explore larger potential sets.
# MECHANISM-3: The current `MAX_ACCEPTED_CAPACITY` of 1000, while larger than the benchmark, might still be too restrictive if the optimal set is significantly larger or if the greedy process temporarily finds a path to a larger set that exceeds this limit. A higher capacity ensures the algorithm can continue adding points as long as they are valid.
# EXPECT-3: combined_score > 0.5

import numpy as np
import itertools

def kissing_number11() -> np.ndarray:
    """
    Constructs a set of points in Z^11 where the maximum L2 norm of any point 
    is less than or equal to the minimum pairwise L2 distance between any two points.
    
    Strategy: 
    1. Define the problem constraints: Let R be the common value. We need max_i ||p_i|| <= R and min_{i!=j} ||p_i - p_j|| >= R.
       If we select points such that ||p_i|| = 2 for all p_i (i.e., ||p_i||^2 = 4), then max_i ||p_i|| = 2.
       This implies R=2, and thus we need min_{i!=j} ||p_i - p_j||^2 >= 4.
    2. Generate candidate points in Z^11 with L2 norm squared equal to 4:
       - Type A: Vectors with one coordinate +/-2 and all others 0. (e.g., (2,0,0,...))
       - Type B: Vectors with four coordinates +/-1 and all others 0. (e.g., (1,1,1,1,0,...))
       Points with norm^2=2 (e.g., (1,1,0,...)) cannot be included because their maximum norm would be sqrt(2), which would require min_dist^2 >= 2, a different problem.
    3. Use a deterministic greedy algorithm to select points from the candidates. For any two selected points p1, p2, the condition ||p1 - p2||^2 >= 4 must hold. For points with ||p||^2 = 4, this is equivalent to the dot product condition: <p1, p2> <= 2.
    4. The greedy selection order is optimized by prioritizing Type A points, then sorting Type B points by their pre-calculated number of conflicts with other candidates.
    """
    d = 11
    
    # Set a fixed random seed for reproducibility (used for potential future randomization, currently deterministic)
    np.random.seed(42)

    all_candidates = []

    # 1. Generate Type A points: (+/-2, 0, ..., 0)
    # These have L2 norm^2 = 2^2 = 4.
    # Total 2 * 11 = 22 points
    for i in range(d):
        for val in [2, -2]:
            vec = np.zeros(d, dtype=np.int64)
            vec[i] = val
            all_candidates.append(vec) 
    
    num_type_A = len(all_candidates) # Store count for later prioritization

    # 2. Generate Type B points: (+/-1, +/-1, +/-1, +/-1, 0, ..., 0)
    # These have L2 norm^2 = 1^2 * 4 = 4.
    # Total 16 * C(11,4) = 16 * 330 = 5280 points
    for positions in itertools.combinations(range(d), 4):
        for signs in itertools.product([-1, 1], repeat=4):
            vec = np.zeros(d, dtype=np.int64)
            for i, pos in enumerate(positions):
                vec[pos] = signs[i]
            all_candidates.append(vec)

    # Convert all candidates to a NumPy array for efficient processing
    all_candidates_arr = np.array(all_candidates, dtype=np.int64)
    num_candidates = len(all_candidates_arr)

    # Calculate conflict scores for each candidate (number of other candidates it conflicts with)
    # A conflict occurs if <p_i, p_j> > 2.
    # Calculate the dot product matrix for all candidate pairs.
    dot_product_matrix = all_candidates_arr @ all_candidates_arr.T
    
    # Count conflicts: for each candidate, sum how many other candidates it conflicts with.
    # We subtract 1 because a point always has a dot product of 4 with itself (4 > 2 is True).
    conflict_scores = np.sum(dot_product_matrix > 2, axis=1) - 1 

    # Create an array of indices to sort candidates.
    # Implement HYPOTHESIS-2: Prioritize Type A points.
    type_A_indices = np.arange(num_type_A)
    type_B_indices = np.arange(num_type_A, num_candidates)

    # Implement HYPOTHESIS-1: Sort Type B candidates by their conflict scores in ascending order.
    # Candidates with fewer conflicts are considered first.
    sorted_type_B_indices = type_B_indices[np.argsort(conflict_scores[type_B_indices])]
    
    # Combine the sorted indices: Type A first, then sorted Type B
    sorted_candidate_indices = np.concatenate((type_A_indices, sorted_type_B_indices))
    
    # Reorder candidates based on the new sorted indices
    sorted_candidates_arr = all_candidates_arr[sorted_candidate_indices]

    # Pre-allocate an array for accepted points to avoid repeated reallocations/conversions.
    # Implement HYPOTHESIS-3: Increase capacity to prevent premature termination.
    MAX_ACCEPTED_CAPACITY = 1200 
    accepted_points_storage = np.zeros((MAX_ACCEPTED_CAPACITY, d), dtype=np.int64)
    num_accepted = 0
    
    # Perform greedy selection using the optimized order
    for p in sorted_candidates_arr:
        if num_accepted == 0:
            is_valid = True
        else:
            # Use a view of the pre-allocated array for efficient dot product calculation.
            current_accepted_view = accepted_points_storage[:num_accepted]
            
            # Calculate dot products with all currently accepted points.
            # For points with ||p||^2 = 4, ||p1 - p2||^2 >= 4 is equivalent to <p1, p2> <= 2.
            dot_products = np.dot(current_accepted_view, p)
            
            # Check if all dot products satisfy the condition
            is_valid = np.all(dot_products <= 2)

        if is_valid:
            # If the point is valid and there's capacity, add it to the accepted set.
            if num_accepted < MAX_ACCEPTED_CAPACITY:
                accepted_points_storage[num_accepted] = p
                num_accepted += 1
            else:
                # If capacity is reached, break early. We have a sufficiently large set.
                break 
            
    # Return only the filled portion of the pre-allocated array
    return accepted_points_storage[:num_accepted]

# EVOLVE-BLOCK-END