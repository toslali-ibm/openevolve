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
    
    # Initialize with a random point as the current state
    current_x = np.random.uniform(low, high)
    current_y = np.random.uniform(low, high)
    current_value = evaluate_function(current_x, current_y)

    # The best point found globally during the search
    best_x, best_y = current_x, current_y
    best_value = current_value

    initial_temp = 1.0  # Starting temperature
    min_temp = 1e-5     # Minimum temperature to avoid division by zero

    for i in range(iterations):
        # Cooling schedule: temperature decreases over iterations
        temp = max(initial_temp * (1 - i / iterations), min_temp)
        
        # Generate a candidate point from the current state
        candidate_x, candidate_y = current_x, current_y
        
        # Mix global exploration (random jumps) and local exploitation (Gaussian perturbations)
        if np.random.rand() < 0.2: # Probability for a global jump (exploration)
            candidate_x = np.random.uniform(low, high)
            candidate_y = np.random.uniform(low, high)
        else:
            # Local refinement: search around current point with a step size (sigma)
            # Sigma scales with the search range and current temperature
            sigma = (high - low) * 0.2 * (temp / initial_temp)
            candidate_x = np.clip(current_x + np.random.normal(0, sigma), low, high)
            candidate_y = np.clip(current_y + np.random.normal(0, sigma), low, high)
            
        candidate_value = evaluate_function(candidate_x, candidate_y)

        # Simulated Annealing acceptance criterion (Metropolis-Hastings)
        if candidate_value < current_value:
            # Always accept better solutions
            current_x, current_y = candidate_x, candidate_y
            current_value = candidate_value
        else:
            # Accept worse solutions with a probability that decreases with temperature
            acceptance_prob = np.exp(-(candidate_value - current_value) / temp)
            if np.random.rand() < acceptance_prob:
                current_x, current_y = candidate_x, candidate_y
                current_value = candidate_value
        
        # Update the overall best solution found so far
        if current_value < best_value:
            best_x, best_y = current_x, current_y
            best_value = current_value

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
