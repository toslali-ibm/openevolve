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
    # Initialize current and global best solutions
    current_x = np.random.uniform(*bounds)
    current_y = np.random.uniform(*bounds)
    current_value = evaluate_function(current_x, current_y)

    global_best_x, global_best_y, global_best_value = current_x, current_y, current_value
    
    for i in range(iterations):
        # Progressively decrease temperature (cooling schedule)
        # Temp goes from 1.0 down to a small positive value (e.g., 1/iterations)
        temp = 1.0 - (i / iterations) 
        
        # Scale of perturbation decreases with temperature
        scale = (bounds[1] - bounds[0]) * temp
        
        # Perturb current solution or explore globally early on
        if i < iterations // 4:
            # Aggressive global exploration phase
            proposed_x, proposed_y = np.random.uniform(*bounds, 2)
        else:
            # Perturb around the current solution (exploration/exploitation)
            # Increased perturbation scale from 0.1 to 0.2 for wider exploration
            proposed_x = np.clip(current_x + np.random.normal(0, scale * 0.2), *bounds)
            proposed_y = np.clip(current_y + np.random.normal(0, scale * 0.2), *bounds)
            
        proposed_value = evaluate_function(proposed_x, proposed_y)

        # Simulated Annealing acceptance criterion (Metropolis-Hastings)
        if proposed_value < current_value:
            # Always accept a better solution
            current_value, current_x, current_y = proposed_value, proposed_x, proposed_y
            # Update global best if this is the best found so far
            if current_value < global_best_value:
                global_best_value, global_best_x, global_best_y = current_value, current_x, current_y
        else:
            # Accept a worse solution with a certain probability (to escape local minima)
            acceptance_probability = np.exp(-(proposed_value - current_value) / temp)
            if np.random.rand() < acceptance_probability:
                current_value, current_x, current_y = proposed_value, proposed_x, proposed_y

    return global_best_x, global_best_y, global_best_value


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
