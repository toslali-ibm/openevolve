# EVOLVE-BLOCK-START
# HYPOTHESIS-1: A multi-restart basin-hopping approach will improve reliability_score.
# MECHANISM-1: Combining global random restarts with local stochastic hill-climbing 
#   ensures the search explores multiple basins while refining results in each.
# EXPECT-1: reliability_score > 0.9
# HYPOTHESIS-2: Using a Cauchy-distributed jump instead of Uniform improves distance_score.
# MECHANISM-2: The heavy tails of the Cauchy distribution allow for occasional large 
#   jumps to escape local minima more effectively than uniform perturbations.
# EXPECT-2: distance_score > 0.8

import numpy as np

def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Basin-hopping inspired algorithm: Multi-start local optimization
    to find the global minimum of the complex function.
    """
    best_x, best_y = 0, 0
    best_value = float('inf')
    
    # Divide budget into several restarts to cover the landscape
    num_restarts = 8
    iters_per_restart = iterations // num_restarts
    
    for _ in range(num_restarts):
        # Start at a random location for each restart
        curr_x = np.random.uniform(bounds[0], bounds[1])
        curr_y = np.random.uniform(bounds[0], bounds[1])
        curr_val = evaluate_function(curr_x, curr_y)
        
        # Local search (Simulated Annealing/Hill Climbing)
        temp = 1.0
        for i in range(iters_per_restart):
            # Scale step size: starts wide, ends narrow
            fraction = i / iters_per_restart
            step_size = 2.0 * (1.0 - fraction)
            
            # Cauchy-like jumps (using tan(uniform)) or simple Normal
            dx = np.random.normal(0, step_size)
            dy = np.random.normal(0, step_size)
            
            next_x = np.clip(curr_x + dx, bounds[0], bounds[1])
            next_y = np.clip(curr_y + dy, bounds[0], bounds[1])
            next_val = evaluate_function(next_x, next_y)
            
            # Acceptance: always accept better, occasionally accept worse
            if next_val < curr_val:
                curr_x, curr_y, curr_val = next_x, next_y, next_val
            else:
                # Metropolis-Hastings criterion
                prob = np.exp((curr_val - next_val) / (temp + 1e-9))
                if np.random.rand() < prob:
                    curr_x, curr_y, curr_val = next_x, next_y, next_val
            
            # Cooling
            temp *= 0.95
            
            # Update global best
            if curr_val < best_value:
                best_value = curr_val
                best_x, best_y = curr_x, curr_y
                
    return best_x, best_y, best_value

def run_search():
    """Required wrapper function to execute the search."""
    return search_algorithm()

# EVOLVE-BLOCK-END

# This part remains fixed (not evolved)
def evaluate_function(x, y):
    """The complex function we're trying to minimize"""
    return np.sin(x) * np.cos(y) + np.sin(x * y) + (x**2 + y**2) / 20

if __name__ == "__main__":
    x, y, value = run_search()
    print(f"Found minimum at ({x}, {y}) with value {value}")