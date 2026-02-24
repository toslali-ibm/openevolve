import importlib.util
from openevolve.evaluation_result import EvaluationResult


# -----------------------------
# Request generation
# -----------------------------
def generate_requests():
    prefixes = [
        "write a python function",
        "write a python function",
        "write a python function",
        "summarize this article",
        "summarize this article",
        "summarize this article",
        "explain transformer attention",
        "explain transformer attention",
        "explain transformer attention",
        "translate to french",
        "translate to french",
        "translate to french",
    ]

    requests = []
    for i in range(20):
        prefix = prefixes[i % len(prefixes)]
        content = prefix + " with simple examples"
        requests.append({"id": i, "content": content})

    return requests


def extract_prefix(request, k=3):
    return " ".join(request["content"].split()[:k])


# -----------------------------
# Realistic prefix-aware simulator
# -----------------------------
class PrefixAwareSimulator:
    """
    Models:
    - sequential execution
    - queueing delay
    - KV-cache locality
    - cache thrashing
    """
    def __init__(self, max_cache=3):
        self.cache = []
        self.max_cache = max_cache

    def run(self, requests):
        total_latency = 0.0

        for position, req in enumerate(requests):
            prefix = extract_prefix(req)

            # base compute latency
            latency = 5.0

            # queueing delay (critical)
            latency += position * 0.5

            # cache hit benefit
            if prefix in self.cache:
                latency -= 2.5
            else:
                # cache miss + LRU eviction
                if len(self.cache) >= self.max_cache:
                    self.cache.pop(0)
                self.cache.append(prefix)

            total_latency += latency

        return total_latency


# -----------------------------
# OpenEvolve evaluator
# -----------------------------
def evaluate(program_path):
    try:
        # load evolved router
        spec = importlib.util.spec_from_file_location("program", program_path)
        program = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(program)

        router = program.run_search()

        requests = generate_requests()
        policy = router(requests, num_sims=2)

        # safety guard
        if not isinstance(policy, list) or len(policy) != len(requests):
            return EvaluationResult(
                metrics={"score": -1e9},
                artifacts={"error": "Invalid routing policy"}
            )

        # split requests
        buckets = [[], []]
        for req, sim_id in zip(requests, policy):
            buckets[int(sim_id)].append(req)

        # run simulators
        sim0 = PrefixAwareSimulator()
        sim1 = PrefixAwareSimulator()

        lat0 = sim0.run(buckets[0])
        lat1 = sim1.run(buckets[1])

        total_latency = lat0 + lat1
        avg_latency = total_latency / len(requests)

        # OpenEvolve maximizes score → minimize latency
        score = -avg_latency

        return EvaluationResult(
            metrics={"score": score},
            artifacts={
                "avg_latency": avg_latency,
                "sim0_requests": len(buckets[0]),
                "sim1_requests": len(buckets[1]),
            }
        )

    except Exception as e:
        return EvaluationResult(
            metrics={"score": -1e9},
            artifacts={"error": str(e)}
        )


def evaluate_stage1(program_path):
    return evaluate(program_path)


def evaluate_stage2(program_path):
    return evaluate(program_path)
