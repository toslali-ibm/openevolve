# EVOLVE-BLOCK-START
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    A simple random search algorithm that often gets stuck in local minima.

    Args:
        iterations: Number of iterations to run
        bounds: Bounds for the search space (min, max)

    Returns:
        Tuple of (best_x, best_y, best_value)
    """
    # Adaptive simulated annealing approach
    best_x = np.random.uniform(*bounds)
    best_y = np.random.uniform(*bounds)
    best_value = evaluate_function(best_x, best_y)

    for i in range(iterations):
        # Progressively decrease search radius (cooling)
        temp = 1.0 - (i / iterations)
        scale = (bounds[1] - bounds[0]) * temp
        
        # Perturb current best or explore globally early on
        if i < iterations // 4:
            x, y = np.random.uniform(*bounds, 2)
        else:
            x = np.clip(best_x + np.random.normal(0, scale * 0.5), *bounds)
            y = np.clip(best_y + np.random.normal(0, scale * 0.5), *bounds)
            
        value = evaluate_function(x, y)
        if value < best_value:
            best_value, best_x, best_y = value, x, y

    return best_x, best_y, best_value


# EVOLVE-BLOCK-END


# This part remains fixed (not evolved)
def evaluate_function(x, y):
    """The complex function we're trying to minimize"""
    return np.sin(x) * np.cos(y) + np.sin(x * y) + (x**2 + y**2) / 20


def run_search():
    x, y, value = search_algorithm()
    return x, y, value


if __name__ == "__main__":
    x, y, value = run_search()
    print(f"Found minimum at ({x}, {y}) with value {value}")
