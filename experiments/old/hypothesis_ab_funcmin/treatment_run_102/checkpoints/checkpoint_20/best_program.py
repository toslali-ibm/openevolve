# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Hybrid global-local sampling with adaptive probability improves combined_score.
# MECHANISM-1: Maintaining a small but constant chance of global jumps throughout the search prevents trapping in local minima while allowing refinement.
# EXPECT-1: combined_score > 1.45
# HYPOTHESIS-2: Periodic relocation to the best-known point improves distance_score.
# MECHANISM-2: Resetting the 'current' walker to the 'best' position every few iterations focuses the local search on the most promising basin found so far.
# EXPECT-2: distance_score > 0.95
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    low, high = bounds
    best_x, best_y = np.random.uniform(low, high, 2)
    best_val = evaluate_function(best_x, best_y)
    curr_x, curr_y, curr_val = best_x, best_y, best_val
    
    for i in range(iterations):
        t = i / iterations
        temp = (1.0 - t) ** 2  # Parabolic cooling
        
        # Hybrid strategy: global jump prob decreases but stays > 0
        p_global = 0.3 * (1.0 - t) + 0.02
        if np.random.rand() < p_global:
            nx, ny = np.random.uniform(low, high, 2)
        else:
            # Periodic exploitation: move current back to best to refine the best basin
            if i % 20 == 0: curr_x, curr_y, curr_val = best_x, best_y, best_val
            step = 2.0 * temp + 0.01
            nx = np.clip(curr_x + np.random.normal(0, step), low, high)
            ny = np.clip(curr_y + np.random.normal(0, step), low, high)
            
        n_val = evaluate_function(nx, ny)
        if n_val < curr_val or np.random.rand() < np.exp((curr_val - n_val) / (temp + 1e-6)):
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
