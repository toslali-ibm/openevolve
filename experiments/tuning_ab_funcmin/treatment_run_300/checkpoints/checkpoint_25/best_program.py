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
    # Probability of performing a local SA-like refinement burst around the current best
    local_sa_prob = 0.5537  # @TUNE [0.1, 0.9] @TUNED(was=0.6, gain=+0.00, best_impact=distance_score:+0.0007)
    # Initial temperature for the local SA-like process
    initial_local_temp = 0.1293  # @TUNE [0.01, 5.0] @TUNED(was=0.5, gain=+0.00, best_impact=distance_score:+0.0007)
    # Cooling rate for the local SA-like process
    local_cooling_rate = 0.8078  # @TUNE [0.8, 0.999] @TUNED(was=0.95, gain=+0.00, best_impact=distance_score:+0.0007)

    # Hardcoded parameters for the local SA burst
    local_sa_steps = 5 # Number of iterations within each local SA burst
    local_sa_step_scale = 0.1 # Scale for proposal step size in local SA

    for _ in range(iterations):
        # Always perform a global random search step (exploration)
        x_global = np.random.uniform(bounds[0], bounds[1])
        y_global = np.random.uniform(bounds[0], bounds[1])
        value_global = evaluate_function(x_global, y_global)

        if value_global < best_value:
            best_value = value_global
            best_x, best_y = x_global, y_global

        # Periodically perform local SA-like refinement around the current best (exploitation with escape)
        if np.random.rand() < local_sa_prob:
            # Initialize a temporary state for the local SA burst, starting from the current overall best
            current_sa_x, current_sa_y = best_x, best_y
            current_sa_val = best_value
            
            # Reset temperature for each new local SA burst
            temp_for_burst = initial_local_temp 

            for _ in range(local_sa_steps):
                # Step size for proposals decreases with temperature, ensuring minimal exploration at low temps
                sa_proposal_std = local_sa_step_scale * temp_for_burst + 0.001 
                
                x_candidate = np.clip(current_sa_x + np.random.normal(0, sa_proposal_std), bounds[0], bounds[1])
                y_candidate = np.clip(current_sa_y + np.random.normal(0, sa_proposal_std), bounds[0], bounds[1])
                val_candidate = evaluate_function(x_candidate, y_candidate)

                # Metropolis-Hastings acceptance criterion
                # Accept if better, or with a probability if worse (to escape local minima)
                if val_candidate < current_sa_val or np.random.rand() < np.exp((current_sa_val - val_candidate) / (temp_for_burst + 1e-10)):
                    current_sa_x, current_sa_y = x_candidate, y_candidate
                    current_sa_val = val_candidate
                    
                    # If this new state found by local SA is better than the overall best, update it
                    if current_sa_val < best_value:
                        best_value = current_sa_val
                        best_x, best_y = current_sa_x, current_sa_y
                
                temp_for_burst *= local_cooling_rate # Cool down the temperature for this local burst

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
