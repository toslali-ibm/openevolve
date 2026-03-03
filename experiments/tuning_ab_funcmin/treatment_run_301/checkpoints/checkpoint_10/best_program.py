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
    # Population-based approach for better global coverage
    pop_size = 5  # @TUNE [5, 30] int @TUNED(was=12, gain=+0.00, best_impact=distance_score:+0.0036)
    mutation_rate = 0.3904  # @TUNE [0.1, 0.9] @TUNED(was=0.7, gain=+0.00, best_impact=distance_score:+0.0036)
    step_scale = 0.9818  # @TUNE [0.5, 3.0] @TUNED(was=1.5, gain=+0.00, best_impact=distance_score:+0.0036)
    
    # Initialize population
    pop = np.random.uniform(bounds[0], bounds[1], (pop_size, 2))
    vals = np.array([evaluate_function(p[0], p[1]) for p in pop])
    
    best_idx = np.argmin(vals)
    best_x, best_y = pop[best_idx]
    best_value = vals[best_idx]

    for i in range(iterations // pop_size):
        # Adaptive shrinkage of search radius
        radius = step_scale * (1.0 - i / (iterations / pop_size))
        
        for j in range(pop_size):
            # Differential mutation: move towards best or random perturbation
            if np.random.rand() < mutation_rate:
                # Move towards best with some noise
                move_x = (best_x - pop[j, 0]) * np.random.rand() + np.random.normal(0, radius)
                move_y = (best_y - pop[j, 1]) * np.random.rand() + np.random.normal(0, radius)
            else:
                # Wide exploration jump
                move_x, move_y = np.random.uniform(bounds[0], bounds[1], 2) - pop[j]

            nx = np.clip(pop[j, 0] + move_x, bounds[0], bounds[1])
            ny = np.clip(pop[j, 1] + move_y, bounds[0], bounds[1])
            nv = evaluate_function(nx, ny)

            if nv < vals[j]:
                pop[j], vals[j] = [nx, ny], nv
                if nv < best_value:
                    best_x, best_y, best_value = nx, ny, nv

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
