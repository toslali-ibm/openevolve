# EVOLVE-BLOCK-START
import numpy as np


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points,11)
    """
    d = 11
    candidates = []

    # D11 Lattice Shell 1: Norm squared = 2
    # Vectors with two +/- 1s and nine 0s. Total: 4 * binom(11, 2) = 440
    for i in range(d):
        for j in range(i + 1, d):
            for s1 in [1, -1]:
                for s2 in [1, -1]:
                    vec = np.zeros(d, dtype=np.int64)
                    vec[i] = s1
                    vec[j] = s2
                    candidates.append(vec)
    
    # D11 Lattice Shell 2 (Partial): Norm squared = 4
    # To keep min_dist >= 2, we can add vectors with norm 2 (like (+/-2, 0...))
    # or (+/-1, +/-1, +/-1, +/-1, 0...). 
    # Let's add the (+/-2, 0, ..., 0) vectors. Total: 2 * 11 = 22
    for i in range(d):
        for s in [1, -1]:
            vec = np.zeros(d, dtype=np.int64)
            vec[i] = 2 * s
            candidates.append(vec)

    # Shell 2 (Partial): (+/-1, +/-1, +/-1, +/-1, 0...) is too many to check greedily 
    # without care, but we can add them if they maintain the min_dist >= 2.
    # For now, let's use a greedy filter to maximize the set.
    
    points = np.array(candidates)
    # The current set has max_norm = 2.0 and min_dist = sqrt(2). 
    # We must filter to ensure min_dist >= max_norm.
    # If we restrict to norm squared = 4, then min_dist must be >= 2.
    
    # Improved Strategy: Use vectors of norm squared 4 where pairwise dist squared >= 4.
    final_points = []
    # Permutations of (2, 0, ..., 0)
    for i in range(d):
        for s in [2, -2]:
            vec = np.zeros(d, dtype=np.int64)
            vec[i] = s
            final_points.append(vec)
            
    # Permutations of (1, 1, 1, 1, 0, ..., 0) with even number of -1s (D11 shell)
    # This is a large set, we use a subset to ensure min_dist.
    import itertools
    count = 0
    for indices in itertools.combinations(range(d), 4):
        for signs in itertools.product([1, -1], repeat=4):
            if sum(signs) % 2 == 0: # Half-shell to maintain distance
                vec = np.zeros(d, dtype=np.int64)
                vec[list(indices)] = signs
                # Check distance to existing points
                is_valid = True
                v_np = np.array(vec)
                for p in final_points:
                    if np.sum((v_np - p)**2) < 4:
                        is_valid = False
                        break
                if is_valid:
                    final_points.append(v_np)
        if len(final_points) > 650: # Safety break
            break

    return np.array(final_points)


# EVOLVE-BLOCK-END
