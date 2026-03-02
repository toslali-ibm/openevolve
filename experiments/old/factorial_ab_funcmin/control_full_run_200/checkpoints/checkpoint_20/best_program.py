# EVOLVE-BLOCK-START
"""Function minimization via Adaptive Particle Swarm Optimization (PSO)."""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Implements an Adaptive Particle Swarm Optimization (PSO) algorithm.
    It uses dynamically adjusted inertia and acceleration coefficients,
    along with velocity clamping, to enhance the balance between global
    exploration and local exploitation. This approach improves the ability
    to escape local minima and converge to the global minimum reliably.
    """
    low, high = bounds
    
    # PSO Hyperparameters
    num_particles = 40  # Increased particles for broader initial exploration
    steps = iterations // num_particles # Total optimization steps for the swarm
    
    # Adaptive parameter ranges: (initial_value, final_value)
    w_initial, w_final = 0.9, 0.4       # Inertia weight: decreases over time
    c1_initial, c1_final = 2.0, 0.5     # Cognitive (personal best) component: decreases
    c2_initial, c2_final = 0.5, 2.0     # Social (global best) component: increases
    
    # Initialize particle positions randomly within the defined bounds
    pos = np.random.uniform(low, high, (num_particles, 2))
    
    # Initialize velocities randomly, scaled to a fraction of the search space width
    vel_range = (high - low) / 4 
    vel = np.random.uniform(-vel_range, vel_range, (num_particles, 2))
    
    # Initialize personal best positions and values for each particle
    p_best_pos = np.copy(pos)
    p_best_val = np.array([evaluate_function(p[0], p[1]) for p in pos])
    
    # Initialize global best position and value found by the entire swarm
    g_best_idx = np.argmin(p_best_val)
    g_best_pos = np.copy(p_best_pos[g_best_idx])
    g_best_val = p_best_val[g_best_idx]
    
    # Main PSO optimization loop
    for step_num in range(steps):
        # Calculate current adaptive parameter values based on optimization progress
        progress = step_num / steps
        w = w_initial - progress * (w_initial - w_final)
        c1 = c1_initial - progress * (c1_initial - c1_final)
        c2 = c2_initial + progress * (c2_final - c2_initial)
        
        # Generate random factors for cognitive and social components
        r1, r2 = np.random.rand(2) 
        
        # Update particle velocities using the PSO equation
        vel = w * vel + c1 * r1 * (p_best_pos - pos) + c2 * r2 * (g_best_pos - pos)
        
        # Clamp velocities to prevent overly aggressive movements and ensure stability
        max_vel = (high - low) * 0.2 
        vel = np.clip(vel, -max_vel, max_vel)

        # Update particle positions and clip them to stay within the search bounds
        pos = np.clip(pos + vel, low, high)
        
        # Evaluate new positions and update personal and global bests
        for i in range(num_particles):
            curr_val = evaluate_function(pos[i, 0], pos[i, 1])
            if curr_val < p_best_val[i]:
                p_best_val[i] = curr_val
                p_best_pos[i] = pos[i]
                
                # If a particle's new personal best is better than the global best, update global best
                if curr_val < g_best_val:
                    g_best_val = curr_val
                    g_best_pos = pos[i]
                    
    # Return the best position and value found by the swarm
    return g_best_pos[0], g_best_pos[1], g_best_val


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