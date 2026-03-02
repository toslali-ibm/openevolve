import numpy as np

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points in Z^11 where max ||p|| <= min ||p_i - p_j||.
    We target the second shell of the D11 lattice (norm^2 = 4).
    The minimum distance between distinct points in this shell is sqrt(4) = 2.
    The maximum norm of any point is sqrt(4) = 2.
    This satisfies the constraint: 2 <= 2.
    """
    d = 11
    points = []

    # Strategy: Use vectors of squared norm 4 in Z^11.
    # Type 1: Permutations of (+-2, 0, 0, ..., 0)
    # Norm = sqrt(4) = 2.
    # Distance between (2,...) and (-2,...) is 4.
    # Distance between (2,...) and (0, 2, ...) is sqrt(8).
    for i in range(d):
        p1 = np.zeros(d, dtype=np.int64)
        p1[i] = 2
        points.append(p1)
        p2 = np.zeros(d, dtype=np.int64)
        p2[i] = -2
        points.append(p2)

    # Type 2: Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0)
    # To ensure min distance >= 2, we use a subset of the D11 shell.
    # The D_n lattice shell consists of vectors with even number of -1s (or even sum).
    # Total points in this shell for D11 is 2^(4-1) * comb(11, 4) = 8 * 330 = 2640.
    # However, we must ensure that for any p_i, p_j, ||p_i - p_j||^2 >= 4.
    
    # We use a simple greedy approach to prune the D11 shell to ensure the distance constraint.
    # In the D_n lattice, the squared distance between any two distinct points is at least 2.
    # To satisfy distance >= 2, we actually need ||p_i - p_j||^2 >= 4.
    # Since all our points have ||p||^2 = 4, ||p_i - p_j||^2 = ||p_i||^2 + ||p_j||^2 - 2(p_i . p_j)
    # ||p_i - p_j||^2 = 4 + 4 - 2(p_i . p_j) = 8 - 2(p_i . p_j).
    # We need 8 - 2(p_i . p_j) >= 4  =>  2(p_i . p_j) <= 4  =>  p_i . p_j <= 2.
    
    # Generate candidate vectors with exactly four +/- 1s.
    from itertools import combinations
    
    indices = list(combinations(range(d), 4))
    for idx in indices:
        # To keep the set large and satisfy p_i . p_j <= 2:
        # We can pick vectors with an even number of -1s.
        # For a fixed set of 4 indices, there are 8 such vectors.
        # To maximize points while maintaining distance, we use a subset.
        for i in range(16):
            bits = bin(i)[2:].zfill(4)
            vals = [1 if b == '0' else -1 for b in bits]
            # Parity check to stay in D11 (sum of coords is even)
            if sum(vals) % 2 == 0:
                p = np.zeros(d, dtype=np.int64)
                for bit_idx, pos in enumerate(idx):
                    p[pos] = vals[bit_idx]
                
                # Check distance against existing points
                # Optimized: p_i . p_j <= 2
                valid = True
                for existing in points:
                    if np.dot(existing, p) > 2:
                        valid = False
                        break
                if valid:
                    points.append(p)
                    
        if len(points) >= 650: # Break early if we exceed target significantly
            break

    return np.array(points)