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

    # Tunable parameters for the hybrid strategy
    # Probability of performing a local refinement step around the current best
    local_refinement_prob = 0.627  # @TUNE [0.1, 0.7] @TUNED(was=0.3, gain=+0.00, best_impact=distance_score:+0.0081)
    # Standard deviation for the local refinement step
    local_step_std = 0.0599  # @TUNE [0.05, 0.5] @TUNED(was=0.2, gain=+0.00, best_impact=distance_score:+0.0081)
    # Number of local refinement attempts if chosen
    num_local_steps = 6  # @TUNE [1, 10] int @TUNED(was=5, gain=+0.00, best_impact=distance_score:+0.0081)

    for _ in range(iterations):
        # Always perform a global random search step
        x_global = np.random.uniform(bounds[0], bounds[1])
        y_global = np.random.uniform(bounds[0], bounds[1])
        value_global = evaluate_function(x_global, y_global)

        if value_global < best_value:
            best_value = value_global
            best_x, best_y = x_global, y_global

        # Periodically perform local refinement around the current best
        if np.random.rand() < local_refinement_prob:
            current_local_x, current_local_y = best_x, best_y
            current_local_value = best_value

            for _ in range(num_local_steps):
                # Take a small step from the current best
                x_local = np.clip(current_local_x + np.random.normal(0, local_step_std), bounds[0], bounds[1])
                y_local = np.clip(current_local_y + np.random.normal(0, local_step_std), bounds[0], bounds[1])
                value_local = evaluate_function(x_local, y_local)

                if value_local < current_local_value:
                    current_local_x, current_local_y = x_local, y_local
                    current_local_value = value_local
                    
                    if value_local < best_value: # Update overall best if local search finds something better
                        best_value = value_local
                        best_x, best_y = x_local, y_local
                # Else, if local step is worse, we just discard it (greedy local search).

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
