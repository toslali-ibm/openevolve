# EVOLVE-BLOCK-START
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Implements a Multi-Start Simulated Annealing (MSSA) strategy.
    Combines global exploration (random restarts) with local exploitation 
    (probabilistic hill climbing) to escape local minima in the function
    f(x, y) = sin(x)cos(y) + sin(xy) + (x^2+y^2)/20.
    """
    low, high = bounds
    best_x, best_y, best_val = 0.0, 0.0, float('inf')
    
    # We use multiple starts to cover the search space.
    # 25 starts with 40 iterations each provides a good balance.
    num_starts = 25
    iters_per_start = iterations // num_starts

    for _ in range(num_starts):
        # Global Step: Random restart using a uniform distribution
        curr_x = np.random.uniform(low, high)
        curr_y = np.random.uniform(low, high)
        curr_val = evaluate_function(curr_x, curr_y)
        
        # Local Step: Simulated Annealing / Stochastic Hill Climbing
        # Initial temperature/step size
        temp = 1.5 
        
        for i in range(iters_per_start):
            # Propose a neighbor using a Gaussian distribution
            # The scale of the search narrows as i increases
            scale = temp * (1.0 - i / iters_per_start)
            nx = np.clip(curr_x + np.random.normal(0, scale), low, high)
            ny = np.clip(curr_y + np.random.normal(0, scale), low, high)
            n_val = evaluate_function(nx, ny)
            
            # Acceptance criteria: Always accept better, 
            # occasionally accept worse to escape local traps
            if n_val < curr_val:
                curr_x, curr_y, curr_val = nx, ny, n_val
            else:
                # Metropolis-like probability (simplified)
                prob = np.exp((curr_val - n_val) / (temp + 1e-9))
                if np.random.rand() < prob * 0.1:
                    curr_x, curr_y, curr_val = nx, ny, n_val

        # Update the global champion
        if curr_val < best_val:
            best_x, best_y, best_val = curr_x, curr_y, curr_val

    return best_x, best_y, best_val


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