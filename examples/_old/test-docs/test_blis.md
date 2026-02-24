./simulation_worker run --model meta-llama/llama-3.1-8b-instruct --hardware H100 --tp 1 --num-instances 4 --routing-policy weighted --routing-cache-weight 0.9 --routing-load-weight 0.1 --max-prompts 500 --rate 20 --trace-level decisions --summarize-trace



./simulation_worker run \
--model meta-llama/llama-3.1-8b-instruct \
--hardware H100 --tp 1 --num-instances 4 \
--policy-config ../routing_policy.yaml



./simulation_worker run \
--model meta-llama/llama-3.1-8b-instruct \
--hardware H100 --tp 1 --num-instances 4 \
--policy-config ../routing_policy.yaml \
--workload-spec ../workload_mixed.yaml 



./simulation_worker run \
--model meta-llama/llama-3.1-8b-instruct \
--hardware H100 --tp 1 --num-instances 4 \
--routing-policy weighted --routing-cache-weight 0.9 --routing-load-weight 0.1 --max-prompts 500 --rate 20 \
--log info


INFO[0000] {
  "instance_id": "cluster",
  "sim_start_timestamp": "2026-02-18 11:20:52",
  "sim_end_timestamp": "2026-02-18 11:20:53",
  "completed_requests": 500,
  "total_input_tokens": 259082,
  "total_output_tokens": 268674,
  "vllm_estimated_duration_s": 29.610209,
  "simulation_duration_s": 0.732220083,
  "responses_per_sec": 16.88606790988878,
  "tokens_per_sec": 9073.694819242917,
  "e2e_mean_ms": 5104.905608,
  "e2e_p90_ms": 8080.4035,
  "e2e_p95_ms": 8920.49915,
  "e2e_p99_ms": 10191.99566,
  "ttft_mean_ms": 22.284828,
  "ttft_p90_ms": 29.316300000000002,
  "ttft_p95_ms": 31.6722,
  "ttft_p99_ms": 34.25163,
  "itl_mean_ms": 9.441143609709705,
  "itl_p90_ms": 9.223,
  "itl_p95_ms": 9.229,
  "itl_p99_ms": 19.441,
  "scheduling_delay_p99_ms": 7.40965
} 


./simulation_worker run \
--model meta-llama/llama-3.1-8b-instruct \
--hardware H100 --tp 1 --num-instances 4 \
--routing-policy weighted --routing-cache-weight 0.1 --routing-load-weight 0.9 --max-prompts 500 --rate 20 \
--log info
