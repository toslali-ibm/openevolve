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
    steps = iterations // num_starts

    for _ in range(num_starts):
        cx = np.random.uniform(*bounds)
        cy = np.random.uniform(*bounds)
        cv = evaluate_function(cx, cy)

        for i in range(steps):
            # Adaptive scale: starts wide, narrows down for precision
            scale = 2.0 * (1 - i / steps)**2
            nx = np.clip(cx + np.random.normal(0, scale), *bounds)
            ny = np.clip(cy + np.random.normal(0, scale), *bounds)
            
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
