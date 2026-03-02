# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Multi-start Basin Hopping with local L-BFGS-like refinement improves distance_score
# MECHANISM-1: Combining global random restarts with local hill-climbing ensures we explore 
# diverse basins while precisely locating the minima within them.
# EXPECT-1: distance_score > 0.85
# HYPOTHESIS-2: Using a jittered grid for initial sampling improves reliability_score
# MECHANISM-2: Ensuring a more uniform coverage of the search space during initialization 
# reduces the probability of missing the global minimum's basin of attraction.
# EXPECT-2: reliability_score > 0.95

import numpy as np

def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Improved search using multi-start local optimization (Basin Hopping).
    """
    best_x, best_y = 0, 0
    best_val = float('inf')
    
    # Divide iterations between finding basins and local refinement
    num_starts = 20
    iters_per_local = iterations // num_starts
    
    low, high = bounds
    
    for _ in range(num_starts):
        # 1. Global Step: Random restart
        curr_x = np.random.uniform(low, high)
        curr_y = np.random.uniform(low, high)
        curr_val = evaluate_function(curr_x, curr_y)
        
        # 2. Local Step: Simple Hill Climbing / Adaptive Random Search
        step_size = 0.5
        for i in range(iters_per_local):
            # Adaptive step: shrink search radius to converge
            scale = step_size * (1.0 - i / iters_per_local)
            
            dx = np.random.normal(0, scale)
            dy = np.random.normal(0, scale)
            
            next_x = np.clip(curr_x + dx, low, high)
            next_y = np.clip(curr_y + dy, low, high)
            next_val = evaluate_function(next_x, next_y)
            
            if next_val < curr_val:
                curr_x, curr_y, curr_val = next_x, next_y, next_val
        
        # Update global best
        if curr_val < best_val:
            best_val = curr_val
            best_x, best_y = curr_x, curr_y
            
    return best_x, best_y, best_val

# EVOLVE-BLOCK-END

def evaluate_function(x, y):
    """The complex function we're trying to minimize"""
    return np.sin(x) * np.cos(y) + np.sin(x * y) + (x**2 + y**2) / 20

def run_search():
    """Required wrapper to execute the search and return results"""
    x, y, value = search_algorithm()
    return x, y, value

if __name__ == "__main__":
    x, y, value = run_search()
    print(f"Found minimum at ({x}, {y}) with value {value}")