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
    low, high = bounds
    best_x, best_y, best_val = 0, 0, float('inf')
    # Multi-restart approach: 5 restarts for better global coverage
    for _ in range(5):
        curr_x, curr_y = np.random.uniform(low, high, 2)
        curr_val = evaluate_function(curr_x, curr_y)
        temp = 1.0
        for i in range(iterations // 5):
            # Exponential cooling and shrinking step
            temp *= 0.98
            step = 3.0 * (temp + 0.01)
            # Mix local exploitation and occasional global perturbation
            if i % 15 == 0:
                nx, ny = np.random.uniform(low, high, 2)
            else:
                nx = np.clip(curr_x + np.random.normal(0, step), low, high)
                ny = np.clip(curr_y + np.random.normal(0, step), low, high)
            
            n_val = evaluate_function(nx, ny)
            if n_val < curr_val or np.random.rand() < np.exp((curr_val - n_val) / (temp + 1e-7)):
                curr_x, curr_y, curr_val = nx, ny, n_val
                if curr_val < best_val:
                    best_x, best_y, best_val = nx, ny, n_val
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
