import importlib.util
from openevolve.evaluation_result import EvaluationResult

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
        requests.append({
            "id": i,
            "content": content
        })

    return requests


def extract_prefix(request, k=3):
    """Use first k words as prefix"""
    return " ".join(request["content"].split()[:k])


class PrefixAwareSimulator:
    def __init__(self, max_prefixes=3, capacity=10):
        self.seen_prefixes = []
        self.max_prefixes = max_prefixes
        self.capacity = capacity

    def run(self, requests):
        reward = 0.0
        overload = max(0, len(requests) - self.capacity)

        for req in requests:
            prefix = extract_prefix(req)
            if prefix in self.seen_prefixes:
                reward += 1.0
            else:
                reward += 0.1
                if len(self.seen_prefixes) < self.max_prefixes:
                    self.seen_prefixes.append(prefix)

        # congestion penalty
        reward -= overload * 0.5
        return reward




def evaluate(program_path):
    try:
        # load evolved router
        spec = importlib.util.spec_from_file_location("program", program_path)
        program = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(program)

        router = program.run_search()

        # generate requests
        requests = generate_requests()

        # routing decision
        policy = router(requests, num_sims=2)

        # split requests
        buckets = [[], []]
        for req, sim_id in zip(requests, policy):
            buckets[int(sim_id)].append(req)

        # run simulators
        sim0 = PrefixAwareSimulator()
        sim1 = PrefixAwareSimulator()

        reward0 = sim0.run(buckets[0])
        reward1 = sim1.run(buckets[1])

        total_reward = reward0 + reward1
        avg_reward = total_reward / len(requests)

        return EvaluationResult(
            metrics={"score": avg_reward},
            artifacts={
                "sim0_requests": len(buckets[0]),
                "sim1_requests": len(buckets[1]),
                "reward0": reward0,
                "reward1": reward1
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