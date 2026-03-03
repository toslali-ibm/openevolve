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
    best_x, best_y, best_value = None, None, float('inf')
    num_starts = 5
    iters_per_start = iterations // num_starts

    for _ in range(num_starts):
        # Start each attempt at a new random location
        curr_x = np.random.uniform(*bounds)
        curr_y = np.random.uniform(*bounds)
        curr_v = evaluate_function(curr_x, curr_y)

        for i in range(iters_per_start):
            # Scale reduces from 2.0 to 0.001
            scale = 2.0 * (1 - i / iters_per_start)**2
            x = np.clip(curr_x + np.random.normal(0, scale), *bounds)
            y = np.clip(curr_y + np.random.normal(0, scale), *bounds)
            
            v = evaluate_function(x, y)
            if v < curr_v:
                curr_x, curr_y, curr_v = x, y, v
        
        if curr_v < best_value:
            best_x, best_y, best_value = curr_x, curr_y, curr_v

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
