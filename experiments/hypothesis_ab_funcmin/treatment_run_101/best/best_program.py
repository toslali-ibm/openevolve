# EVOLVE-BLOCK-START
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    A simple random search algorithm that often gets stuck in local minima.

    Args:
        iterations: Number of iterations to run
        bounds: Bounds for the search space (min, max)

    Returns:
        Tuple of (best_x, best_y, best_value)
    """
    # Multi-start Hill Climbing / Simulated Annealing hybrid with proper state management
    current_x, current_y = np.random.uniform(*bounds, 2)
    current_value = evaluate_function(current_x, current_y)
    
    best_x, best_y, best_value = current_x, current_y, current_value # Initialize global best
    
    # Use 20% of budget for global sampling, 80% for refinement
    for i in range(iterations):
        temp = 1.0 - (i / iterations)
        
        # Candidate point generation
        if i % 10 == 0: # Global jump
            candidate_x, candidate_y = np.random.uniform(*bounds, 2)
        else: # Local perturbation around current_x, current_y
            # Increased scale factor from 0.1 to 0.2 for better initial exploration (H2)
            scale = (bounds[1] - bounds[0]) * 0.2 * temp 
            candidate_x = np.clip(current_x + np.random.normal(0, scale), *bounds)
            candidate_y = np.clip(current_y + np.random.normal(0, scale), *bounds)
            
        candidate_value = evaluate_function(candidate_x, candidate_y)
        
        # Acceptance criterion for current state (H1)
        if candidate_value < current_value or np.random.rand() < np.exp((current_value - candidate_value) / (temp + 1e-9)):
            current_x, current_y, current_value = candidate_x, candidate_y, candidate_value
            
            # Update global best if current state is better
            if current_value < best_value:
                best_x, best_y, best_value = current_x, current_y, current_value

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
