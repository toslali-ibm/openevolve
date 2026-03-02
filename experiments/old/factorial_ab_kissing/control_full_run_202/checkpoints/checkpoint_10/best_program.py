import numpy as np
from itertools import combinations

def kissing_number11() -> np.ndarray:
    """
    Constructs a set of points in Z^11 where max ||p_i|| <= min ||p_i - p_j||.
    
    Strategy:
    We use the second shell of the D11 lattice (squared norm 4).
    Points in this shell have the form:
    1. Permutations of (+-2, 0, ..., 0): 2 * 11 = 22 points.
    2. Permutations of (+-1, +-1, +-1, +-1, 0, ..., 0) with an even number of minus signs.
    
    To satisfy max_norm <= min_dist, we need:
    max ||p_i||^2 = 4 <= min ||p_i - p_j||^2.
    Since ||p_i - p_j||^2 = ||p_i||^2 + ||p_j||^2 - 2 <p_i, p_j>,
    and ||p_i||^2 = ||p_j||^2 = 4, we need 8 - 2 <p_i, p_j> >= 4,
    which simplifies to <p_i, p_j> <= 2.
    
    We can achieve a large set by selecting vectors with exactly four 1s and no -1s.
    For any two such vectors, the dot product is the number of shared '1' positions.
    If we pick vectors with four 1s, the dot product can be 0, 1, 2, 3, or 4.
    To ensure dot product <= 2, any two vectors must share at most 2 indices.
    This is a problem of finding a constant weight code (n=11, w=4, d=4).
    """
    d = 11
    points = []
    
    # 1. Add vectors of type (+-2, 0, ..., 0)
    # Pairwise dot products are 0 or -4, satisfying <p_i, p_j> <= 2.
    for i in range(d):
        p_pos = np.zeros(d, dtype=np.int64)
        p_neg = np.zeros(d, dtype=np.int64)
        p_pos[i] = 2
        p_neg[i] = -2
        points.append(p_pos)
        points.append(p_neg)
        
    # 2. Add vectors of type (1, 1, 1, 1, 0, ..., 0)
    # We use a greedy approach to find a large subset where no two vectors 
    # overlap in more than 2 positions.
    all_quads = list(combinations(range(d), 4))
    selected_indices = []
    
    for quad in all_quads:
        quad_set = set(quad)
        valid = True
        for existing in selected_indices:
            # Intersection size is the dot product for (0,1) vectors
            if len(quad_set.intersection(existing)) > 2:
                valid = False
                break
        if valid:
            selected_indices.append(quad_set)
            p = np.zeros(d, dtype=np.int64)
            for idx in quad:
                p[idx] = 1
            points.append(p)
            
    # 3. Add vectors of type (-1, -1, -1, -1, 0, ..., 0)
    # A vector p and -p have dot product -4, which is <= 2.
    # Two negative vectors -p and -q have dot product <p, q>.
    # So we can simply add the negatives of all selected Type 2 points.
    type2_count = len(selected_indices)
    for i in range(22, 22 + type2_count):
        points.append(-points[i])

    return np.array(points)

if __name__ == "__main__":
    pts = kissing_number11()
    # Verification logic (internal)
    norms_sq = np.sum(pts**2, axis=1)
    max_norm_sq = np.max(norms_sq)
    
    min_dist_sq = float('inf')
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            dist_sq = np.sum((pts[i] - pts[j])**2)
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
    
    print(f"Number of points: {len(pts)}")
    print(f"Max squared norm: {max_norm_sq}")
    print(f"Min squared distance: {min_dist_sq}")
    print(f"Valid: {max_norm_sq <= min_dist_sq}")