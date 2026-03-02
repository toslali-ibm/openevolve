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

    starts = 10
    for s in range(starts):
        # Start from a new random location each cycle
        cx, cy = np.random.uniform(*bounds, 2)
        cv = evaluate_function(cx, cy)
        
        for i in range(iterations // starts):
            # Local refinement with quadratic decay for better convergence
            ratio = i / (iterations // starts)
            sigma = 2.5 * (1 - ratio)**2 + 0.001
            nx = np.clip(cx + np.random.normal(0, sigma), *bounds)
            ny = np.clip(cy + np.random.normal(0, sigma), *bounds)
            
            nv = evaluate_function(nx, ny)
            if nv < cv:
                cx, cy, cv = nx, ny, nv
        
        if cv < best_value:
            best_x, best_y, best_value = cx, cy, cv

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
