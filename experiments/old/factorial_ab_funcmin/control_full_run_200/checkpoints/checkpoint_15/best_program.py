# EVOLVE-BLOCK-START
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Implements a multi-start Simulated Annealing algorithm to robustly
    find the global minimum of the function. It combines broad global
    exploration with a metaheuristic local search that can escape
    local minima by accepting uphill moves with a decreasing probability.
    """
    low, high = bounds
    best_x, best_y, best_value = 0, 0, float('inf')
    
    # Configuration for multi-start Simulated Annealing
    # Fewer starts, but each local search is more thorough (Simulated Annealing)
    num_starts = 10  # Number of independent SA runs
    local_iters_per_start = iterations // num_starts # Iterations for each SA run (e.g., 100 for 1000 total)

    # Simulated Annealing parameters
    initial_temp = 0.5  # Starting temperature for SA (can be tuned)
    initial_step_std = 1.0 # Initial standard deviation for proposing new points (can be tuned)

    for _ in range(num_starts):
        # Global Exploration Phase: Start each SA run from a random point
        start_x = np.random.uniform(low, high)
        start_y = np.random.uniform(low, high)
        
        # Initialize current state for this SA run
        sa_curr_x, sa_curr_y = start_x, start_y
        sa_curr_value = evaluate_function(sa_curr_x, sa_curr_y)
        
        # Track the best solution found *during this specific SA run*
        local_best_x, local_best_y, local_best_value = sa_curr_x, sa_curr_y, sa_curr_value

        # Local Exploitation Phase (Simulated Annealing):
        for i in range(local_iters_per_start):
            # Temperature schedule: decreases linearly from initial_temp to near zero
            # Adding a small epsilon to avoid division by zero in exp((...) / temp)
            temp = initial_temp * (1 - i / local_iters_per_start) + 1e-9 
            
            # Adaptive step size: decreases proportionally with temperature
            # This allows larger jumps initially and finer adjustments later
            step_std = initial_step_std * (temp / initial_temp) 
            
            # Propose a new point by adding Gaussian noise
            nx = np.clip(sa_curr_x + np.random.normal(0, step_std), low, high)
            ny = np.clip(sa_curr_y + np.random.normal(0, step_std), low, high)
            nv = evaluate_function(nx, ny)
            
            # Metropolis-Hastings acceptance criterion
            # Accept if better, or accept worse with a probability determined by temperature
            if nv < sa_curr_value or np.random.rand() < np.exp((sa_curr_value - nv) / temp):
                sa_curr_x, sa_curr_y, sa_curr_value = nx, ny, nv
            
            # Always update the best solution found so far in this local run
            if sa_curr_value < local_best_value:
                local_best_x, local_best_y, local_best_value = sa_curr_x, sa_curr_y, sa_curr_value

        # After each SA run, compare its best result to the overall global best
        if local_best_value < best_value:
            best_x, best_y, best_value = local_best_x, local_best_y, local_best_value

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