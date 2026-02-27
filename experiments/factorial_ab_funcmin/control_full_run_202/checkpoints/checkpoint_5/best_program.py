# EVOLVE-BLOCK-START
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Implements a Basin-Hopping inspired approach: Multi-start local search
    to escape local minima and find the global minimum of the function.
    """
    low, high = bounds
    best_x, best_y, best_value = 0, 0, float('inf')
    
    # Divide iterations between global exploration and local exploitation
    # Use a multi-start strategy: pick random points and hill-climb
    num_starts = 40
    local_iters = iterations // num_starts

    for _ in range(num_starts):
        # Global Step: Random restart
        curr_x = np.random.uniform(low, high)
        curr_y = np.random.uniform(low, high)
        
        # Local Step: Hill climbing (Random Walk with shrinking step)
        step_size = 1.0
        for i in range(local_iters):
            # Propose a move
            nx = np.clip(curr_x + np.random.normal(0, step_size), low, high)
            ny = np.clip(curr_y + np.random.normal(0, step_size), low, high)
            nv = evaluate_function(nx, ny)
            
            if nv < evaluate_function(curr_x, curr_y):
                curr_x, curr_y = nx, ny
            
            # Reduce step size to converge
            step_size *= 0.95

        # Update global best
        final_v = evaluate_function(curr_x, curr_y)
        if final_v < best_value:
            best_x, best_y, best_value = curr_x, curr_y, final_v

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