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
    
    initial_temp = 0.9919  # @TUNE [0.5, 5.0] @TUNED(was=1.2534, gain=+0.72, best_impact=combined_score:+0.7228)
    current_temp = initial_temp # Variable for the decaying temperature
    cooling_rate = 0.9758  # @TUNE [0.90, 0.999] @TUNED(was=0.993, gain=+0.72, best_impact=combined_score:+0.7228)
    
    # Probability of a global exploration jump (new tunable parameter)
    global_jump_prob = 0.3419  # @TUNE [0.01, 0.5] @TUNED(was=0.1, gain=+0.72, best_impact=combined_score:+0.7228)
    
    # Base perturbation sigma for local search. Hardcoded from previous s_init average.
    base_perturbation_sigma = 1.5 

    for i in range(iterations):
        # Adaptive step size for local perturbations: scales down with temperature, relative to initial_temp
        perturbation_sigma = base_perturbation_sigma * (current_temp / initial_temp) + 0.01
        
        # Decide search strategy: global random jump, jump to best, or local perturbation
        rand_val = np.random.rand()
        if rand_val < global_jump_prob: # Pure exploration: jump to a random point
            x, y = np.random.uniform(*bounds, 2)
        elif rand_val < global_jump_prob + (global_jump_prob * 0.5): # Exploitation: jump to the best known position
            x, y = best_x, best_y
        else: # Local search: perturb around the current position
            x = np.clip(cur_x + np.random.normal(0, perturbation_sigma), *bounds)
            y = np.clip(cur_y + np.random.normal(0, perturbation_sigma), *bounds)
        
        val = evaluate_function(x, y)
        
        # Metropolis-Hastings criterion for accepting new state
        if val < cur_val or np.random.rand() < np.exp((cur_val - val) / (current_temp + 1e-9)):
            cur_x, cur_y, cur_val = x, y, val
            if val < best_value:
                best_x, best_y, best_value = x, y, val
        
        current_temp *= cooling_rate # Apply cooling schedule

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
