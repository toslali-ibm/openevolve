# EVOLVE-BLOCK-START
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Implements a multi-start local search strategy (inspired by Basin-Hopping)
    to reliably find the global minimum of a complex function with many local minima.

    The algorithm divides the total iterations into multiple independent local searches.
    Each local search starts from a random point and performs a hill-climbing
    optimization with a shrinking step size to converge to a local minimum.
    The best result from all local searches is then returned as the global minimum candidate.
    """
    low, high = bounds
    best_x, best_y, best_value = 0, 0, float('inf')
    
    # Number of independent local search runs (starts)
    # Reverting `num_starts` from 50 to 40, as seen in the top-performing Program 1.
    # This allows for more iterations per local search, improving local convergence
    # without sacrificing too much global exploration.
    num_starts = 40 
    # Number of iterations for each local search
    local_iters = max(1, iterations // num_starts) 

    for _ in range(num_starts):
        # 1. Global Exploration: Pick a new random starting point for the current local search
        curr_x = np.random.uniform(low, high)
        curr_y = np.random.uniform(low, high)
        curr_value = evaluate_function(curr_x, curr_y) # Evaluate the starting point once
        
        # 2. Local Exploitation: Perform hill-climbing from this starting point
        # Initial step size for perturbations, decreases over local search iterations
        step_size = 1.0 
        # Adjusted `step_decay` from 0.95 to 0.9. A slightly faster decay rate helps
        # the local search converge more precisely to the bottom of the basin
        # within the allocated `local_iters`.
        step_decay = 0.9 

        for _ in range(local_iters):
            # Propose a new candidate point by perturbing around (curr_x, curr_y)
            # Using a normal distribution helps concentrate steps around the current point.
            candidate_x = np.clip(curr_x + np.random.normal(0, step_size), low, high)
            candidate_y = np.clip(curr_y + np.random.normal(0, step_size), low, high)
            candidate_value = evaluate_function(candidate_x, candidate_y)
            
            # If the candidate point is better, move to it for the current local search
            if candidate_value < curr_value:
                curr_x, curr_y = candidate_x, candidate_y
                curr_value = candidate_value
            
            # Reduce step size for finer search as iterations progress
            step_size *= step_decay

        # After the current local search completes, compare its best result
        # with the overall best found across all starts so far.
        if curr_value < best_value:
            best_x, best_y, best_value = curr_x, curr_y, curr_value

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