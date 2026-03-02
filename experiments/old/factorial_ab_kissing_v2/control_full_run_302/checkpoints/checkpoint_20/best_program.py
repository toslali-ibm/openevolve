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
    max_norm_squared = 4  # Target maximum squared norm for points
    min_distance_squared = 4  # Target minimum squared pairwise distance between points

    # Generate shells from the D_11 lattice
    def generate_shell(norm_squared):
        """
        Generate points in D_11 lattice with a fixed squared norm.
        Points in D_11 lattice must have even sum of coordinates.

        Args:
            norm_squared (int): Target squared norm of points.

        Returns:
            np.ndarray: Array of points with the specified squared norm.
        """
        shell = []
        for indices in combinations(range(d), norm_squared):
            for signs in np.ndindex(*([2] * norm_squared)):  # Generate all combinations of ±1
                point = np.zeros(d, dtype=np.int64)
                for idx, sign in zip(indices, signs):
                    point[idx] = 1 if sign == 1 else -1
                if np.sum(point) % 2 == 0:  # Ensure sum of coordinates is even
                    shell.append(point)
        return np.array(shell)

    # Generate lattice shells for ||p||^2 = 2 and ||p||^2 = 4
    shell_2 = generate_shell(2)
    shell_4 = generate_shell(4)

    # Combine all points into one set
    all_points = np.vstack([shell_2, shell_4])

    # Filter points to enforce the constraint
    def filter_points(points):
        """
        Filters points to satisfy the constraint:
        max_i ||p_i|| <= min_{i!=j} ||p_i - p_j||.

        Args:
            points (np.ndarray): Array of candidate points.

        Returns:
            np.ndarray: Array of filtered points satisfying the constraint.
        """
        filtered_points = []
        for p_i in points:
            valid = True
            for p_j in filtered_points:
                if np.sum((p_i - p_j) ** 2) < min_distance_squared:
                    valid = False
                    break
            if valid:
                filtered_points.append(p_i)
        return np.array(filtered_points)

    # Apply filtering
    filtered_points = filter_points(all_points)

    return filtered_points


# Test the function
points = kissing_number11()
print(f"Number of points: {len(points)}")
print(f"Points:\n{points}")