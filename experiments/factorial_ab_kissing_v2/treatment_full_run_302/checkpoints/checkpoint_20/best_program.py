# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Using the first shell of the D_11 root lattice provides a structured set of points with guaranteed minimum pairwise distances of sqrt(2).
# MECHANISM-1: The D_11 root lattice's first shell has high symmetry and inherent minimum distance properties, ensuring valid points satisfy the condition max ||p|| <= min ||p_i - p_j||.
# EXPECT-1: num_points > 220

# HYPOTHESIS-2: Extending to higher shells of the D_11 lattice while filtering points by pairwise distance constraints will increase the size of the valid set.
# MECHANISM-2: Higher shells contain points with larger norms, but careful filtering ensures only points satisfying the condition are added to the set.
# EXPECT-2: num_points > 400

# HYPOTHESIS-3: Using symmetry operations to generate additional valid points efficiently will further maximize the set size.
# MECHANISM-3: Symmetry operations preserve the distances and norms of lattice points, allowing for efficient generation of valid points without recomputation.
# EXPECT-3: combined_score > 0.8

import numpy as np

def generate_d11_shell(n_nonzero: int, d: int) -> np.ndarray:
    """
    Generates a shell of the D_11 lattice with a given number of nonzero ±1 entries.

    Args:
        n_nonzero: Number of ±1 entries in each point.
        d: Dimension of the space (11 for D_11).

    Returns:
        shell: np.ndarray of shape (num_points, d), points in the shell.
    """
    from itertools import combinations, product
    shell = []
    for indices in combinations(range(d), n_nonzero):
        for signs in product([-1, 1], repeat=n_nonzero):
            point = np.zeros(d, dtype=int)
            point[list(indices)] = signs
            shell.append(point)
    return np.array(shell)

def filter_points(points: np.ndarray, existing_points: np.ndarray) -> np.ndarray:
    """
    Filters a set of candidate points to ensure the distance constraint is satisfied with existing points.

    Args:
        points: np.ndarray of shape (num_candidates, d), candidate points to filter.
        existing_points: np.ndarray of shape (num_existing, d), current valid points.

    Returns:
        filtered_points: np.ndarray of valid points satisfying the distance constraint.
    """
    filtered_points = []
    for point in points:
        if len(existing_points) == 0:
            filtered_points.append(point)
        else:
            # Check if the new point satisfies the distance constraint with all existing points
            distances = np.linalg.norm(existing_points - point, axis=1)
            if np.min(distances) >= np.linalg.norm(point):
                filtered_points.append(point)
    return np.array(filtered_points)

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm
    is less than or equal to the minimum pairwise distance between any two points, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points, 11)
    """
    d = 11  # Dimension
    valid_points = []
    
    # Start with the first shell (points with 2 nonzero entries ±1)
    shell_1 = generate_d11_shell(2, d)
    valid_points = shell_1
    
    # Iteratively add higher shells
    for n_nonzero in range(4, d + 1, 2):  # Even number of nonzero entries for D_11 lattice
        shell = generate_d11_shell(n_nonzero, d)
        filtered_shell = filter_points(shell, valid_points)
        valid_points = np.vstack((valid_points, filtered_shell)) if len(filtered_shell) > 0 else valid_points

    return np.array(valid_points)

# Run the function and store the result for evaluation
points = kissing_number11()
print(f"Number of points: {len(points)}")
# EVOLVE-BLOCK-END