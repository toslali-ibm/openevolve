# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Multi-start Basin Hopping improves reliability_score and distance_score.
# MECHANISM-1: Combining random restarts with local hill-climbing ensures we don't 
#   just find a local basin but actively explore multiple basins to find the global one.
# EXPECT-1: reliability_score > 0.95
# HYPOTHESIS-2: Iterative step-size reduction improves value_score.
# MECHANISM-2: Starting with large jumps allows jumping between basins, while 
#   narrowing the search allows for high-precision convergence to the minimum.
# EXPECT-2: combined_score > 1.3

import numpy as np

def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Improved search algorithm using a multi-start basin-hopping approach.
    """
    best_x, best_y = None, None
    best_val = float('inf')
    
    # We split the budget into multiple independent restarts
    num_starts = 8
    iters_per_start = iterations // num_starts
    
    for _ in range(num_starts):
        # 1. Random restart
        curr_x = np.random.uniform(bounds[0], bounds[1])
        curr_y = np.random.uniform(bounds[0], bounds[1])
        curr_val = evaluate_function(curr_x, curr_y)
        
        # 2. Local search with simulated annealing behavior
        temp = 1.0
        for i in range(iters_per_start):
            # Adaptive step: starts wide, ends narrow
            fraction = i / iters_per_start
            step = 3.0 * (1.0 - fraction)**2 + 0.01
            
            # Propose move
            next_x = np.clip(curr_x + np.random.normal(0, step), bounds[0], bounds[1])
            next_y = np.clip(curr_y + np.random.normal(0, step), bounds[0], bounds[1])
            next_val = evaluate_function(next_x, next_y)
            
            # Metropolis-like acceptance
            diff = next_val - curr_val
            if diff < 0 or (temp > 0 and np.random.rand() < np.exp(-diff / temp)):
                curr_x, curr_y, curr_val = next_x, next_y, next_val
                
                if curr_val < best_val:
                    best_val, best_x, best_y = curr_val, curr_x, curr_y
            
            # Cool temperature
            temp *= 0.95

    return best_x, best_y, best_val

def run_search():
    """Wrapper function required by the evaluation environment."""
    x, y, value = search_algorithm()
    return x, y, value

# EVOLVE-BLOCK-END

# This part remains fixed (not evolved)
def evaluate_function(x, y):
    """The complex function we're trying to minimize"""
    return np.sin(x) * np.cos(y) + np.sin(x * y) + (x**2 + y**2) / 20

if __name__ == "__main__":
    x, y, value = run_search()
    print(f"Found minimum at ({x}, {y}) with value {value}")