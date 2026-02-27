# EVOLVE-BLOCK-START
"""
Optimized constructor-based circle packing for n=26 circles.
Uses a dense hexagonal lattice base with iterative force-directed relaxation
to maximize the sum of radii within a unit square.
"""
import numpy as np

def construct_packing():
    """
    Constructs a 26-circle packing using a hexagonal grid base
    followed by a repulsion-relaxation step to maximize spacing.
    """
    n = 26
    # Create a hexagonal grid slightly larger than needed to select best points
    centers = []
    # Approx 5.1 circles per row/column for n=26
    d_guess = 1.0 / 4.6
    for r in range(6):
        for c in range(6):
            x = (c + 0.5 * (r % 2)) * d_guess
            y = r * (np.sqrt(3) / 2) * d_guess
            centers.append([x, y])
    
    centers = np.array(centers[:n])
    
    # Scale and center the initial grid into the unit square
    centers -= np.min(centers, axis=0)
    centers /= np.max(centers)
    centers = 0.1 + 0.8 * centers 

    # Force-directed relaxation (repulsion)
    # This helps circles find a more optimal distribution for sum of radii
    learning_rate = 0.02
    for _ in range(60):
        forces = np.zeros_like(centers)
        for i in range(n):
            for j in range(i + 1, n):
                diff = centers[i] - centers[j]
                dist = np.linalg.norm(diff)
                if dist < 0.2:  # Interaction radius
                    force = (diff / (dist + 1e-6)) * (0.2 - dist)
                    forces[i] += force
                    forces[j] -= force
        
        centers += forces * learning_rate
        # Keep centers in bounds allowing for a minimum radius
        centers = np.clip(centers, 0.04, 0.96)

    radii = compute_max_radii(centers)
    sum_radii = np.sum(radii)
    
    return centers, radii, sum_radii

def compute_max_radii(centers):
    """
    Computes the maximum valid radii for the given centers.
    Ensures circles stay within [0, 1] and do not overlap.
    """
    n = centers.shape[0]
    # Initial radii: distance to nearest wall
    radii = np.min(np.concatenate([centers, 1 - centers], axis=1), axis=1)
    
    # Iteratively resolve overlaps by shrinking radii
    # To maximize sum, we shrink the larger radius in an overlap more gently
    for _ in range(30):
        for i in range(n):
            for j in range(i + 1, n):
                d = np.linalg.norm(centers[i] - centers[j])
                if radii[i] + radii[j] > d:
                    overlap = (radii[i] + radii[j]) - d
                    # Proportional adjustment
                    r_sum = radii[i] + radii[j]
                    radii[i] -= overlap * (radii[i] / r_sum)
                    radii[j] -= overlap * (radii[j] / r_sum)
    return radii

def run_packing():
    """Fixed entry point for the evaluator"""
    return construct_packing()

# EVOLVE-BLOCK-END