# EVOLVE-BLOCK-START
"""Function minimization example for OpenEvolve"""
import numpy as np


def search_algorithm(iterations=1000, bounds=(-5, 5)):
    """
    Hybrid Particle Swarm and Simulated Annealing with adaptive cooling.
    """
    low, high = bounds
    num_particles = 5
    # Initialize particles
    particles = [np.random.uniform(low, high, 2) for _ in range(num_particles)]
    p_best = [p.copy() for p in particles]
    p_best_v = [evaluate_function(p[0], p[1]) for p in particles]
    
    idx = np.argmin(p_best_v)
    gx, gy, gv = p_best[idx][0], p_best[idx][1], p_best_v[idx]
    
    for i in range(iterations):
        # Adaptive temperature: slower decay at start
        temp = 1.0 / (1 + np.log(1 + i))
        
        for j in range(num_particles):
            # Dynamic scale: global exploration early, local exploitation late
            scale = 1.5 * (1 - i/iterations)**2
            dx, dy = np.random.normal(0, scale, 2)
            
            # Particle move with momentum towards global best
            nx = np.clip(particles[j][0] + dx + 0.1*(gx - particles[j][0]), low, high)
            ny = np.clip(particles[j][1] + dy + 0.1*(gy - particles[j][1]), low, high)
            nv = evaluate_function(nx, ny)
            
            # SA-style acceptance
            if nv < p_best_v[j] or np.random.rand() < np.exp((p_best_v[j] - nv) / (temp + 1e-9)):
                particles[j] = [nx, ny]
                if nv < p_best_v[j]:
                    p_best_v[j], p_best[j] = nv, [nx, ny]
                    if nv < gv:
                        gx, gy, gv = nx, ny, nv
        
        # Occasional chaotic jump for the worst particle
        if i % 50 == 0:
            w_idx = np.argmax(p_best_v)
            particles[w_idx] = np.random.uniform(low, high, 2)
            
    return gx, gy, gv


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
