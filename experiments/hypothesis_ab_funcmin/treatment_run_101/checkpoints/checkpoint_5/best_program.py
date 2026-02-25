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
    # Simulated Annealing with Local Search
    curr_x = np.random.uniform(*bounds)
    curr_y = np.random.uniform(*bounds)
    curr_v = evaluate_function(curr_x, curr_y)
    best_x, best_y, best_v = curr_x, curr_y, curr_v

    for i in range(iterations):
        temp = 1 - i / iterations
        # Mix global jumps with local refinement
        if i % 10 == 0:
            nx, ny = np.random.uniform(*bounds, 2)
        else:
            nx = np.clip(curr_x + np.random.normal(0, temp * 2), *bounds)
            ny = np.clip(curr_y + np.random.normal(0, temp * 2), *bounds)
        
        nv = evaluate_function(nx, ny)
        if nv < curr_v or np.random.rand() < np.exp((curr_v - nv) / (temp + 1e-9)):
            curr_x, curr_y, curr_v = nx, ny, nv
            if nv < best_v:
                best_x, best_y, best_v = nx, ny, nv

    return best_x, best_y, best_v


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
