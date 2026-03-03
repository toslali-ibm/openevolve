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
    # Initialize state
    cur_x = np.random.uniform(bounds[0], bounds[1])
    cur_y = np.random.uniform(bounds[0], bounds[1])
    cur_val = evaluate_function(cur_x, cur_y)
    best_x, best_y, best_value = cur_x, cur_y, cur_val
    
    temp = 2.6765  # @TUNE [0.1, 5.0] @TUNED(was=1.0, gain=+0.13, best_impact=distance_score:+0.2591)
    cooling = 0.9756  # @TUNE [0.95, 0.999] @TUNED(was=0.995, gain=+0.13, best_impact=distance_score:+0.2591)
    step_size = 1.6218  # @TUNE [0.1, 2.0] @TUNED(was=0.5, gain=+0.13, best_impact=distance_score:+0.2591)

    for i in range(iterations):
        # Mix local perturbation and global restarts
        if i % 10 == 0:
            x, y = np.random.uniform(bounds[0], bounds[1], 2)
        else:
            x = np.clip(cur_x + np.random.normal(0, step_size), bounds[0], bounds[1])
            y = np.clip(cur_y + np.random.normal(0, step_size), bounds[0], bounds[1])
        
        val = evaluate_function(x, y)
        
        # Metropolis-Hastings criterion
        if val < cur_val or np.random.rand() < np.exp((cur_val - val) / (temp + 1e-12)):
            cur_x, cur_y, cur_val = x, y, val
            if val < best_value:
                best_x, best_y, best_value = x, y, val
        
        temp *= cooling

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
