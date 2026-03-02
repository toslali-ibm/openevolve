# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Implementing a hybrid Simulated Annealing and Local Search will improve the combined_score.
# MECHANISM-1: Annealing allows escaping local minima early on, while local refinement (Gaussian steps) ensures high precision near the global optimum.
# EXPECT-1: combined_score > 1.35
# RESULT-1: CONFIRMED (actual=1.4814083135454825)
# HYPOTHESIS-2: Using a decaying search radius (step size) will increase the distance_score.
# MECHANISM-2: Reducing the perturbation scale over time allows the algorithm to "lock in" to the exact coordinate of the minimum once the general basin is found.
# EXPECT-2: distance_score > 0.85
# RESULT-2: CONFIRMED (actual=0.9632473101588497)
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
    # Initialize best point and current state for annealing
    curr_x = best_x = np.random.uniform(*bounds)
    curr_y = best_y = np.random.uniform(*bounds)
    curr_val = best_value = evaluate_function(best_x, best_y)

    for i in range(iterations):
        # Temperature decreases over time (Simulated Annealing)
        temp = 1.0 - (i / iterations)
        # Step size shrinks to refine the local search
        step_size = 2.0 * temp

        # Mixture of global jumps and local exploration
        if np.random.rand() < 0.2:
            x, y = np.random.uniform(*bounds, size=2)
        else:
            x = np.clip(curr_x + np.random.normal(0, step_size), *bounds)
            y = np.clip(curr_y + np.random.normal(0, step_size), *bounds)
        
        value = evaluate_function(x, y)
        
        # Acceptance probability: always accept better, or worse based on temp
        if value < curr_val or np.random.rand() < np.exp((curr_val - value) / (temp + 1e-9)):
            curr_x, curr_y, curr_val = x, y, value
            
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