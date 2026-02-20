#!/bin/bash
# =============================================================================
# BLIS Workload Test Runner
# =============================================================================
# Runs BLIS simulation against all available workloads and reports cluster metrics.
#
# USAGE:
#   cd examples/blis_router
#   chmod +x run_all_workloads.sh
#   ./run_all_workloads.sh
#
# PREREQUISITES:
#   1. Build BLIS first:
#      cd inference-sim && go build -o simulation_worker main.go && cd ..
#
# OUTPUT:
#   For each workload: mean_e2e_ms, p90_e2e_ms, completed_requests
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLIS_DIR="$SCRIPT_DIR/inference-sim"
WORKLOAD_DIR="$SCRIPT_DIR"
POLICY_CONFIG="$SCRIPT_DIR/routing_policy.yaml"

# Coefficients from evaluator.py (Qwen/Qwen2.5-7B-Instruct)
ALPHA_COEFFS="4680.303204056608,0.0,0.0"
BETA_COEFFS="7051.796874715078,19.538416565504026,25.431830886933543"

# Check if simulation_worker exists
if [ ! -f "$BLIS_DIR/simulation_worker" ]; then
    echo "ERROR: simulation_worker not found. Build it first:"
    echo "  cd $BLIS_DIR && go build -o simulation_worker main.go"
    exit 1
fi

# All workloads to test (challenging scenarios for routing optimization)
WORKLOADS=(
    "workload_multi_tenant_chat.yaml"  # 5 tenants, multi-turn, 5000 reqs
    "workload_prefix_pressure.yaml"    # 8 prefix groups vs 4 instances, 8000 reqs
    "workload_context_growth.yaml"     # Multi-turn with context accumulation, 3000 reqs
    "workload_burst_steady.yaml"       # CV=5.0 bursts + steady realtime, 6000 reqs
)

echo "=============================================="
echo "BLIS Workload Test Results"
echo "=============================================="
printf "%-28s %12s %12s %12s\n" "WORKLOAD" "MEAN_E2E" "P90_E2E" "REQUESTS"
echo "----------------------------------------------"

for workload in "${WORKLOADS[@]}"; do
    workload_path="$WORKLOAD_DIR/$workload"

    if [ ! -f "$workload_path" ]; then
        printf "%-28s %12s %12s %12s\n" "$workload" "MISSING" "-" "-"
        continue
    fi

    # Build and print command
    cmd="$BLIS_DIR/simulation_worker run \
--model Qwen/Qwen2.5-7B-Instruct \
--hardware H100 \
--tp 1 \
--num-instances 4 \
--policy-config $POLICY_CONFIG \
--workload-spec $workload_path \
--alpha-coeffs $ALPHA_COEFFS \
--beta-coeffs $BETA_COEFFS \
--total-kv-blocks 65833 \
--max-num-running-reqs 256 \
--max-num-scheduled-tokens 4096 \
--log error"

    echo ""
    echo "Running: $workload"
    echo "$cmd"
    echo ""

    # Run simulation and capture output
    output=$("$BLIS_DIR/simulation_worker" run \
        --model "Qwen/Qwen2.5-7B-Instruct" \
        --hardware "H100" \
        --tp 1 \
        --num-instances 4 \
        --policy-config "$POLICY_CONFIG" \
        --workload-spec "$workload_path" \
        --alpha-coeffs "$ALPHA_COEFFS" \
        --beta-coeffs "$BETA_COEFFS" \
        --total-kv-blocks 65833 \
        --max-num-running-reqs 256 \
        --max-num-scheduled-tokens 4096 \
        --log error 2>&1) || {
        printf "%-28s %12s %12s %12s\n" "$workload" "ERROR" "-" "-"
        continue
    }

    # Parse cluster metrics from JSON output
    # Extract the cluster block (starts with "instance_id": "cluster")
    cluster_block=$(echo "$output" | grep -A 25 '"instance_id": "cluster"')

    if [ -z "$cluster_block" ]; then
        printf "%-28s %12s %12s %12s\n" "$workload" "NO_OUTPUT" "-" "-"
        continue
    fi

    # Extract metrics using sed (portable, no jq dependency)
    mean_e2e=$(echo "$cluster_block" | grep '"e2e_mean_ms":' | sed 's/.*: *\([0-9.]*\).*/\1/')
    p90_e2e=$(echo "$cluster_block" | grep '"e2e_p90_ms":' | sed 's/.*: *\([0-9.]*\).*/\1/')
    num_reqs=$(echo "$cluster_block" | grep '"completed_requests":' | sed 's/.*: *\([0-9]*\).*/\1/')

    # Format output
    mean_e2e_fmt=$(printf "%.1f" "$mean_e2e" 2>/dev/null || echo "-")
    p90_e2e_fmt=$(printf "%.1f" "$p90_e2e" 2>/dev/null || echo "-")
    num_reqs_fmt=${num_reqs:-"-"}

    printf "%-28s %12s %12s %12s\n" "$workload" "$mean_e2e_fmt" "$p90_e2e_fmt" "$num_reqs_fmt"
done

echo "=============================================="
echo "Done."
