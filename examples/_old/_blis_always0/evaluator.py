"""
Evaluator for routing policy discovery
"""

import importlib.util
from openevolve.evaluation_result import EvaluationResult


def evaluate(program_path):
    try:
        # Load evolved program
        spec = importlib.util.spec_from_file_location("program", program_path)
        program = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(program)

        if not hasattr(program, "run_search"):
            return EvaluationResult(
                metrics={"score": 0.0},
                artifacts={"error": "Missing run_search"}
            )

        router = program.run_search()

        # Generate requests
        requests = [{"id": i} for i in range(20)]

        # Get routing decisions
        policy = router(requests, num_sims=2)

        if len(policy) != len(requests):
            return EvaluationResult(
                metrics={"score": 0.0},
                artifacts={"error": "Policy length mismatch"}
            )

        # Mock simulators
        rewards = []
        for sim_id in policy:
            if sim_id == 0:
                rewards.append(1.0)   # good simulator
            else:
                rewards.append(0.0)   # bad simulator

        avg_reward = sum(rewards) / len(rewards)

        return EvaluationResult(
            metrics={
                "score": avg_reward
            },
            artifacts={
                "sim0_count": policy.count(0),
                "sim1_count": policy.count(1)
            }
        )

    except Exception as e:
        return EvaluationResult(
            metrics={"score": 0.0},
            artifacts={"error": str(e)}
        )


def evaluate_stage1(program_path):
    """Fast filter: just run once"""
    return evaluate(program_path)


def evaluate_stage2(program_path):
    """Full evaluation"""
    return evaluate(program_path)
