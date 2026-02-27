# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Generating the full set of Type B candidates and using a randomized greedy selection will significantly increase the number of points.
# MECHANISM-1: Program 1's Type B generation was incomplete (missed half the sign combinations) and the greedy selection order was fixed. Generating all 5280 Type B points and randomizing their selection order allows for a more thorough exploration of valid subsets, potentially finding a larger configuration that satisfies the distance constraints.
# EXPECT-1: num_points > 230

# HYPOTHESIS-2: Optimizing the distance check by batching dot products and avoiding repeated array creation will improve performance.
# MECHANISM-2: Instead of repeatedly converting a list to a NumPy array or using `np.vstack` in a loop, pre-allocate a NumPy array for accepted points and fill it incrementally. This allows for efficient `np.dot` operations with a slice of the array, avoiding memory reallocations and speeding up the greedy selection process.
# EXPECT-2: combined_score > 0.4

# HYPOTHESIS-3: Exploring combinations of Type A and Type B points, rather than strictly separating them, could yield a denser packing.
# MECHANISM-3: The greedy selection processes all candidates (Type A and Type B) together after shuffling. This allows for interdependencies and a more globally optimized selection compared to processing Type A first, then Type B.
# EXPECT-3: num_points > 250

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
       Points with norm^2=2 (e.g., (1,1,0,...)) cannot be included because their pairwise distance can be sqrt(2) < 2.
    3. Use a randomized greedy algorithm to select points from the candidates. For any two selected points p1, p2, the condition ||p1 - p2||^2 >= 4 must hold. For points with ||p||^2 = 4, this is equivalent to the dot product condition: <p1, p2> <= 2.
    """
    d = 11
    
    # Set a fixed random seed for reproducibility
    np.random.seed(42)

    all_candidates = []

    # 1. Generate Type A points: (+/-2, 0, ..., 0)
    # These have L2 norm^2 = 2^2 = 4.
    for i in range(d):
        for val in [2, -2]:
            vec = np.zeros(d, dtype=np.int64)
            vec[i] = val
            all_candidates.append(vec) # Total 2 * 11 = 22 points

    # 2. Generate Type B points: (+/-1, +/-1, +/-1, +/-1, 0, ..., 0)
    # These have L2 norm^2 = 1^2 * 4 = 4.
    # Select 4 positions out of d
    for positions in itertools.combinations(range(d), 4):
        # Select signs for these 4 positions (2^4 = 16 combinations)
        for signs in itertools.product([-1, 1], repeat=4):
            vec = np.zeros(d, dtype=np.int64)
            for i, pos in enumerate(positions):
                vec[pos] = signs[i]
            all_candidates.append(vec) # Total 16 * C(11,4) = 16 * 330 = 5280 points

    # Convert all candidates to a NumPy array for efficient processing and shuffle for randomized greedy selection
    all_candidates_arr = np.array(all_candidates, dtype=np.int64)
    np.random.shuffle(all_candidates_arr)

    # Pre-allocate an array for accepted points to avoid repeated reallocations/conversions.
    # The total number of candidates is 5302. While not all will be accepted,
    # we choose a capacity significantly higher than the benchmark (593) to allow for growth.
    MAX_ACCEPTED_CAPACITY = 1000 
    accepted_points_storage = np.zeros((MAX_ACCEPTED_CAPACITY, d), dtype=np.int64)
    num_accepted = 0
    
    # Perform greedy selection
    for p in all_candidates_arr:
        # If no points accepted yet, or if current point is the first to be added
        if num_accepted == 0:
            is_valid = True
        else:
            # Use a view of the pre-allocated array for efficient dot product calculation.
            # This avoids creating new arrays inside the loop.
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