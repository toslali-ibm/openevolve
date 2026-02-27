# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Implementing Simulated Annealing with a hybrid exploration strategy will significantly improve the combined_score.
# MECHANISM-1: SA's probabilistic acceptance of worse solutions allows escaping local minima, while the cooling schedule focuses the search. The hybrid exploration (periodic global jumps + local Gaussian steps) balances broad exploration with fine-grained exploitation.
# EXPECT-1: combined_score > 1.35
# HYPOTHESIS-2: Periodic global jumps embedded in SA will enhance the reliability_score by preventing premature convergence.
# MECHANISM-2: By occasionally forcing the search to explore distant regions, the algorithm reduces the chance of getting permanently trapped in a sub-optimal local minimum, increasing the likelihood of finding the global minimum across multiple runs.
# EXPECT-2: reliability_score > 0.95
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Hybrid Simulated Annealing for global optimization.
    It combines probabilistic acceptance of worse solutions to escape local minima
    with a cooling schedule to guide convergence. Periodic global jumps ensure
    broader exploration.

    Args:
        iterations: Number of iterations to run
        bounds: Bounds for the search space (min, max)

    Returns:
        Tuple of (best_x, best_y, best_value)
    """
    low, high = bounds
    # Start at a random point within the bounds
    curr_x = np.random.uniform(low, high)
    curr_y = np.random.uniform(low, high)
    curr_val = evaluate_function(curr_x, curr_y)
    
    # Initialize the best found solution
    best_x, best_y, best_val = curr_x, curr_y, curr_val
    
    for i in range(iterations):
        # Linear cooling schedule: temperature decreases from 1.0 to 0.0
        temp = 1.0 - (i / iterations)
        
        # Exploration strategy: mix global jumps with local steps
        # Every 10th iteration, make a large, uniform global jump to explore widely
        if i % 10 == 0:
            next_x, next_y = np.random.uniform(low, high, 2)
        else:
            # Otherwise, make a local step using a Gaussian distribution
            # Step size decreases with temperature, allowing for finer search later
            step_size = 2.0 * temp 
            next_x = np.clip(curr_x + np.random.normal(0, step_size), low, high)
            next_y = np.clip(curr_y + np.random.normal(0, step_size), low, high)
            
        next_val = evaluate_function(next_x, next_y)
        
        # Metropolis Criterion:
        # Accept the new state if it's better, or probabilistically if it's worse.
        # The probability of accepting a worse state decreases with temperature.
        # Add a small constant to temp in the denominator to avoid division by zero
        # and ensure a valid probability even at very low temperatures.
        if next_val < curr_val or (temp > 1e-9 and np.random.rand() < np.exp((curr_val - next_val) / temp)):
            curr_x, curr_y, curr_val = next_x, next_y, next_val
            
        # Always update the overall best solution found so far
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
