# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Integrating a Simulated Annealing-like acceptance criterion into the local search will improve value_score and distance_score.
# MECHANISM-1: By allowing the local search to probabilistically accept slightly worse solutions (Metropolis criterion), it can temporarily escape shallow local minima within a basin, preventing premature convergence and leading to a deeper, more accurate minimum. The decreasing 'temperature' ensures eventual convergence.
# EXPECT-1: value_score > 0.9996
# HYPOTHESIS-2: Refining the adaptive step size and temperature cooling schedule for the local search will improve combined_score.
# MECHANISM-2: A more carefully tuned exponential decay for the step size (exploration) and a geometric cooling schedule for temperature (acceptance probability) within each local search phase will balance exploration and exploitation better, leading to more consistent and higher quality results.
# EXPECT-2: combined_score > 1.5

import numpy as np

def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Improved search using multi-start local optimization (Basin Hopping) with
    Simulated Annealing-like local search for better local minimum discovery.
    """
    best_x, best_y = 0, 0
    best_val = float('inf')
    
    low, high = bounds
    search_space_range = high - low
    
    # Divide iterations between finding basins and local refinement.
    # Reduced number of global starts to allow more iterations for each local SA-like search,
    # enabling deeper exploration within each basin.
    num_starts = 10 
    iters_per_local = iterations // num_starts
    
    # Ensure at least one iteration per local search
    if iters_per_local == 0:
        iters_per_local = 1
        num_starts = iterations # Fallback for very low iterations
    
    for _ in range(num_starts):
        # 1. Global Step: Random restart to find a new basin of attraction
        curr_x = np.random.uniform(low, high)
        curr_y = np.random.uniform(low, high)
        curr_val = evaluate_function(curr_x, curr_y)
        
        # Keep track of the best point found *during* the current local search.
        # This is important because SA can accept worse solutions, so the final 'curr_val'
        # of a local search might not be its best discovery.
        local_best_x, local_best_y, local_best_val = curr_x, curr_y, curr_val

        # 2. Local Step: Adaptive Simulated Annealing-like search
        # Initial perturbation range, e.g., 20% of total search space range
        initial_step_scale = search_space_range / 5 
        # Starting temperature for the SA-like local search. Tuned for local exploration.
        initial_temp = 0.1 
        
        # Calculate decay factors for step scale and temperature.
        # Both decay to 1% of their initial value over `iters_per_local` steps.
        # This ensures exploration at the beginning and fine-tuning at the end.
        if iters_per_local > 1:
            step_decay_factor = (0.01)**(1.0 / (iters_per_local - 1))
            temp_cooling_rate = (0.01)**(1.0 / (iters_per_local - 1))
        else: # Handle case where only 1 iteration is available
            step_decay_factor = 0.0 # No decay, step_scale will stay initial_step_scale
            temp_cooling_rate = 0.0 # No decay, temp will stay initial_temp
        
        for i in range(iters_per_local):
            # Adaptive step size: exponential decay
            current_step_scale = initial_step_scale * (step_decay_factor ** i)

            # Current temperature for acceptance probability: geometric cooling
            current_temp = initial_temp * (temp_cooling_rate ** i)
            # Prevent temperature from becoming too small too early, which would halt exploration
            if current_temp < 1e-7: current_temp = 1e-7 # A small non-zero lower bound
            
            # Generate a new candidate point by perturbing the current best in the basin
            # using a normal distribution with adaptive standard deviation.
            dx = np.random.normal(0, current_step_scale)
            dy = np.random.normal(0, current_step_scale)
            
            next_x = np.clip(curr_x + dx, low, high)
            next_y = np.clip(curr_y + dy, low, high)
            next_val = evaluate_function(next_x, next_y)
            
            delta = next_val - curr_val
            
            # Metropolis criterion: Accept if new solution is better,
            # or probabilistically if it's worse (to escape local minima).
            if delta < 0 or np.random.rand() < np.exp(-delta / current_temp):
                curr_x, curr_y, curr_val = next_x, next_y, next_val
                
                # Always update the local best if a better solution is found,
                # even if SA later accepts a worse one.
                if curr_val < local_best_val:
                    local_best_val = curr_val
                    local_best_x, local_best_y = curr_x, curr_y
        
        # After the local SA-like search completes, use the best point found *during*
        # that local search to update the global best. This ensures we don't end
        # up with a suboptimal point if the last SA move was an "uphill" one.
        if local_best_val < best_val:
            best_val = local_best_val
            best_x, best_y = local_best_x, local_best_y
            
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