# EVOLVE-BLOCK-START
# HYPOTHESIS-1: Multi-start Simulated Annealing improves reliability_score and distance_score.
# MECHANISM-1: Dividing the iteration budget into multiple restarts from random positions increases the probability of hitting the global minimum's basin of attraction.
# EXPECT-1: reliability_score > 0.98
# HYPOTHESIS-2: A combination of high-frequency early global jumps and late-stage local refinement improves value_score.
# MECHANISM-2: Frequent jumps at the start allow for broad exploration; as iterations progress, focusing on local refinement ensures the algorithm settles precisely.
# EXPECT-2: combined_score > 1.48
import numpy as np

def search_algorithm(iterations=1000, bounds=(-5, 5)):
    low, high = bounds
    best_x, best_y, best_val = 0, 0, float('inf')
    num_starts = 5
    iters_per_start = iterations // num_starts

    for _ in range(num_starts):
        cx = np.random.uniform(low, high)
        cy = np.random.uniform(low, high)
        cv = evaluate_function(cx, cy)
        
        for i in range(iters_per_start):
            t = (1.0 - (i / iters_per_start))**2
            if i % 15 == 0 and t > 0.2:
                nx, ny = np.random.uniform(low, high, 2)
            else:
                s = 3.0 * t
                nx = np.clip(cx + np.random.normal(0, s), low, high)
                ny = np.clip(cy + np.random.normal(0, s), low, high)
            
            nv = evaluate_function(nx, ny)
            if nv < cv or np.random.rand() < np.exp((cv - nv) / (t + 1e-7)):
                cx, cy, cv = nx, ny, nv
            if cv < best_val:
                best_x, best_y, best_val = cx, cy, cv
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
