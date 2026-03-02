// Adaptive Sorting Algorithm Implementation
// This program implements a sorting algorithm that can be evolved to adapt to different data patterns



// EVOLVE-BLOCK-START
// Initial implementation: Simple quicksort
// This can be evolved to:
// - Hybrid algorithms (introsort, timsort-like)
// - Adaptive pivot selection
// - Special handling for nearly sorted data
// - Switching to different algorithms based on data characteristics

pub fn adaptive_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 { return; }

    if n <= 24 { insertion_sort(arr); return; }

    // Avoid always scanning huge random inputs; sample first.
    if n <= 256 {
        if is_nearly_sorted_adjacent(arr) { insertion_sort(arr); return; }
    } else if is_nearly_sorted_sampled(arr) {
        insertion_sort(arr);
        return;
    }

    arr.sort_unstable();
}

fn is_nearly_sorted_adjacent<T: Ord>(arr: &[T]) -> bool {
    let limit = arr.len() / 16 + 1;
    let mut bad = 0usize;
    for w in arr.windows(2) {
        if w[0] > w[1] {
            bad += 1;
            if bad > limit { return false; }
        }
    }
    true
}

fn is_nearly_sorted_sampled<T: Ord>(arr: &[T]) -> bool {
    let n = arr.len();
    let step = (n / 64).max(1);
    let mut bad = 0usize;
    let mut i = 1;
    while i < n {
        if arr[i - 1] > arr[i] {
            bad += 1;
            if bad > 2 { return false; }
        }
        i += step;
    }
    true
}

fn insertion_sort<T: Ord>(arr: &mut [T]) {
    for i in 1..arr.len() {
        let mut j = i;
        while j > 0 && arr[j - 1] > arr[j] {
            arr.swap(j, j - 1);
            j -= 1;
        }
    }
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