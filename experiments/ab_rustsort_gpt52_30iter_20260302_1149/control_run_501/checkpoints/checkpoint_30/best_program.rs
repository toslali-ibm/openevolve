// Adaptive Sorting Algorithm Implementation
// This program implements a sorting algorithm that can be evolved to adapt to different data patterns

// EVOLVE-BLOCK-START
pub fn adaptive_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 || arr.windows(2).all(|w| w[0] <= w[1]) { return; }
    if n <= 32 || is_nearly_sorted(arr) { insertion_sort(arr); } else { arr.sort_unstable(); }
}

fn is_nearly_sorted<T: Ord>(arr: &[T]) -> bool {
    let n = arr.len();
    let mut bad = 0usize;
    let limit = (n / 64).max(1);
    for i in 1..n {
        if arr[i - 1] > arr[i] {
            bad += 1;
            if bad > limit { return false; }
        }
    }
    true
}

fn insertion_sort<T: Ord>(a: &mut [T]) {
    for i in 1..a.len() {
        let mut j = i;
        while j > 0 && a[j - 1] > a[i] { j -= 1; }
        if j != i { a[j..=i].rotate_right(1); }
    }
}
// EVOLVE-BLOCK-END

// Benchmark function to test the sort implementation
pub fn run_benchmark(test_data: Vec<Vec<i32>>) -> BenchmarkResults {
    let mut r = BenchmarkResults { times: vec![], correctness: vec![], adaptability_score: 0.0 };
    for data in test_data {
        let mut a = data.clone();
        let t = std::time::Instant::now();
        adaptive_sort(&mut a);
        r.times.push(t.elapsed().as_secs_f64());
        r.correctness.push(a.windows(2).all(|w| w[0] <= w[1]));
    }
    let n = r.times.len() as f64;
    if n > 1.0 {
        let mean = r.times.iter().sum::<f64>() / n;
        let var = r.times.iter().map(|t| (t - mean) * (t - mean)).sum::<f64>() / n;
        r.adaptability_score = 1.0 / (1.0 + var.sqrt());
    }
    r
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