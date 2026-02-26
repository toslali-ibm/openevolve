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
    # Multi-start Hill Climbing / Simulated Annealing hybrid
    best_x, best_y = np.random.uniform(*bounds, 2)
    best_value = evaluate_function(best_x, best_y)
    
    # Use 20% of budget for global sampling, 80% for refinement
    for i in range(iterations):
        temp = 1.0 - (i / iterations)
        if i % 10 == 0: # Global jump
            x, y = np.random.uniform(*bounds, 2)
        else: # Local perturbation
            scale = (bounds[1] - bounds[0]) * 0.1 * temp
            x = np.clip(best_x + np.random.normal(0, scale), *bounds)
            y = np.clip(best_y + np.random.normal(0, scale), *bounds)
            
        value = evaluate_function(x, y)
        # Probabilistic acceptance to escape local minima
        if value < best_value or np.random.rand() < np.exp((best_value - value) / (temp + 1e-9)):
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
