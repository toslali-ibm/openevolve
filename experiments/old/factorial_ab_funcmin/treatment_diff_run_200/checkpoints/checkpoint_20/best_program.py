# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Simulated Annealing with local exploitation improves value_score and distance_score.
# MECHANISM-1: Combining wide-range exploration with localized Gaussian perturbations allows the
#   algorithm to escape local minima while refining the search in promising regions.
# EXPECT-1: combined_score > 1.3
# HYPOTHESIS-2: Iterative narrowing of search radius improves reliability_score.
# MECHANISM-2: Reducing the step size over time ensures convergence on the global minimum
#   once the general vicinity is located, preventing "jumping out" of the optimal basin.
# EXPECT-2: reliability_score > 0.95
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    An improved search algorithm using a hybrid of global exploration 
    and local refinement (Simulated Annealing style).
    """
    low, high = bounds
    # Initial grid-based sampling to find the best basin (H1)
    grid_size = 8
    points = np.linspace(low, high, grid_size)
    best_x, best_y, best_value = 0, 0, float('inf')
    for gx in points:
        for gy in points:
            val = evaluate_function(gx, gy)
            if val < best_value:
                best_x, best_y, best_value = gx, gy, val

    for i in range(iterations):
        # Progressively reduce the search radius with a faster cooling schedule (H2)
        temp = (1 - i / iterations)**2
        
        # Mix global exploration and local exploitation with decaying exploration rate (H2)
        if np.random.rand() < 0.1 * temp: # Global jump probability decays with temp
            # Global jump
            x = np.random.uniform(low, high)
            y = np.random.uniform(low, high)
        else:
            # Local refinement: search around current best with decaying radius (H2)
            sigma = (high - low) * 0.15 * temp # Slightly smaller initial sigma, decaying faster
            x = np.clip(best_x + np.random.normal(0, sigma), low, high)
            y = np.clip(best_y + np.random.normal(0, sigma), low, high)
            
        value = evaluate_function(x, y)

        if value < best_value:
            best_value = value
            best_x, best_y = x, y

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
