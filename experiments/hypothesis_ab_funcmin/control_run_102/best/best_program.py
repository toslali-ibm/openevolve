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
    # Initialize with a random point
    best_x = np.random.uniform(bounds[0], bounds[1])
    best_y = np.random.uniform(bounds[0], bounds[1])
    best_value = evaluate_function(best_x, best_y)

    curr_x, curr_y = best_x, best_y
    for i in range(iterations):
        # Simulated Annealing: reduce step size over time
        temp = 1 - (i / iterations)
        step = (bounds[1] - bounds[0]) * 0.1 * temp
        
        # Mix global exploration and local exploitation
        if np.random.rand() < 0.1:
            x, y = np.random.uniform(*bounds, 2)
        else:
            x = np.clip(curr_x + np.random.normal(0, step), *bounds)
            y = np.clip(curr_y + np.random.normal(0, step), *bounds)
            
        value = evaluate_function(x, y)
        # Acceptance probability
        if value < best_value or np.random.rand() < np.exp((best_value - value) / (temp + 1e-9)):
            curr_x, curr_y = x, y
            if value < best_value:
                best_x, best_y, best_value = x, y, value

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
