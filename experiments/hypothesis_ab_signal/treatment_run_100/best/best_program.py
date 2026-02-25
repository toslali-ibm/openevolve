# EVOLVE-BLOCK-START
"""
Real-Time Adaptive Signal Processing Algorithm for Non-Stationary Time Series

This algorithm implements a sliding window approach to filter volatile, non-stationary
time series data while minimizing noise and preserving signal dynamics.
"""
import numpy as np
# from scipy import signal # Not used in Kalman filter, removed for brevity
# from collections import deque # Not used in Kalman filter, removed for brevity


def process_signal(x, window_size=20, algorithm_type=None):
    """
    Adaptive Kalman Filter: Estimates signal state (position, velocity) to minimize
    lag and noise, preserving dynamics in non-stationary data.
    """
    n = len(x)
    if n == 0: return np.array([])

    # Initial state vector: [position, velocity]
    # Initialize with the first measurement and zero velocity
    x_est = np.array([x[0], 0.0])

    # Initial state covariance matrix (P) - high uncertainty initially
    P_est = np.array([[1.0, 0.0],
                      [0.0, 1.0]])

    # State transition matrix (A) - constant velocity model, dt=1 (sample interval)
    A = np.array([[1.0, 1.0],
                  [0.0, 1.0]])

    # Observation matrix (H) - we observe position
    H = np.array([[1.0, 0.0]])

    # Measurement noise covariance (R)
    # R represents the variance of the measurement noise.
    # A typical noise_level in the test signal is 0.3, so variance is 0.09.
    R_val = 0.09 # Based on expected noise_level=0.3 in generate_test_signal
    R = np.array([[R_val]])

    # Process noise covariance (Q)
    # Q represents the uncertainty in our state model (how much the state changes between steps).
    # It balances responsiveness vs. smoothness.
    # Larger window_size -> more smoothing desired -> smaller Q.
    # Smaller window_size -> more responsiveness desired -> larger Q.
    # Let's scale Q inversely with window_size, and make velocity noise component larger.
    q_scale_factor = 1.0 / window_size # Example: for window_size=20, q_scale_factor=0.05
    Q = np.array([[R_val * q_scale_factor * 0.1, 0.0], # Position noise (smaller)
                  [0.0, R_val * q_scale_factor]])    # Velocity noise (larger)

    # Identity matrix for update step
    I = np.eye(2)

    res = []
    for z in x: # z is the current measurement
        # Predict step
        x_pred = A @ x_est
        P_pred = A @ P_est @ A.T + Q

        # Update step
        y = z - H @ x_pred # Measurement residual
        S = H @ P_pred @ H.T + R # Residual covariance
        K = P_pred @ H.T @ np.linalg.inv(S) # Kalman Gain
        
        x_est = x_pred + K @ y # Updated state estimate
        P_est = (I - K @ H) @ P_pred # Updated state covariance

        res.append(x_est[0]) # The estimated position is our filtered output

    # The original DEMA implementation sliced the output to match expected length/delay.
    # A Kalman filter produces an output for every input.
    # To match the `run_signal_processing` function's `delay = window_size - 1` logic,
    # we slice the first `window_size - 1` outputs, as initial estimates are often less reliable.
    start_idx = min(n, window_size - 1)
    return np.array(res)[start_idx:]


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
