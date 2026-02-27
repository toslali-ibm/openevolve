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
            
    # Type 2: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0) - Norm squared 4
    for indices in itertools.combinations(range(d), 4):
        for signs in itertools.product([1, -1], repeat=4):
            vec = np.zeros(d, dtype=np.int64)
            vec[list(indices)] = signs
            candidates.append(vec)
            
    # Type 3: The 11D version of the 'half-integer' shell, scaled to Z^11.
    # We look for vectors with norm squared 4. Already covered by Type 1 and 2.
    # To maximize, we use a deterministic greedy approach on the D11 shell.
    candidates = np.array(candidates)
    
    # Sort to prioritize Type 1 (sparser) vectors which are more 'efficient'
    norms = np.sum(candidates**2, axis=1)
    sparsity = np.count_nonzero(candidates, axis=1)
    # Sort by sparsity (primary) then by index to be deterministic
    idx = np.lexsort((np.arange(len(candidates)), sparsity))
    candidates = candidates[idx]
    
    selected = []
    # Use a set of tuples for faster lookup of distance constraints if possible, 
    # but with N~1000, a simple loop is fine.
    for c in candidates:
        is_valid = True
        for s in selected:
            # For norm-4 points, we need distance squared >= 4
            # dot product (c.s) must be <= (norm_c^2 + norm_s^2 - 4) / 2
            # Since norm_c^2 = norm_s^2 = 4, dot(c, s) <= 2
            if np.dot(c, s) > 2:
                is_valid = False
                break
        if is_valid:
            selected.append(c)
            
    return np.array(selected)


# EVOLVE-BLOCK-END
