# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Simulated Annealing with local refinement improves distance_score.
# MECHANISM-1: Probabilistically accepting worse solutions allows the search to escape
#   shallow local minima, while a cooling schedule narrows focus on the global basin.
# EXPECT-1: distance_score > 0.85
# HYPOTHESIS-2: Using a hybrid of global exploration and local Gaussian mutation
# MECHANISM-2: Global uniform sampling finds potential basins, while Gaussian steps
#   converge precisely to the actual minimum within those basins.
# EXPECT-2: combined_score > 1.35
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Hybrid Simulated Annealing and Random Search.
    """
    low, high = bounds
    # Start at a random point
    curr_x = np.random.uniform(low, high)
    curr_y = np.random.uniform(low, high)
    curr_val = evaluate_function(curr_x, curr_y)
    
    best_x, best_y, best_val = curr_x, curr_y, curr_val
    
    for i in range(iterations):
        temp = 1.0 - (i / iterations)
        # Mix global jumps and local refinement
        if i % 10 == 0:
            nx, ny = np.random.uniform(low, high, 2)
        else:
            step = 2.0 * temp
            nx = np.clip(curr_x + np.random.normal(0, step), low, high)
            ny = np.clip(curr_y + np.random.normal(0, step), low, high)
            
        n_val = evaluate_function(nx, ny)
        
        # Metropolis Criterion
        if n_val < curr_val or np.random.rand() < np.exp((curr_val - n_val) / (temp + 1e-9)):
            curr_x, curr_y, curr_val = nx, ny, n_val
            
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
