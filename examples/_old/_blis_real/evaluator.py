import importlib.util
from openevolve.evaluation_result import EvaluationResult


from dataclasses import dataclass
import csv
import random
import time


@dataclass
class InferenceRequest:
    arrival_time: float   # seconds
    input_len: int
    output_len: int
    input: str
    output: str

    def to_csv_row(self):
        return [
            self.arrival_time,
            self.input_len,
            self.output_len,
            self.input,
            self.output,
        ]


def generate_requests(n=100, start_time=0.0):
    """
    here, we are going to read from promptsblisopenevolve.txt (which includes prompts separated by "\n\n")
    we will create random arrival time - say with 5 req per second
    output len will be random like random.randint(16, 256)
    """
    def read_prompts(path):
        with open(path, "r") as f:
            text = f.read()

        prompts = [
            p.strip()
            for p in text.split("\n\n")
            if p.strip()
        ]

        return prompts
    
    prompts = read_prompts("promptsblisopenevolve.txt") 
    requests = []
    current_time = start_time

    for i in range(n):
        # inter-arrival time (exponential-ish)
        current_time += random.expovariate(5)  # avg 5 req/sec
        prompt = prompts[n]

        input_len = len(prompt.split()) # will be length of whatever prompt picked 
        output_len = random.randint(16, 256)

        inp = prompt
        out = f"Output {i} with {output_len} tokens"

        req = InferenceRequest(
            arrival_time=round(current_time, 6),
            input_len=input_len,
            output_len=output_len,
            input=inp,
            output=out,
        )
        requests.append(req)

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
