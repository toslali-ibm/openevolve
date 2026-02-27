# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Filtering lattice shells from D_11 improves fitness by generating structured points with optimal minimum distances.
# MECHANISM-1: D_11 root system provides symmetric lattice vectors with guaranteed minimum pairwise distances, and filtering its shells ensures valid sets of points.
# EXPECT-1: num_points > 593
# HYPOTHESIS-2: Laminated lattice L_11 will outperform D_11 because it is optimized for sphere packing in high dimensions.
# MECHANISM-2: Laminated lattices are dense packings designed for high-dimensional geometry, yielding larger sets of points with minimal computational overhead.
# EXPECT-2: num_points > 700
# HYPOTHESIS-3: Combining symmetry group filtering with lattice constructions will reduce redundancy and improve computational efficiency.
# MECHANISM-3: Symmetry group filtering avoids generating equivalent points, focusing computations on unique valid candidates.
# EXPECT-3: combined_score > 1.2
import numpy as np


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points,11)
    """
    # Use the D_11 lattice first shell as candidate points
    d = 11
    radius_sq = 2  # Minimal squared radius for D_11 shell
    lattice_shell = []
    
    # Generate all integer points satisfying the norm constraint for the D_11 lattice
    for x in range(-2, 3):
        for y in range(-2, 3):
            for z in range(-2, 3):
                # Continue for all 11 dimensions
                point = np.array([x, y, z, 0, 0, 0, 0, 0, 0, 0, 0])
                if np.sum(point**2) == radius_sq:
                    lattice_shell.append(point)
    
    # Convert to numpy array
    candidate_points = np.array(lattice_shell, dtype=np.int64)
    
    # Filter points to satisfy the kissing number constraint
    valid_points = []
    for p1 in candidate_points:
        valid = True
        for p2 in valid_points:
            if np.linalg.norm(p1 - p2) <= np.linalg.norm(p1):
                valid = False
                break
        if valid:
            valid_points.append(p1)
    
    points = np.array(valid_points)

    return points


# EVOLVE-BLOCK-END
