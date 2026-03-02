 // Adaptive Sorting Algorithm Implementation
// This program implements a sorting algorithm that can be evolved to adapt to different data patterns

use std::cmp::Ordering;

// EVOLVE-BLOCK-START
// HYPOTHESIS-1: Switching to std slice sort_unstable improves performance_score by using Rusts highly optimized introsort.
 // MECHANISM-1: Delegating to the standard library reduces overhead, avoids worst-case quicksort, and removes Clone pivot costs.
 // EXPECT-1: performance_score > 0.985
 // RESULT-1: CONFIRMED (actual=0.9996502883410284)
// HYPOTHESIS-2: Removing unused helpers and Clone bounds improves combined_score by reducing code size and constraints.
 // MECHANISM-2: Less code and fewer trait bounds increase simplicity and applicability without hurting correctness.
 // EXPECT-2: combined_score > 0.986
 // RESULT-2: CONFIRMED (actual=0.9997747692403245)
// HYPOTHESIS-3: Early-exit check for already sorted inputs improves avg_time on common nearly-sorted cases.
 // MECHANISM-3: O(n) monotonicity scan avoids sorting work when the slice is already ordered.
 // EXPECT-3: avg_time < 0.0022
 // RESULT-3: CONFIRMED (actual=3.49834e-05)

pub fn adaptive_sort<T: Ord>(arr: &mut [T]) {
    if arr.len() <= 1 {
        return;
    }
    // Fast path: already sorted
    if arr.windows(2).all(|w| w[0] <= w[1]) {
        return;
    }
    // Use optimized standard library sort (introsort/pdqsort variant).
    arr.sort_unstable();
}
// EVOLVE-BLOCK-END

// Benchmark function to test the sort implementation
pub fn run_benchmark(test_data: Vec<Vec<i32>>) -> BenchmarkResults {
    let mut results = BenchmarkResults {
        times: Vec::new(),
        correctness: Vec::new(),
        adaptability_score: 0.0,
    };
    
    for data in test_data {
        let mut arr = data.clone();
        let start = std::time::Instant::now();
        
        adaptive_sort(&mut arr);
        
        let elapsed = start.elapsed();
        results.times.push(elapsed.as_secs_f64());
        
        // Check if correctly sorted
        let is_sorted = arr.windows(2).all(|w| w[0] <= w[1]);
        results.correctness.push(is_sorted);
    }
    
    // Calculate adaptability score based on performance variance
    if results.times.len() > 1 {
        let mean_time: f64 = results.times.iter().sum::<f64>() / results.times.len() as f64;
        let variance: f64 = results.times.iter()
            .map(|t| (t - mean_time).powi(2))
            .sum::<f64>() / results.times.len() as f64;
        
        // Lower variance means better adaptability
        results.adaptability_score = 1.0 / (1.0 + variance.sqrt());
    }
    
    results
}

#[derive(Debug)]
pub struct BenchmarkResults {
    pub times: Vec<f64>,
    pub correctness: Vec<bool>,
    pub adaptability_score: f64,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_basic_sort() {
        let mut arr = vec![3, 1, 4, 1, 5, 9, 2, 6];
        adaptive_sort(&mut arr);
        assert_eq!(arr, vec![1, 1, 2, 3, 4, 5, 6, 9]);
    }
    
    #[test]
    fn test_empty_array() {
        let mut arr: Vec<i32> = vec![];
        adaptive_sort(&mut arr);
        assert_eq!(arr, vec![]);
    }
    
    #[test]
    fn test_single_element() {
        let mut arr = vec![42];
        adaptive_sort(&mut arr);
        assert_eq!(arr, vec![42]);
    }
}