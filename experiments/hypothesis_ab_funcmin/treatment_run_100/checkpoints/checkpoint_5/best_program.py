# EVOLVE-BLOCK-START
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    An improved search algorithm using simulated annealing and local refinement.
    """
    low, high = bounds
    # Initial state
    curr_x = np.random.uniform(low, high)
    curr_y = np.random.uniform(low, high)
    curr_v = evaluate_function(curr_x, curr_y)
    
    best_x, best_y, best_v = curr_x, curr_y, curr_v

    for i in range(iterations):
        # Temperature schedule decreases linearly
        temp = 1.0 * (1 - i / iterations)
        
        # Mix global jumps with local refinement
        if i % 15 == 0:
            # Global jump to explore new basins
            nx = np.random.uniform(low, high)
            ny = np.random.uniform(low, high)
        else:
            # Local Gaussian perturbation scaled by temperature for fine-tuning
            scale = (high - low) * 0.1 * (temp + 0.01)
            nx = np.clip(curr_x + np.random.normal(0, scale), low, high)
            ny = np.clip(curr_y + np.random.normal(0, scale), low, high)
            
        nv = evaluate_function(nx, ny)
        
        # Metropolis criterion: always accept better, occasionally accept worse
        if nv < curr_v or (temp > 0 and np.random.rand() < np.exp((curr_v - nv) / (temp * 0.5 + 1e-6))):
            curr_x, curr_y, curr_v = nx, ny, nv
            
            if curr_v < best_v:
                best_x, best_y, best_v = curr_x, curr_y, curr_v

    return best_x, best_y, best_v


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
