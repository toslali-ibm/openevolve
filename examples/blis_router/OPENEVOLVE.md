# OpenEvolve Workflow: BLIS Router Optimization

This guide explains how OpenEvolve works using the BLIS (Blackbox Inference Simulator) router optimization as a concrete example.

---

## Table of Contents

1. [What is OpenEvolve?](#what-is-openevolve)
2. [The BLIS Router Use Case](#the-blis-router-use-case)
3. [The Initial Program](#the-initial-program)
4. [Configuration File Explained](#configuration-file-explained)
5. [The Evolutionary Loop](#the-evolutionary-loop)
6. [The Evaluator](#the-evaluator)
7. [Running the Evolution](#running-the-evolution)
8. [Understanding the Results](#understanding-the-results)

---

## What is OpenEvolve?

**OpenEvolve** is an evolutionary coding system that uses Large Language Models (LLMs) to automatically optimize code through iterative evolution. It's inspired by Google DeepMind's AlphaEvolve.

### Core Concept

1. **Start** with a working program (the "initial program")
2. **Evolve** it by having an LLM generate mutations
3. **Evaluate** each mutation to measure its performance
4. **Select** the best mutations to guide future evolution
5. **Repeat** until you find optimal solutions

### Key Features

- **MAP-Elites Algorithm**: Maintains diverse population across feature dimensions
- **Island-Based Evolution**: Multiple populations evolve independently with periodic migration
- **LLM-Powered Mutations**: Uses models like GPT-4, Claude, or Gemini to generate code changes
- **Cross-Language Support**: Can evolve Python, Go, Rust, R, and other languages
- **Checkpointing**: Save and resume evolution at any point

---

## The BLIS Router Use Case

### Problem Statement

BLIS is a multi-instance LLM inference cluster simulator. Requests arrive and must be routed to one of several instances (replicas). The router uses a weighted scoring formula:

```go
score = cacheScore * cacheWeight + loadScore * loadWeight
```

**Goal**: Evolve adaptive routing logic that minimizes end-to-end latency across diverse workloads.

**Challenge**: Static weights (cache=0.6, load=0.4) don't adapt to changing conditions. We want the LLM to discover better adaptive strategies.

### Why This is Hard

1. **Multiple conflicting objectives**: Cache affinity vs load balancing
2. **Dynamic system state**: Cache utilization and load vary over time
3. **Diverse workloads**: Light, heavy, and mixed traffic patterns
4. **Complex interactions**: Routing decisions affect future system state

### What We're Optimizing

The code between `EVOLVE-BLOCK-START` and `EVOLVE-BLOCK-END` markers in the `WeightedScoring.Route()` function:

```go
// EVOLVE-BLOCK-START
// Find max FreeKVBlocks for normalization
maxFreeKV := int64(0)
for _, snap := range snapshots {
    if snap.FreeKVBlocks > maxFreeKV {
        maxFreeKV = snap.FreeKVBlocks
    }
}

// Compute scores
for i, snap := range snapshots {
    cacheScore := 0.0
    if maxFreeKV > 0 {
        cacheScore = float64(snap.FreeKVBlocks) / float64(maxFreeKV)
    }

    effectiveLoad := snap.QueueDepth + snap.BatchSize + snap.PendingRequests
    loadScore := 1.0 / (1.0 + float64(effectiveLoad))

    score := cacheScore*ws.cacheWeight + loadScore*ws.loadWeight
    scores[snap.ID] = score

    if score > bestScore {
        bestScore = score
        bestIdx = i
    }
}
// EVOLVE-BLOCK-END
```

---

## The Initial Program

**Location**: `examples/blis_router/initial_program.py`

### Structure

The initial program is a Python file containing a Go program as a string:

```python
GO_ROUTING_CODE = """package sim

import "fmt"

// ... full routing.go file with EVOLVE-BLOCK markers ...
"""
```

### What It Contains

1. **Full routing.go file** (~13KB): Complete, working Go code
2. **EVOLVE-BLOCK markers**: Delimit the section that can be modified
3. **Context**: All supporting code (types, other functions) for compilation
4. **Baseline implementation**: Static weight routing as starting point

### Available State Variables

The evolved code has access to:

**Per-Instance Snapshot** (`snap`):
- `snap.ID` (string): Instance identifier
- `snap.QueueDepth` (int): Requests waiting in queue
- `snap.BatchSize` (int): Requests currently processing
- `snap.PendingRequests` (int): Routed but not yet queued
- `snap.FreeKVBlocks` (int64): Available KV cache blocks
- `snap.KVUtilization` (float64): KV cache usage [0.0-1.0]
- `snap.CacheHitRate` (float64): Cache hit rate [0.0-1.0]

**Computed Variables**:
- `maxFreeKV` (int64): Maximum FreeKVBlocks across all instances
- `effectiveLoad` (int): QueueDepth + BatchSize + PendingRequests

**Global State**:
- `state.Clock` (int64): Current simulation time (microseconds)
- `state.Snapshots` ([]RoutingSnapshot): All instance snapshots

**Current Weights**:
- `ws.cacheWeight` (float64): Weight for cache affinity (default 0.6)
- `ws.loadWeight` (float64): Weight for load balancing (default 0.4)

### Constraints

**Must NOT change**:
- Code outside EVOLVE-BLOCK markers
- Function signatures or return types
- Variable declarations outside the block
- The overall algorithm structure

**Can optimize**:
- Weight calculation logic
- Conditional logic based on state
- Score computation formulas
- Variable declarations within the block
- Mathematical operations

---

## Configuration File Explained

**Location**: `examples/blis_router/config.yaml`

### Execution Settings

```yaml
max_iterations: 50          # Total evolution iterations to run
checkpoint_interval: 5      # Save progress every N iterations
log_level: "INFO"          # Logging verbosity
```

**50 iterations** = ~1-2 hours of evolution depending on simulation time.

### LLM Configuration

```yaml
llm:
  primary_model: Azure/gpt-4o              # Main model for mutations
  primary_model_weight: 0.6                # Weight in ensemble (60%)

  secondary_model: GCP/gemini-2.5-flash   # Optional second model
  secondary_model_weight: 0.4              # Weight in ensemble (40%)

  api_base: https://...                    # Optional custom endpoint

  temperature: 1.0                         # Randomness [0.0-2.0]
  max_tokens: 16000                        # Max response length
  timeout: 120                             # API timeout (seconds)
```

**Ensemble voting**: Multiple models vote on mutations, weighted average determines final choice. Increases robustness.

**Temperature**: Controls creativity
- **Low (0.3-0.5)**: Conservative, similar to past solutions
- **Medium (0.7-0.8)**: Balanced creativity
- **High (0.9-1.2)**: Very creative, diverse mutations

### Prompt Configuration

```yaml
prompt:
  system_message: |
    You are an expert Go programmer...
    # Detailed instructions for the LLM
    # Available state, optimization opportunities, constraints

  num_top_programs: 3       # Show 3 best programs as examples
  num_diverse_programs: 2   # Show 2 diverse programs for variety
```

**System message**: The primary way to guide the LLM's optimization approach. Contains:
- Goal and constraints
- Available state variables
- Optimization strategies to try
- Success criteria
- Code requirements

### Database Configuration (MAP-Elites)

```yaml
database:
  population_size: 50            # Total programs across all islands
  archive_size: 15              # Elite archive size (best programs)
  num_islands: 3                # Number of independent populations

  elite_selection_ratio: 0.3    # Top 30% are "elite"
  exploitation_ratio: 0.65      # 65% samples from best programs
  exploration_ratio: 0.35       # 35% samples from diverse programs
```

**MAP-Elites**: Maintains diversity by mapping programs to feature grid cells. Each cell stores the best program for that feature combination.

**Islands**: Multiple populations evolve independently, preventing premature convergence. They periodically exchange programs (migration).

**Elite vs Diverse**:
- **Elite selection**: Sample from top performers (exploitation)
- **Diverse selection**: Sample from underexplored regions (exploration)

### Evaluator Configuration

```yaml
evaluator:
  timeout: 30                    # Max time per evaluation (seconds)
  parallel_evaluations: 1        # Number of parallel evaluations
  cascade_evaluation: false      # Disable multi-stage eval
```

**Timeout**: Safety limit. If evaluation takes longer, it's terminated and assigned worst score.

**Parallel evaluations**: BLIS requires sequential evaluation (1) because Go build writes to the same file. Python examples can use higher values.

### Evolution Strategy

```yaml
diff_based_evolution: true      # Show LLM only the changes (diffs)
allow_full_rewrites: false      # Only allow EVOLVE-BLOCK changes
max_code_length: 20000          # Safety limit on code size
```

**Diff-based**: More efficient prompts by showing only what changed, not entire programs.

**Block enforcement**: Prevents LLM from breaking code structure by restricting changes to EVOLVE-BLOCK.

---

## The Evolutionary Loop

### High-Level Flow

```
┌─────────────────────────────────────────────────┐
│  1. INITIALIZATION                              │
│  - Load initial program                         │
│  - Initialize database (MAP-Elites)            │
│  - Set up islands                              │
└─────────────────────────────────────────────────┘
                    ↓
        ┌───────────────────────┐
        │  FOR EACH ITERATION   │
        └───────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  2. SAMPLING                                    │
│  - Select island to sample from                 │
│  - Sample "parent" programs from database       │
│    • 65% from best performers (exploitation)   │
│    • 35% from diverse cells (exploration)      │
│  - Select examples to show LLM                  │
│    • 3 top programs for inspiration            │
│    • 2 diverse programs for variety            │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  3. MUTATION (LLM Generation)                   │
│  - Build prompt with:                           │
│    • System message (goals, constraints)       │
│    • Parent programs (for inspiration)         │
│    • Previous mutations (if diff-based)        │
│  - Send to LLM ensemble                         │
│  - LLM generates mutated code                   │
│  - Extract code from response                   │
│  - Validate syntax                             │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  4. EVALUATION                                  │
│  - Write mutated code to file                   │
│  - Build with Go compiler                       │
│  - Run on 3 workloads:                         │
│    • Light (low rate)                          │
│    • Heavy (high rate)                         │
│    • Mixed (variable rate)                     │
│  - Compute score: -avg_latency                 │
│  - Extract features for MAP-Elites             │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  5. DATABASE UPDATE                             │
│  - Compute feature coordinates                  │
│  - Find MAP-Elites cell                        │
│  - If better than current cell occupant:       │
│    • Replace cell with new program             │
│    • Update elite archive if top performer    │
│  - If not better:                              │
│    • Discard mutation                          │
│  - Log results and artifacts                   │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  6. MIGRATION (Periodic)                        │
│  - Every N generations:                         │
│    • Exchange programs between islands         │
│    • Maintain island diversity                 │
│    • Prevent premature convergence             │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  7. CHECKPOINT (Every 5 iterations)             │
│  - Save full database state                     │
│  - Save best program                            │
│  - Save evolution metrics                       │
│  - Enable resume from any iteration            │
└─────────────────────────────────────────────────┘
                    ↓
        ┌───────────────────────┐
        │  REPEAT OR TERMINATE  │
        └───────────────────────┘
```

### Detailed Iteration Breakdown

#### Step 1: Initialization (Once at Start)

```python
# Load initial program
initial_code = load_initial_program("initial_program.py")

# Create database with MAP-Elites
database = ProgramDatabase(
    population_size=50,
    num_islands=3,
    feature_dimensions=["avg_latency", "success_rate"]
)

# Add initial program to database
initial_score = evaluate(initial_code)
database.add_program(initial_code, initial_score)
```

#### Step 2: Sampling (Each Iteration)

```python
# Select island (round-robin or random)
island_id = iteration % num_islands

# Sample parent programs
parents = database.sample_programs(
    island_id=island_id,
    n_exploit=int(num_samples * 0.65),  # 65% best
    n_explore=int(num_samples * 0.35),  # 35% diverse
)

# Select examples to show LLM
examples = {
    "top": database.get_top_programs(n=3),
    "diverse": database.get_diverse_programs(n=2)
}
```

**Why sample this way?**
- **Exploitation**: Build on proven successes
- **Exploration**: Try underexplored strategies
- **Balance**: Prevents getting stuck in local optima

#### Step 3: Mutation (LLM Generation)

```python
# Build prompt
prompt = build_prompt(
    system_message=config.system_message,
    parent_programs=parents,
    example_programs=examples,
    diff_based=config.diff_based_evolution
)

# Generate mutation via LLM ensemble
responses = await llm_ensemble.generate(
    prompt,
    temperature=config.temperature,
    max_tokens=config.max_tokens
)

# Extract code from response
mutated_code = extract_code_from_response(responses)

# Validate syntax (quick check before eval)
if not validate_syntax(mutated_code):
    return None  # Skip invalid mutation
```

**LLM sees**:
- The goal and constraints (system message)
- 3-5 example programs with their scores
- The parent program to mutate
- Previous successful mutations (if diff-based)

**LLM generates**:
- Modified code within EVOLVE-BLOCK
- Reasoning about why changes should improve performance
- The complete mutated code

#### Step 4: Evaluation

```python
# Evaluate mutated program
score, metrics = evaluate_program(
    mutated_code,
    evaluator=evaluator,
    timeout=config.timeout
)

# For BLIS router:
# 1. Write mutated routing.go to file
# 2. Run: go build -o simulation_worker main.go
# 3. Run 3 workloads:
#    - Light: ./simulation_worker run --workload-spec workload_light.yaml
#    - Heavy: ./simulation_worker run --workload-spec workload_heavy.yaml
#    - Mixed: ./simulation_worker run --workload-spec workload_mixed.yaml
# 4. Parse JSON metrics from each run
# 5. Compute: score = -average(light_e2e, heavy_e2e, mixed_e2e)

# Extract features for MAP-Elites
features = extract_features(metrics)
# e.g., features = {"avg_latency": 1780.28, "success_rate": 1.0}
```

**Score interpretation**:
- **Higher score = Better** (less negative = lower latency)
- Baseline: ~-2143 ms (static weights)
- Target: <-2000 ms (10% improvement)

#### Step 5: Database Update

```python
# Compute feature coordinates for MAP-Elites grid
cell_coords = compute_cell_coordinates(features)

# Check if this cell is empty or has worse program
current_occupant = database.get_cell(cell_coords)

if current_occupant is None or score > current_occupant.score:
    # This mutation is better! Store it.
    database.add_program(
        code=mutated_code,
        score=score,
        features=features,
        cell_coords=cell_coords,
        island_id=island_id
    )

    # Update elite archive if this is a top performer
    if score > database.get_kth_best_score(archive_size):
        database.add_to_elite(mutated_code, score)

    logging.info(f"✓ Iteration {i}: NEW BEST in cell {cell_coords}: {score:.2f}")
else:
    # Mutation is worse than current cell occupant, discard
    logging.info(f"✗ Iteration {i}: Rejected (worse than cell occupant)")
```

**Why MAP-Elites?**
- Maintains diversity across feature dimensions
- Prevents convergence to single solution
- Discovers multiple good strategies
- Each cell represents a different trade-off

#### Step 6: Migration (Periodic)

```python
# Every N generations, exchange programs between islands
if generation % migration_interval == 0:
    for island_id in range(num_islands):
        # Select programs to migrate
        migrants = database.sample_programs(
            island_id=island_id,
            n=migration_size
        )

        # Send to neighboring islands
        target_island = (island_id + 1) % num_islands
        database.migrate_programs(migrants, target_island)
```

**Why migration?**
- Islands explore different strategies independently
- Periodic exchange shares discoveries
- Prevents global convergence
- Increases robustness

#### Step 7: Checkpointing

```python
# Save every 5 iterations
if iteration % checkpoint_interval == 0:
    save_checkpoint(
        iteration=iteration,
        database=database,
        best_program=database.get_best_program(),
        config=config,
        metrics=evolution_metrics
    )
```

**Checkpoint contains**:
- Complete database state (all programs, scores, features)
- Best program found so far
- Evolution metrics (score history, diversity)
- Configuration (for reproducibility)

**Resume from checkpoint**:
```bash
python openevolve-run.py initial_program.py evaluator.py \
    --config config.yaml \
    --checkpoint path/to/checkpoint \
    --iterations 50  # Continue for 50 more iterations
```

---

## The Evaluator

**Location**: `examples/blis_router/evaluator.py`

### Purpose

The evaluator is responsible for:
1. **Extracting** Go code from the Python wrapper
2. **Building** the BLIS binary with the mutated code
3. **Running** simulations on multiple workloads
4. **Parsing** metrics from simulation output
5. **Computing** the final score

### Implementation

```python
def evaluate(program_path: str) -> EvaluationResult:
    """
    Evaluate routing algorithm on 3 workloads, return score.

    Score = -avg_latency (lower latency = higher score)
    """
    # 1. Extract Go code from Python wrapper
    go_code = extract_go_code(read_file(program_path))

    # 2. Write to BLIS source
    write_file("inference-sim/sim/routing.go", go_code)

    # 3. Build BLIS
    result = subprocess.run(
        ["go", "build", "-o", "simulation_worker", "main.go"],
        cwd="inference-sim",
        timeout=60
    )
    if result.returncode != 0:
        return EvaluationResult(
            metrics={"combined_score": -100000.0, "error": "Build failed"}
        )

    # 4. Run on 3 workloads
    workloads = ["light", "heavy", "mixed"]
    latencies = []

    for workload in workloads:
        result = subprocess.run([
            "./simulation_worker", "run",
            "--model", "Qwen/Qwen2.5-7B-Instruct",
            "--hardware", "H100",
            "--tp", "1",
            "--num-instances", "4",
            "--workload-spec", f"workload_{workload}.yaml",
            "--log", "info",
            "--alpha-coeffs", "4680.303204056608,0.0,0.0",
            "--beta-coeffs", "7051.796874715078,19.538416565504026,25.431830886933543"
        ], cwd="inference-sim", timeout=120, capture_output=True)

        # 5. Parse cluster-wide metrics from JSON
        metrics = parse_json_metrics(result.stderr)
        cluster_metrics = find_cluster_metrics(metrics)
        latencies.append(cluster_metrics["e2e_mean_ms"])

    # 6. Compute score
    avg_latency = mean(latencies)
    score = -avg_latency  # Negative because we minimize latency

    return EvaluationResult(
        metrics={
            "combined_score": score,
            "avg_e2e_ms": avg_latency,
            "light_e2e_ms": latencies[0],
            "heavy_e2e_ms": latencies[1],
            "mixed_e2e_ms": latencies[2],
            "success_rate": 1.0
        }
    )
```

### Workload Specifications

Each workload YAML file specifies:

```yaml
# workload_light.yaml
clients:
  - name: light_client
    num_requests: 1000
    arrival_process: poisson
    rate: 10  # 10 req/s
    prompt_tokens:
      distribution: normal
      mean: 512
      stddev: 128
    output_tokens:
      distribution: normal
      mean: 256
      stddev: 64
```

**Three workload patterns**:
- **Light**: 10 req/s, tests low-load behavior
- **Heavy**: 50 req/s, tests high-load behavior
- **Mixed**: Variable rate, tests adaptability

### Metric Parsing

BLIS outputs structured JSON with logrus:

```
time="..." level=info msg="{
  \"instance_id\": \"cluster\",
  \"e2e_mean_ms\": 1780.28,
  \"ttft_mean_ms\": 20.5,
  ...
}"
```

The evaluator:
1. Searches for lines containing `msg="`
2. Extracts JSON from within the msg field
3. Unescapes newlines and quotes
4. Parses JSON to extract metrics
5. Filters for `instance_id == "cluster"` (cluster-wide aggregate)

### Error Handling

```python
# Build errors
if build fails:
    return score = -100000.0  # Worst possible score

# Simulation errors
if simulation fails or times out:
    skip that workload
    if all workloads fail:
        return score = -100000.0

# Parse errors
if can't parse metrics:
    treat as workload failure
```

### Evaluation Time

**Total time per evaluation**: ~10-30 seconds
- Go build: 1-3 seconds
- Light workload: 2-5 seconds
- Heavy workload: 3-8 seconds
- Mixed workload: 2-5 seconds
- Overhead: 1-2 seconds

**50 iterations × 30 sec/eval** = ~25 minutes minimum
- Add time for LLM generation: +5-15 sec/iteration
- Add time for failed mutations and retries
- **Typical runtime**: 1-2 hours for 50 iterations

---

## Running the Evolution

### Prerequisites

1. **Install OpenEvolve**:
```bash
cd openevolve
pip install -e ".[dev]"
```

2. **Set up inference-sim**:
```bash
cd examples/blis_router/inference-sim
go build -o simulation_worker main.go
```

3. **Configure LLM API keys**:
```bash
export OPENAI_API_KEY="..."      # For GPT models
export ANTHROPIC_API_KEY="..."   # For Claude models
export GEMINI_API_KEY="..."      # For Gemini models
```

### Basic Run

```bash
cd examples/blis_router

python ../../openevolve-run.py \
    initial_program.py \
    evaluator.py \
    --config config.yaml \
    --iterations 50
```

### Resume from Checkpoint

```bash
python ../../openevolve-run.py \
    initial_program.py \
    evaluator.py \
    --config config.yaml \
    --checkpoint ./openevolve_output/checkpoints/checkpoint_25 \
    --iterations 50  # Run 50 MORE iterations
```

### Monitor Progress

**During evolution**:
```
INFO - Iteration 1/50
INFO - ✓ Generated mutation (2187 chars)
INFO - Evaluating program...
INFO - ✓ Light: 1748.17ms
INFO - ✓ Heavy: 2495.16ms
INFO - ✓ Mixed: 2187.51ms
INFO - Score: -2143.61 (avg latency: 2143.61ms)
INFO - NEW BEST! Improved from -2200.00 to -2143.61
INFO - Saved checkpoint to ./openevolve_output/checkpoints/checkpoint_1
```

**Check best program**:
```bash
cat openevolve_output/best_program.py
```

**Visualize evolution tree**:
```bash
python scripts/visualizer.py --path openevolve_output/checkpoints/checkpoint_50/
```

---

## Understanding the Results

### Output Directory Structure

```
examples/blis_router/openevolve_output/
├── checkpoints/
│   ├── checkpoint_5/
│   │   ├── database.pkl          # Full database state
│   │   ├── best_program.py       # Best program at iteration 5
│   │   ├── metadata.json         # Iteration info, scores
│   │   └── tree_visualization.html
│   ├── checkpoint_10/
│   └── checkpoint_50/
├── best_program.py                # Overall best program
├── evolution_log.txt              # Detailed logs
└── metrics.json                   # Score history, statistics
```

### Metrics to Watch

**Primary metric: `combined_score`**
- Baseline: ~-2143 (static weights)
- Target: <-2000 (10% improvement)
- Best achieved: Check `best_program.py` header

**Secondary metrics**:
- `light_e2e_ms`: Performance on light workload
- `heavy_e2e_ms`: Performance on heavy workload
- `mixed_e2e_ms`: Performance on mixed workload
- `success_rate`: Fraction of workloads that completed

**Evolution metrics**:
- **Diversity**: Number of unique cells occupied in MAP-Elites grid
- **Elite size**: Number of programs in top-K archive
- **Improvement rate**: Score increase per iteration
- **Convergence**: Plateau in score improvements

### Interpreting the Best Program

The evolved code will contain adaptive logic, e.g.:

```go
// EVOLVE-BLOCK-START

// Evolved strategy: Cache-adaptive weighting
maxFreeKV := int64(0)
for _, snap := range snapshots {
    if snap.FreeKVBlocks > maxFreeKV {
        maxFreeKV = snap.FreeKVBlocks
    }
}

// Compute adaptive weights based on cache utilization
avgUtilization := 0.0
for _, snap := range snapshots {
    avgUtilization += snap.KVUtilization
}
avgUtilization /= float64(len(snapshots))

// Key insight discovered by evolution:
// - When cache has room (low utilization), prioritize cache affinity
// - When cache is full (high utilization), prioritize load balancing
var cacheWeight, loadWeight float64
if avgUtilization < 0.4 {
    // Plenty of cache space - maximize cache hits
    cacheWeight = 0.8
    loadWeight = 0.2
} else if avgUtilization > 0.7 {
    // Cache constrained - balance load aggressively
    cacheWeight = 0.3
    loadWeight = 0.7
} else {
    // Middle ground - use balanced weights
    cacheWeight = 0.6
    loadWeight = 0.4
}

// Compute scores with adaptive weights
scores := make(map[string]float64, len(snapshots))
bestScore := -1.0
bestIdx := 0

for i, snap := range snapshots {
    cacheScore := 0.0
    if maxFreeKV > 0 {
        cacheScore = float64(snap.FreeKVBlocks) / float64(maxFreeKV)
    }

    effectiveLoad := snap.QueueDepth + snap.BatchSize + snap.PendingRequests
    loadScore := 1.0 / (1.0 + float64(effectiveLoad))

    score := cacheScore*cacheWeight + loadScore*loadWeight
    scores[snap.ID] = score

    if score > bestScore {
        bestScore = score
        bestIdx = i
    }
}

// EVOLVE-BLOCK-END
```

**What the LLM discovered**:
- Cache utilization is a better signal than static weights
- Threshold-based adaptation (0.4, 0.7) works well
- Cluster-wide average captures system state better than per-instance

**Why this works**:
- **Low utilization**: Cache has room → prioritize placing related requests together
- **High utilization**: Cache is full anyway → focus on balancing load
- **Dynamic adaptation**: Responds to changing workload patterns

### Performance Analysis

Compare baseline vs evolved:

| Workload | Baseline (ms) | Evolved (ms) | Improvement |
|----------|---------------|--------------|-------------|
| Light    | 1748.17       | 1620.45      | 7.3%        |
| Heavy    | 2495.16       | 2310.88      | 7.4%        |
| Mixed    | 2187.51       | 2055.12      | 6.1%        |
| **Avg**  | **2143.61**   | **1995.48**  | **6.9%**    |

**Conclusion**: Evolved adaptive strategy achieves **~7% latency reduction** across all workload types.

---

## Tips for Success

### Configuration Tuning

**For faster iteration**:
- Reduce `max_iterations` to 20-30 for quick experiments
- Use single model (remove `secondary_model`)
- Increase `temperature` to 1.2 for more creative mutations

**For better results**:
- Increase `max_iterations` to 100-200
- Use ensemble (primary + secondary models)
- Lower `temperature` to 0.7 after finding good solutions
- Increase `population_size` to 100 for more diversity

**For debugging**:
- Set `log_level: "DEBUG"` to see detailed info
- Enable `allow_full_rewrites: true` temporarily if stuck
- Reduce `timeout` to catch slow evaluations earlier

### Common Issues

**"All evaluations failing"**:
- Check that BLIS builds: `cd inference-sim && go build`
- Verify workload files exist: `ls workload_*.yaml`
- Test evaluator manually: `python evaluator.py`

**"No improvement after many iterations"**:
- LLM may need more guidance - enhance `system_message`
- Try different `temperature` values
- Check if baseline is already optimal (hard to beat)
- Increase diversity: more islands, more exploration

**"LLM generating invalid code"**:
- Strengthen constraints in `system_message`
- Show more examples of valid code
- Enable `diff_based_evolution` for better context
- Consider using Claude (better at following constraints)

---

## Summary

### The Evolution Pipeline

```
Initial Program → [Iteration 1] → Mutation 1 → Evaluation → Score 1 → Database
                ↓
                [Iteration 2] → Sample from Database → Mutation 2 → Evaluation → Score 2 → Database
                ↓
                [Iteration 3] → ...
                ↓
                [Iteration 50] → Best Program
```

### Key Takeaways

1. **Initial Program**: Working baseline with EVOLVE-BLOCK markers
2. **Config**: Controls LLM, database, evaluation, and evolution strategy
3. **Evolutionary Loop**: Sample → Mutate → Evaluate → Update → Repeat
4. **Evaluator**: Builds, runs, measures, and scores each mutation
5. **MAP-Elites**: Maintains diverse population across feature dimensions
6. **Islands**: Independent populations prevent premature convergence
7. **Checkpointing**: Save progress, resume anytime

### Why This Works

- **LLMs are creative**: Discover strategies humans might not think of
- **Evolution is systematic**: Explores solution space efficiently
- **MAP-Elites maintains diversity**: Avoids local optima
- **Islands prevent convergence**: Robust to getting stuck
- **Evaluation is automatic**: No manual tuning required

### Next Steps

- **Run your first evolution**: Start with 20 iterations
- **Analyze the results**: Check if improvement > 5%
- **Iterate on the config**: Tune LLM, prompts, and parameters
- **Try different use cases**: Adapt to your own optimization problems

---

**Happy evolving! 🧬**
