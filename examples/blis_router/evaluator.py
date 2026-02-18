"""
BLIS Router Evaluator

Evaluates evolved routing algorithms by:
1. Extracting Go code from Python wrapper
2. Writing evolved routing.go to BLIS source
3. Building BLIS
4. Running simulations on 3 workloads
5. Computing score based on average end-to-end latency

Score = -avg_latency (negative because we're minimizing latency)
Higher score = Lower latency = Better!
"""

import json
import re
import subprocess
import traceback
from pathlib import Path
from openevolve.evaluation_result import EvaluationResult


def extract_go_code(program_text: str) -> str:
    """Extract Go code from Python program text"""

    # Look for GO_ROUTING_CODE variable
    match = re.search(r'GO_ROUTING_CODE\s*=\s*"""(.*?)"""', program_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # If no Python wrapper, assume it's raw Go code
    if "package sim" in program_text:
        return program_text

    return ""


def evaluate(program_path: str) -> EvaluationResult:
    """
    Evaluate the evolved routing algorithm.

    Args:
        program_path: Path to the program file containing routing.go code

    Returns:
        EvaluationResult with metrics and artifacts
    """

    # Load program text from file
    with open(program_path, 'r') as f:
        program_text = f.read()

    # Get paths
    script_dir = Path(__file__).parent
    inference_sim_dir = script_dir / "inference-sim"
    routing_go_path = inference_sim_dir / "sim" / "routing.go"
    policy_config_path = script_dir / "routing_policy.yaml"

    # Step 1: Extract Go code from Python wrapper
    print(f"Program text preview: {program_text[:100]}...")
    go_code = extract_go_code(program_text)
    if not go_code:
        print("✗ Failed to extract Go code from program")
        print(f"Program text length: {len(program_text)}")
        print(f"Contains GO_ROUTING_CODE: {'GO_ROUTING_CODE' in program_text}")
        return EvaluationResult(
            metrics={
                "combined_score": -100000.0,
                "avg_e2e_ms": float('inf'),
                "error": "Failed to extract Go code"
            },
            artifacts={
                "error_type": "ExtractionError",
                "error_message": "Could not find GO_ROUTING_CODE variable or valid Go code",
                "suggestion": "Ensure program contains GO_ROUTING_CODE = \"\"\"...\"\"\" or starts with 'package sim'"
            }
        )

    print(f"✓ Extracted Go code: {len(go_code)} chars, first line: {go_code.split(chr(10))[0]}")

    # Step 2: Write evolved routing.go
    try:
        with open(routing_go_path, 'w') as f:
            f.write(go_code)
        print(f"✓ Wrote evolved routing.go to {routing_go_path}")
    except Exception as e:
        print(f"✗ Failed to write routing.go: {e}")
        print(traceback.format_exc())

        return EvaluationResult(
            metrics={
                "combined_score": -100000.0,  # Very bad score for file write failure
                "avg_e2e_ms": float('inf'),
                "error": f"Failed to write file: {e}"
            },
            artifacts={
                "error_type": "FileWriteError",
                "error_message": str(e),
                "full_traceback": traceback.format_exc()
            }
        )

    # Step 3: Build BLIS
    try:
        print("Building BLIS...")
        result = subprocess.run(
            ["go", "build", "-o", "simulation_worker", "main.go"],
            cwd=inference_sim_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            print(f"✗ Build failed:")
            print(result.stderr)

            return EvaluationResult(
                metrics={
                    "combined_score": -100000.0,  # Very bad score for build failure
                    "avg_e2e_ms": float('inf'),
                    "error": "Build failed"
                },
                artifacts={
                    "error_type": "BuildError",
                    "error_message": "Go build failed - likely syntax error in evolved code",
                    "build_stderr": result.stderr,
                    "suggestion": "Check for Go syntax errors in the evolved EVOLVE-BLOCK section"
                }
            )

        print("✓ Build successful")
    except subprocess.TimeoutExpired:
        print(f"✗ Build timed out")

        return EvaluationResult(
            metrics={
                "combined_score": -100000.0,
                "avg_e2e_ms": float('inf'),
                "error": "Build timeout"
            },
            artifacts={
                "error_type": "BuildTimeout",
                "error_message": "Go build exceeded 60 second timeout",
                "suggestion": "Build should be fast - this indicates a serious problem"
            }
        )
    except Exception as e:
        print(f"✗ Build error: {e}")
        print(traceback.format_exc())

        return EvaluationResult(
            metrics={
                "combined_score": -100000.0,
                "avg_e2e_ms": float('inf'),
                "error": f"Build error: {e}"
            },
            artifacts={
                "error_type": type(e).__name__,
                "error_message": str(e),
                "full_traceback": traceback.format_exc()
            }
        )

    # Step 4: Run simulations on 3 realistic servegen workloads
    workloads = [
        ("light", "workload_light.yaml"),
        ("heavy", "workload_heavy.yaml"),
        ("mixed", "workload_mixed.yaml")
    ]

    latencies = []
    workload_results = {}
    failed_workloads = []

    for workload_name, workload_file in workloads:
        try:
            print(f"Running {workload_name} workload...")

            # Workload file path (relative to script directory)
            workload_path = script_dir / workload_file

            cmd = [
                "./simulation_worker", "run",
                "--model", "Qwen/Qwen2.5-7B-Instruct",
                "--hardware", "H100",
                "--tp", "1",
                "--num-instances", "4",
                "--policy-config", str(policy_config_path),
                "--workload-spec", str(workload_path),
                "--log", "info",
                # Blackbox mode with custom coefficients for Qwen/Qwen2.5-7B-Instruct
                "--alpha-coeffs", "4680.303204056608,0.0,0.0",
                "--beta-coeffs", "7051.796874715078,19.538416565504026,25.431830886933543"
            ]

            result = subprocess.run(
                cmd,
                cwd=inference_sim_dir,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                print(f"✗ {workload_name} workload failed:")
                print(result.stderr)
                failed_workloads.append(workload_name)
                workload_results[workload_name] = {
                    "e2e_ms": None,
                    "error": "Simulation failed",
                    "stderr": result.stderr[:500]
                }
                continue

            # Parse JSON output from stderr (logrus outputs to stderr with --log flag)
            # BLIS outputs multiple JSON blocks - one per instance + one cluster-wide aggregate
            # We want the CLUSTER aggregate (instance_id == "cluster")
            try:
                # Find all JSON blocks in the output (could be in stdout or stderr)
                output_text = result.stderr if result.stderr else result.stdout

                # Extract JSON objects from the log output
                json_blocks = []
                for line in output_text.split('\n'):
                    # Look for lines with msg="..." containing JSON
                    # Format: level=info msg="{\n  \"instance_id\": ..."
                    if 'msg="' in line and '{' in line:
                        # Extract JSON from msg="..." field
                        msg_start = line.find('msg="')
                        if msg_start >= 0:
                            json_start = line.find('{', msg_start)
                            if json_start >= 0:
                                # Find the closing "
                                json_end = line.rfind('"')
                                if json_end > json_start:
                                    json_str = line[json_start:json_end]
                                    # Unescape newlines and quotes
                                    json_str = json_str.replace('\\n', '\n').replace('\\"', '"')
                                    try:
                                        json_obj = json.loads(json_str)
                                        json_blocks.append(json_obj)
                                    except json.JSONDecodeError:
                                        continue

                # Find the cluster-wide metrics (instance_id == "cluster")
                cluster_metrics = None
                for block in json_blocks:
                    if block.get("instance_id") == "cluster":
                        cluster_metrics = block
                        break

                if cluster_metrics and "e2e_mean_ms" in cluster_metrics:
                    e2e_ms = float(cluster_metrics["e2e_mean_ms"])
                    latencies.append(e2e_ms)
                    workload_results[workload_name] = {
                        "e2e_ms": e2e_ms,
                        "ttft_mean_ms": cluster_metrics.get("ttft_mean_ms"),
                        "itl_mean_ms": cluster_metrics.get("itl_mean_ms"),
                        "tokens_per_sec": cluster_metrics.get("tokens_per_sec")
                    }
                    print(f"✓ {workload_name}: e2e_mean_ms={e2e_ms:.2f}ms (cluster-wide)")
                else:
                    print(f"✗ Could not find cluster metrics in {workload_name} output")
                    print(f"Found {len(json_blocks)} JSON blocks")
                    failed_workloads.append(workload_name)
                    workload_results[workload_name] = {
                        "e2e_ms": None,
                        "error": "Failed to find cluster metrics",
                        "json_blocks_found": len(json_blocks)
                    }
            except Exception as parse_error:
                print(f"✗ Error parsing {workload_name} output: {parse_error}")
                print("Output sample:", output_text[:500])
                failed_workloads.append(workload_name)
                workload_results[workload_name] = {
                    "e2e_ms": None,
                    "error": f"Parse error: {str(parse_error)}",
                    "output_sample": output_text[:500]
                }

        except subprocess.TimeoutExpired:
            print(f"✗ {workload_name} workload timed out")
            failed_workloads.append(workload_name)
            workload_results[workload_name] = {
                "e2e_ms": None,
                "error": "Timeout (120s)"
            }
        except Exception as e:
            print(f"✗ {workload_name} workload error: {e}")
            failed_workloads.append(workload_name)
            workload_results[workload_name] = {
                "e2e_ms": None,
                "error": str(e)
            }

    # Step 5: Compute score
    if len(latencies) == 0:
        # All workloads failed
        print("✗ All workloads failed")

        return EvaluationResult(
            metrics={
                "combined_score": -100000.0,  # Very bad score for all failures
                "avg_e2e_ms": float('inf'),
                "num_successful": 0,
                "num_failed": len(workloads),
                "error": "All workloads failed"
            },
            artifacts={
                "error_type": "AllWorkloadsFailed",
                "error_message": f"All {len(workloads)} workloads failed to run or parse",
                "failed_workloads": failed_workloads,
                "workload_results": workload_results,
                "suggestion": "Check BLIS simulation errors. May be routing logic causing crashes or timeouts."
            }
        )

    # Calculate average latency from successful runs
    avg_latency = sum(latencies) / len(latencies)

    # Score = negative latency (so lower latency = higher score)
    # E.g., 5000ms → score -5000, 4500ms → score -4500 (better!)
    score = -avg_latency

    # Calculate success rate
    success_rate = len(latencies) / len(workloads)

    print(f"\n{'='*60}")
    print(f"EVALUATION COMPLETE")
    print(f"{'='*60}")
    for name, result in workload_results.items():
        if result.get("e2e_ms") is not None:
            print(f"{name.capitalize():12s}: {result['e2e_ms']:.2f}ms ✓")
        else:
            print(f"{name.capitalize():12s}: FAILED ✗")
    print(f"{'─'*60}")
    print(f"Average latency: {avg_latency:.2f}ms")
    print(f"Success rate:    {success_rate:.0%} ({len(latencies)}/{len(workloads)})")
    print(f"Score:           {score:.2f}")
    print(f"{'='*60}\n")

    # Prepare artifacts
    artifacts = {
        "workload_results": workload_results,
        "successful_workloads": len(latencies),
        "failed_workloads": len(failed_workloads),
        "success_rate": f"{success_rate:.0%}"
    }

    if failed_workloads:
        artifacts["warning"] = f"Some workloads failed: {', '.join(failed_workloads)}"
        artifacts["suggestion"] = "Check if evolved routing logic causes crashes or extreme slowdowns"

    # Return metrics
    metrics = {
        "combined_score": score,
        "avg_e2e_ms": avg_latency,
        "light_e2e_ms": workload_results.get("light", {}).get("e2e_ms"),
        "heavy_e2e_ms": workload_results.get("heavy", {}).get("e2e_ms"),
        "mixed_e2e_ms": workload_results.get("mixed", {}).get("e2e_ms"),
        "success_rate": success_rate,
        "num_successful": len(latencies),
        "num_failed": len(failed_workloads)
    }

    return EvaluationResult(
        metrics=metrics,
        artifacts=artifacts
    )


if __name__ == "__main__":
    # Test the evaluator with the initial program
    print("Testing evaluator with initial program...")

    script_dir = Path(__file__).parent
    initial_program_path = script_dir / "initial_program.py"

    # Evaluate it by passing the file path
    result = evaluate(str(initial_program_path))

    print("\nTest result:")
    score = result.metrics.get('combined_score')
    avg_e2e = result.metrics.get('avg_e2e_ms')
    success_rate = result.metrics.get('success_rate')

    print(f"  Score: {score:.2f}" if score is not None else "  Score: N/A")
    print(f"  Avg E2E: {avg_e2e:.2f}ms" if avg_e2e is not None and avg_e2e != float('inf') else "  Avg E2E: N/A")
    print(f"  Success rate: {success_rate:.0%}" if success_rate is not None else "  Success rate: N/A")
