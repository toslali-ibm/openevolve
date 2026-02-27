import numpy as np
from itertools import combinations, product


def kissing_number11() -> np.ndarray:
    """
    Constructs a collection of 11-dimensional points with integral coordinates such that their maximum
    L2 norm is less than or equal to their minimum pairwise L2 distance, aiming to maximize the number of points.

    The strategy uses points from the D₁₁ lattice with squared L2 norms 2 and 4, filtered efficiently
    to satisfy the constraint max_i ||p_i|| <= min_{i!=j} ||p_i - p_j||.

    Returns:
        points: np.ndarray of shape (num_points, 11) containing the generated points.
    """
    d = 11  # Dimension of the space
    max_norm_squared = 4  # Maximum squared L2 norm of points
    min_distance_squared = 4  # Minimum squared pairwise L2 distance between points

    # Generate points in the D₁₁ lattice with ||p||² = 2
    def generate_shell_2():
        """
        Generate points in the D₁₁ lattice with squared L2 norm 2.
        """
        points = []
        for indices in combinations(range(d), 2):  # Choose 2 non-zero coordinates
            for signs in product([-1, 1], repeat=2):  # Assign signs to the coordinates
                point = np.zeros(d, dtype=np.int64)
                for i, sign in zip(indices, signs):
                    point[i] = sign
                if np.sum(point) % 2 == 0:  # D₁₁ lattice condition: sum of coordinates is even
                    points.append(point)
        return points

    # Generate points in the D₁₁ lattice with ||p||² = 4
    def generate_shell_4():
        """
        Generate points in the D₁₁ lattice with squared L2 norm 4.
        """
        points = []
        # Case 1: One coordinate is ±2
        for i in range(d):
            for sign in [-2, 2]:
                point = np.zeros(d, dtype=np.int64)
                point[i] = sign
                points.append(point)

        # Case 2: Four coordinates are ±1
        for indices in combinations(range(d), 4):  # Choose 4 non-zero coordinates
            for signs in product([-1, 1], repeat=4):  # Assign signs to the coordinates
                point = np.zeros(d, dtype=np.int64)
                for i, sign in zip(indices, signs):
                    point[i] = sign
                if np.sum(point) % 2 == 0:  # D₁₁ lattice condition: sum of coordinates is even
                    points.append(point)
        return points

    # Generate shells for ||p||² = 2 and ||p||² = 4
    shell_2 = generate_shell_2()
    shell_4 = generate_shell_4()

    # Combine all generated points
    all_points = np.array(shell_2 + shell_4, dtype=np.int64)

    # Optimized filtering using a greedy approach
    def filter_points(points):
        """
        Filters points to maximize the valid set satisfying the constraint:
        max_i ||p_i|| <= min_{i!=j} ||p_i - p_j||.

        Args:
            points (np.ndarray): Array of candidate points.

        Returns:
            np.ndarray: Array of filtered points satisfying the constraint.
        """
        filtered_points = []
        norms = np.linalg.norm(points, axis=1)  # Precompute norms for efficiency
        sorted_indices = np.argsort(norms)  # Sort points by norm for incremental filtering

        for idx in sorted_indices:
            p_i = points[idx]
            is_valid = True
            for p_j in filtered_points:
                if np.sum((p_i - p_j) ** 2) < min_distance_squared:
                    is_valid = False
                    break
            if is_valid:
                filtered_points.append(p_i)
        return np.array(filtered_points, dtype=np.int64)

    # Apply filtering to maximize the valid set of points
    filtered_points = filter_points(all_points)

    return filtered_points


# Test the function
if __name__ == "__main__":
    points = kissing_number11()
    print(f"Number of points found: {len(points)}")
    # Uncomment the line below to print the points if necessary
    # print(f"Points:\n{points}")