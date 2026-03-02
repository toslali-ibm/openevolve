# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Sorting the candidates by their sparsity (number of non-zero coordinates) before greedy selection will improve the final count of valid points.
# MECHANISM-1: In greedy selection, the order of processing candidates matters significantly. Prioritizing sparser points (e.g., `(+-2,0,...)` which have 1 non-zero coordinate, before `(+-1,+-1,+-1,+-1,0,...)` which have 4 non-zero coordinates) might allow these simpler, potentially more "isolated" points to be chosen first. This could lead to a more efficient packing by leaving more "space" for subsequent, denser points, thus improving the overall packing density found by the greedy approach.
# EXPECT-1: num_points > 292

import numpy as np
import itertools

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points in Z^11 using candidates from the D_11 lattice's squared norm 4 shell
    and greedy selection to maximize the set size while maintaining max_norm <= min_dist.
    """
    d = 11
    candidates = []
    
    # All vectors selected will have norm squared = 4.
    # Therefore, the condition max_norm <= min_dist becomes 2 <= min_dist, or 4 <= min_dist^2.
    
    # Type 1: Permutations of (+-2, 0, 0, ..., 0)
    # These are in D_11 as the sum of coordinates is +-2 (even). Sparsity = 1.
    for i in range(d):
        for val in [2, -2]:
            vec = np.zeros(d, dtype=np.int64)
            vec[i] = val
            candidates.append(vec)
            
    # Type 2: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    # These are also in D_11 as the sum of 4 coordinates (each +-1) is always even. Sparsity = 4.
    for indices in itertools.combinations(range(d), 4):
        for signs in itertools.product([1, -1], repeat=4):
            vec = np.zeros(d, dtype=np.int64)
            for i_idx, s_val in zip(indices, signs): # Renamed loop vars to avoid confusion with outer 'i'
                vec[i_idx] = s_val
            candidates.append(vec)

    candidates_np = np.array(candidates)
    
    # Apply Hypothesis 1: Sort candidates by sparsity (number of non-zero elements)
    # Sparsity for Type 1 points is 1, for Type 2 points is 4. So Type 1 points will come first.
    sparsities = np.count_nonzero(candidates_np, axis=1)
    sorted_indices = np.argsort(sparsities)
    candidates_np = candidates_np[sorted_indices]
    
    # No random shuffle, as candidates are now deterministically sorted.
    
    selected = []
    # Greedy filtering: only keep points that are at least distance sqrt(4) apart
    # This implies min_dist_squared >= 4
    for c in candidates_np:
        is_valid = True
        for s in selected:
            # L2 distance squared
            if np.sum((c - s)**2) < 4:
                is_valid = False
                break
        if is_valid:
            selected.append(c)
            
    return np.array(selected)


# EVOLVE-BLOCK-END
