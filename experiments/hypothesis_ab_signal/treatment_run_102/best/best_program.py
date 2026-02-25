# EVOLVE-BLOCK-START
"""
Real-Time Adaptive Signal Processing Algorithm for Non-Stationary Time Series

This algorithm implements a sliding window approach to filter volatile, non-stationary
time series data while minimizing noise and preserving signal dynamics.
"""
import numpy as np
from scipy import signal
from collections import deque


def kalman_filter_process(x, window_size=20):
    """
    Kalman Filter for 1D signal with constant velocity model.
    Adapts Q and R based on window_size to balance responsiveness and smoothness.
    """
    n = len(x)
    if n == 0:
        return np.array([])
    
    # Ensure window_size is at least 1 for scaling purposes
    effective_window_size = max(1, window_size)

    # Initial state estimate: [position, velocity]
    # Start with the first measurement, assume zero initial velocity
    x_hat = np.array([x[0], 0.0]) 

    # Initial error covariance matrix (high uncertainty)
    P = np.eye(2) * 100.0 

    # State transition matrix (constant velocity model, dt=1)
    F = np.array([[1, 1],
                  [0, 1]])

    # Measurement matrix (we only measure position)
    H = np.array([[1, 0]])

    # Process noise covariance matrix (Q) and Measurement noise covariance matrix (R)
    # Tuning these based on window_size:
    # Larger window_size -> more smoothing desired.
    #   - Smaller Q (assume state is more stable, less process noise)
    #   - Larger R (trust measurements less, more measurement noise)
    
    # Heuristic scaling:
    # Q_factor: Inversely proportional to window_size (smaller window -> more dynamics -> larger Q)
    # R_factor: Proportional to window_size (larger window -> more smoothing -> larger R)
    
    # Using sqrt for a smoother transition in scaling.
    q_scale = 1.0 / np.sqrt(effective_window_size)
    r_scale = np.sqrt(effective_window_size)
    
    # Base values for Q and R, typical for signal processing
    base_q_pos = 0.001
    base_q_vel = 0.01
    base_r_meas = 0.1

    Q = np.array([[base_q_pos * q_scale, 0],
                  [0, base_q_vel * q_scale]])
    
    R = np.array([[base_r_meas * r_scale]])

    filtered_signal = np.zeros(n)
    
    # The first filtered value is the first input value
    filtered_signal[0] = x[0]
    
    for i in range(1, n):
        # Prediction step
        x_hat_minus = F @ x_hat
        P_minus = F @ P @ F.T + Q

        # Update step
        z_k = x[i] # Current measurement
        y_k = z_k - H @ x_hat_minus # Measurement residual
        S_k = H @ P_minus @ H.T + R # Residual covariance
        K_k = P_minus @ H.T @ np.linalg.inv(S_k) # Kalman Gain
        x_hat = x_hat_minus + K_k @ y_k # Updated state estimate
        P = (np.eye(2) - K_k @ H) @ P_minus # Updated error covariance

        filtered_signal[i] = x_hat[0] # The position estimate is the filtered value

    # Return sliced to match expected sliding window output length
    # This aligns with how the ZLEMA and WMA filters are typically evaluated,
    # accounting for an initial transient or "warm-up" period.
    if n < effective_window_size:
        return np.array([])
    return filtered_signal[effective_window_size-1:]


def process_signal(input_signal, window_size=20, algorithm_type=None):
    """
    Main signal processing function that applies the Kalman filter.
    """
    return kalman_filter_process(input_signal, window_size)


# EVOLVE-BLOCK-END


def generate_test_signal(length=1000, noise_level=0.3, seed=42):
    """
    Generate synthetic test signal with known characteristics.

    Args:
        length: Length of the signal
        noise_level: Standard deviation of noise to add
        seed: Random seed for reproducibility

    Returns:
        Tuple of (noisy_signal, clean_signal)
    """
    np.random.seed(seed)
    t = np.linspace(0, 10, length)

    # Create a complex signal with multiple components
    clean_signal = (
        2 * np.sin(2 * np.pi * 0.5 * t)  # Low frequency component
        + 1.5 * np.sin(2 * np.pi * 2 * t)  # Medium frequency component
        + 0.5 * np.sin(2 * np.pi * 5 * t)  # Higher frequency component
        + 0.8 * np.exp(-t / 5) * np.sin(2 * np.pi * 1.5 * t)  # Decaying oscillation
    )

    # Add non-stationary behavior
    trend = 0.1 * t * np.sin(0.2 * t)  # Slowly varying trend
    clean_signal += trend

    # Add random walk component for non-stationarity
    random_walk = np.cumsum(np.random.randn(length) * 0.05)
    clean_signal += random_walk

    # Add noise
    noise = np.random.normal(0, noise_level, length)
    noisy_signal = clean_signal + noise

    return noisy_signal, clean_signal


def run_signal_processing(signal_length=1000, noise_level=0.3, window_size=20):
    """
    Run the signal processing algorithm on a test signal.

    Returns:
        Dictionary containing results and metrics
    """
    # Generate test signal
    noisy_signal, clean_signal = generate_test_signal(signal_length, noise_level)

    # Process the signal
    filtered_signal = process_signal(noisy_signal, window_size, "enhanced")

    # Calculate basic metrics
    if len(filtered_signal) > 0:
        # Align signals for comparison (account for processing delay)
        delay = window_size - 1
        aligned_clean = clean_signal[delay:]
        aligned_noisy = noisy_signal[delay:]

        # Ensure same length
        min_length = min(len(filtered_signal), len(aligned_clean))
        filtered_signal = filtered_signal[:min_length]
        aligned_clean = aligned_clean[:min_length]
        aligned_noisy = aligned_noisy[:min_length]

        # Calculate correlation with clean signal
        correlation = np.corrcoef(filtered_signal, aligned_clean)[0, 1] if min_length > 1 else 0

        # Calculate noise reduction
        noise_before = np.var(aligned_noisy - aligned_clean)
        noise_after = np.var(filtered_signal - aligned_clean)
        noise_reduction = (noise_before - noise_after) / noise_before if noise_before > 0 else 0

        return {
            "filtered_signal": filtered_signal,
            "clean_signal": aligned_clean,
            "noisy_signal": aligned_noisy,
            "correlation": correlation,
            "noise_reduction": noise_reduction,
            "signal_length": min_length,
        }
    else:
        return {
            "filtered_signal": [],
            "clean_signal": [],
            "noisy_signal": [],
            "correlation": 0,
            "noise_reduction": 0,
            "signal_length": 0,
        }


if __name__ == "__main__":
    # Test the algorithm
    results = run_signal_processing()
    print(f"Signal processing completed!")
    print(f"Correlation with clean signal: {results['correlation']:.3f}")
    print(f"Noise reduction: {results['noise_reduction']:.3f}")
    print(f"Processed signal length: {results['signal_length']}")
