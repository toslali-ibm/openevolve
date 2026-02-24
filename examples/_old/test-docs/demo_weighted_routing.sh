#!/bin/bash
# Demo script to compare cache-dominant vs load-dominant routing

set -e

# Change to the inference-sim directory
cd "$(dirname "$0")/inference-sim"

echo "======================================================================"
echo "Weighted Routing Comparison Demo"
echo "======================================================================"
echo ""
echo "This demo compares two routing strategies at --rate 1000:"
echo "  1. Cache-dominant: Favors instances with most free KV blocks"
echo "  2. Load-dominant: Spreads requests evenly across instances"
echo ""
echo "Compare the 'Target Distribution' in each trace summary."
echo "======================================================================"
echo ""

# Cache-dominant configuration
echo ">>> Running CACHE-DOMINANT routing (cache=0.9, load=0.1)..."
echo ""
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --num-instances 4 --routing-policy weighted \
  --routing-cache-weight 0.9 --routing-load-weight 0.1 \
  --max-prompts 500 --rate 1000 \
  --trace-level decisions --summarize-trace --log info

echo ""
echo "======================================================================"
echo ""
echo ">>> Running LOAD-DOMINANT routing (cache=0.1, load=0.9)..."
echo ""

# Load-dominant configuration
./simulation_worker run \
  --model meta-llama/llama-3.1-8b-instruct \
  --num-instances 4 --routing-policy weighted \
  --routing-cache-weight 0.1 --routing-load-weight 0.9 \
  --max-prompts 500 --rate 1000 \
  --trace-level decisions --summarize-trace --log info

echo ""
echo "======================================================================"
echo "Demo complete! Compare the Target Distribution values above."
echo "======================================================================"



INFO[0000] {
  "instance_id": "cluster",
  "sim_start_timestamp": "2026-02-18 11:36:14",
  "sim_end_timestamp": "2026-02-18 11:36:15",
  "completed_requests": 500,
  "total_input_tokens": 259082,
  "total_output_tokens": 268674,
  "vllm_estimated_duration_s": 10.237475,
  "simulation_duration_s": 0.718432375,
  "responses_per_sec": 48.84016810785863,
  "tokens_per_sec": 26244.166652421616,
  "e2e_mean_ms": 5850.348685999999,
  "e2e_p90_ms": 8624.8602,
  "e2e_p95_ms": 9529.62025,
  "e2e_p99_ms": 10645.12818,
  "ttft_mean_ms": 484.29184200000003,
  "ttft_p90_ms": 827.1365999999999,
  "ttft_p95_ms": 865.35,
  "ttft_p99_ms": 908.15796,
  "itl_mean_ms": 9.967635886081121,
  "itl_p90_ms": 9.058,
  "itl_p95_ms": 9.061,
  "itl_p99_ms": 43.851,
  "scheduling_delay_p99_ms": 864.1058999999999
} 