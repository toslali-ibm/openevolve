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
    // Small slices: insertion sort is faster and avoids recursion overhead
    if n <= 24 { insertion_sort(arr); return; }
    // Nearly sorted: insertion sort tends to be very fast
    if is_nearly_sorted(arr, 0.02) { insertion_sort(arr); return; }
    quicksort(arr, 0, n - 1);
}

fn quicksort<T: Ord>(arr: &mut [T], mut low: usize, mut high: usize) {
    // Tail-recursion elimination: recurse on smaller side to cap stack depth
    while low < high {
        let p = partition(arr, low, high);
        if p > 0 && (p - low) < (high - p) {
            quicksort(arr, low, p - 1);
            low = p + 1;
        } else {
            if p + 1 <= high { quicksort(arr, p + 1, high); }
            if p == 0 { break; }
            high = p - 1;
        }
    }
}

fn partition<T: Ord>(arr: &mut [T], low: usize, high: usize) -> usize {
    // Median-of-three pivot to reduce worst-case behavior on sorted/structured inputs
    let mid = low + (high - low) / 2;
    if arr[mid] < arr[low] { arr.swap(mid, low); }
    if arr[high] < arr[low] { arr.swap(high, low); }
    if arr[high] < arr[mid] { arr.swap(high, mid); }
    arr.swap(mid, high);

    let mut i = low;
    for j in low..high {
        if arr[j] <= arr[high] {
            arr.swap(i, j);
            i += 1;
        }
    }
    arr.swap(i, high);
    i
}

// Helper function to detect if array is nearly sorted
fn is_nearly_sorted<T: Ord>(arr: &[T], threshold: f64) -> bool {
    // O(n) adjacent inversion heuristic (much cheaper than O(n^2) counting)
    let n = arr.len();
    if n <= 1 { return true; }
    let mut bad = 0usize;
    for i in 1..n {
        if arr[i - 1] > arr[i] { bad += 1; }
    }
    (bad as f64) <= (n as f64 * threshold)
}

// Helper function for insertion sort (useful for small arrays)
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