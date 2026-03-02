# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Hybridizing a global search with a localized refinement improves distance_score.
# MECHANISM-1: Multi-start random sampling identifies the most promising basin, then a high-iteration 
#   local search converges precisely on the minimum within that basin.
# EXPECT-1: distance_score > 0.9
# HYPOTHESIS-2: Using a larger proportion of iterations for local refinement improves value_score.
# MECHANISM-2: The quadratic term (x^2+y^2)/20 creates a strong global pull toward (0,0), 
#   so focusing refinement near the center after exploration avoids trapping in peripheral minima.
# EXPECT-2: value_score > 0.95

import numpy as np

def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Finds the global minimum using a multi-start exploration followed by 
    an adaptive local refinement.
    """
    
    # 1. Global Exploration Phase (20% of budget)
    # Sample points to find the most promising basin of attraction
    best_x, best_y = 0, 0
    best_val = float('inf')
    
    num_starts = int(iterations * 0.2)
    for _ in range(num_starts):
        x = np.random.uniform(bounds[0], bounds[1])
        y = np.random.uniform(bounds[0], bounds[1])
        val = evaluate_function(x, y)
        if val < best_val:
            best_val, best_x, best_y = val, x, y

    # 2. Local Refinement Phase (80% of budget)
    # Use a hill-climbing approach with shrinking step size
    curr_x, curr_y, curr_val = best_x, best_y, best_val
    refine_iters = iterations - num_starts
    
    for i in range(refine_iters):
        # Progressively smaller search radius
        scale = 1.0 - (i / refine_iters)
        step_size = 0.5 * scale
        
        # Try a small perturbation
        dx, dy = np.random.normal(0, step_size, 2)
        next_x = np.clip(curr_x + dx, bounds[0], bounds[1])
        next_y = np.clip(curr_y + dy, bounds[0], bounds[1])
        
        next_val = evaluate_function(next_x, next_y)
        
        if next_val < curr_val:
            curr_x, curr_y, curr_val = next_x, next_y, next_val
            
            # Update global best if found
            if curr_val < best_val:
                best_val, best_x, best_y = curr_val, curr_x, curr_y
                
    return best_x, best_y, best_val

def run_search():
    """Wrapper function required by the evaluation harness."""
    return search_algorithm()

# EVOLVE-BLOCK-END

def evaluate_function(x, y):
    """The complex function we're trying to minimize"""
    return np.sin(x) * np.cos(y) + np.sin(x * y) + (x**2 + y**2) / 20

if __name__ == "__main__":
    x, y, value = run_search()
    print(f"Found minimum at ({x}, {y}) with value {value}")