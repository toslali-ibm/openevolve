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

    min_b, max_b = bounds
    for i in range(iterations):
        # exploration_prob starts at 1.0 and linearly decreases to 0.3
        # Quadratic decay for exploration_prob: stays higher for longer, promoting global search
        exploration_prob = 1.0 - (i / iterations)**2 * 0.7 
        
        if np.random.rand() < exploration_prob:
            # Global exploration: sample widely across the bounds
            x = np.random.uniform(min_b, max_b)
            y = np.random.uniform(min_b, max_b)
        else:
            # Local exploitation: perturb around the current best point
            # Increased initial std_dev and quadratic decay for better local escape and fine-tuning
            std_dev = (max_b - min_b) * 0.2 * (1 - i / iterations)**2 + 0.01
            x = np.clip(best_x + np.random.normal(0, std_dev), min_b, max_b)
            y = np.clip(best_y + np.random.normal(0, std_dev), min_b, max_b)
        
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
