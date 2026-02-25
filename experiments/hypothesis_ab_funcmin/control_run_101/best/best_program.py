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
    # Simulated Annealing with Local Refinement
    curr_x = np.random.uniform(*bounds)
    curr_y = np.random.uniform(*bounds)
    curr_val = evaluate_function(curr_x, curr_y)
    best_x, best_y, best_value = curr_x, curr_y, curr_val

    for i in range(iterations):
        temp = (1.0 - i / iterations) ** 2
        step = 2.0 * temp + 0.02
        
        # Mix of local search, medium jumps, and global resets
        r = np.random.rand()
        if r > 0.15:
            x, y = np.clip([curr_x, curr_y] + np.random.normal(0, step, 2), *bounds)
        elif r > 0.05:
            x, y = np.clip([best_x, best_y] + np.random.uniform(-1, 1, 2), *bounds)
        else:
            x, y = np.random.uniform(*bounds, 2)
            
        val = evaluate_function(x, y)
        
        if val < curr_val or np.random.rand() < np.exp((curr_val - val) / (temp + 1e-7)):
            curr_x, curr_y, curr_val = x, y, val
            if val < best_value:
                best_x, best_y, best_value = x, y, val

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
