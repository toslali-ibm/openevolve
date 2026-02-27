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
    # These are part of the D_11 lattice second shell or related structures.
    # We iterate through combinations to find points with norm squared 4.
    for indices in itertools.combinations(range(d), 4):
        for signs in itertools.product([1, -1], repeat=4):
            vec = np.zeros(d, dtype=np.int64)
            vec[list(indices)] = signs
            candidates.append(vec)

    candidates = np.array(candidates)
# HYPOTHESIS-1: Sorting candidate points by L1 norm (ascending) then lexicographically before greedy selection will increase the number of selected points.
# MECHANISM-1: A deterministic sorting order, especially one that places 'simpler' or 'sparser' vectors (lower L1 norm) first, can lead to a better greedy selection. These 'simpler' vectors might occupy less "space" and leave more options for subsequent, more complex vectors, potentially allowing a larger overall set to be constructed compared to random selection.
# EXPECT-1: num_points > 300

    # Sort candidates by L1 norm, then lexicographically for reproducibility and potentially better greedy selection.
    # Create a list of (L1_norm, vector_as_tuple, original_index) for sorting.
    # This allows stable sorting and retrieval of original vectors.
    sort_data = []
    for i, cand in enumerate(candidates):
        sort_data.append((np.sum(np.abs(cand)), tuple(cand), i))
    
    # Sort the list. Python's sort is stable and sorts by elements of the tuple in order.
    sort_data.sort()
    
    # Reconstruct the candidates array in the new sorted order.
    candidates = np.array([candidates[idx] for _, _, idx in sort_data])
    
    selected = []
    # Greedy filtering: only keep points that are at least distance sqrt(4) apart
    for c in candidates:
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
