# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Utilizing the shells of the D_11 lattice (even-sum integers) will provide a high density of points with a fixed norm.
# MECHANISM-1: The D_11 lattice consists of vectors in Z^11 where the sum of coordinates is even. The shortest vectors have norm squared 2 (220 points) and the next shell has norm squared 4. By selecting vectors with a specific norm squared (e.g., 4) that also satisfy the distance constraint, we exploit the structured packing of the lattice.
# EXPECT-1: num_points > 400
# HYPOTHESIS-2: Filtering vectors with norm squared 4 and 6 from Z^11 will allow a larger set where max_norm <= min_dist.
# MECHANISM-2: If we pick points with norm squared K, the distance squared between any two points must be >= K. For Z^11, vectors with norm squared 4 (like (+-2, 0...)) or (1, 1, 1, 1, 0...) provide a large pool to greedily select from.
# EXPECT-2: num_points > 593
import numpy as np


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points in Z^11 using the D_11 lattice structure
    and greedy selection to maximize the set size while maintaining max_norm <= min_dist.
    """
    import itertools
    d = 11
    candidates = []
    
    # All vectors selected will have norm squared = 4.
    # Therefore, the condition max_norm <= min_dist becomes 2 <= min_dist, or 4 <= min_dist^2.
    
    # Type 1: Permutations of (+-2, 0, 0, ..., 0)
    for i in range(d):
        for val in [2, -2]:
            vec = np.zeros(d, dtype=np.int64)
            vec[i] = val
            candidates.append(vec)
            
    # Type 2: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    for indices in itertools.combinations(range(d), 4):
        for signs in itertools.product([1, -1], repeat=4):
            vec = np.zeros(d, dtype=np.int64)
            vec[list(indices)] = signs
            candidates.append(vec)
            
    # Type 3: Permutations of (+-2, +-1, +-1, 0, ..., 0) - Norm squared 6
    # Note: We only add these if they help, but to stay safe and fast, we'll 
    # focus on a structured subset of the weight-4 shell first.
    
    candidates = np.array(candidates)
    # Sort candidates by a combination of absolute sum and variance to 
    # prioritize 'spread out' vectors which often pack better greedily.
    norms = np.sum(np.abs(candidates), axis=1)
    sort_idx = np.lexsort((candidates[:, 10], candidates[:, 0], norms))
    candidates = candidates[sort_idx]
    
    selected = []
    # Use a set of tuples for faster lookups or a matrix for vectorization
    if len(candidates) > 0:
        selected.append(candidates[0])
    
    for i in range(1, len(candidates)):
        c = candidates[i]
        # Vectorized distance check against already selected points
        # Using squared distance >= 4
        diffs = np.array(selected) - c
        dist_sq = np.sum(diffs**2, axis=1)
        if np.all(dist_sq >= 4):
            selected.append(c)
            
    return np.array(selected)


# EVOLVE-BLOCK-END
