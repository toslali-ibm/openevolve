import numpy as np
from itertools import combinations

def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum norm
    is smaller than their minimum pairwise distance, aiming to maximize the number of points.

    Returns:
        points: np.ndarray of shape (num_points, 11)
    """
    d = 11
    
    # Generate points in the D_11 lattice with ||p||^2 <= 4
    # D_n lattice consists of points in Z^n such that the sum of coordinates is even
    def generate_d11_lattice_shell(max_norm_squared):
        lattice_points = []
        for indices in combinations(range(d), 2):
            for signs in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                point = np.zeros(d, dtype=int)
                point[indices[0]] = signs[0]
                point[indices[1]] = signs[1]
                if np.sum(point) % 2 == 0:
                    lattice_points.append(point)
        return np.array(lattice_points)
    
    # Generate the shell of points with ||p||^2 = 2
    shell_2 = generate_d11_lattice_shell(max_norm_squared=2)
    
    # Generate the shell of points with ||p||^2 = 4
    shell_4 = []
    for indices in combinations(range(d), 4):
        for signs in [(1, 1, 1, 1), (1, 1, -1, -1), (1, -1, 1, -1), (1, -1, -1, 1)]:
            point = np.zeros(d, dtype=int)
            for i, sign in zip(indices, signs):
                point[i] = sign
            if np.sum(point) % 2 == 0:
                shell_4.append(point)
    shell_4 = np.array(shell_4)
    
    # Combine shells and filter points to satisfy the distance condition
    all_points = np.vstack([shell_2, shell_4])
    
    # Filter points to ensure max_i ||p_i|| <= min_{i!=j} ||p_i - p_j||
    def is_valid_set(points):
        max_norm = np.max(np.linalg.norm(points, axis=1))
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                if np.linalg.norm(points[i] - points[j]) < max_norm:
                    return False
        return True
    
    # Use a greedy approach to find the largest valid subset
    valid_points = []
    for point in all_points:
        temp_set = valid_points + [point]
        if is_valid_set(temp_set):
            valid_points.append(point)
    
    return np.array(valid_points)

# Example usage
points = kissing_number11()
print(f"Number of points found: {len(points)}")
print(f"Points:\n{points}")