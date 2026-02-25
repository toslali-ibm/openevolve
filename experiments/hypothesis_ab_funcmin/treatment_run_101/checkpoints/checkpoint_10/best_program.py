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
    # Multi-scale Random Search with Shrinking Radius
    best_x, best_y = np.random.uniform(*bounds, 2)
    best_v = evaluate_function(best_x, best_y)
    
    for i in range(iterations):
        # Progress from 1.0 down to 0.0
        ratio = i / iterations
        # Adaptive step size: starts large, becomes very small
        sigma = 3.0 * (1 - ratio)**2 + 0.01
        
        # Candidate 1: Local search around current best
        x1 = np.clip(best_x + np.random.normal(0, sigma), *bounds)
        y1 = np.clip(best_y + np.random.normal(0, sigma), *bounds)
        
        # Candidate 2: Global exploration or wide-area search
        if i % 5 == 0:
            x2, y2 = np.random.uniform(*bounds, 2)
        else:
            x2 = np.clip(best_x + np.random.standard_cauchy() * sigma, *bounds)
            y2 = np.clip(best_y + np.random.standard_cauchy() * sigma, *bounds)
            
        for nx, ny in [(x1, y1), (x2, y2)]:
            nv = evaluate_function(nx, ny)
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
