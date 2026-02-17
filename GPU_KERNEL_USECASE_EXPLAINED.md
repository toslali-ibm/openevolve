# GPU Kernel Optimization Use Case - Simple Explanation

## What is this use case about?

This example uses OpenEvolve to automatically optimize a GPU kernel (a small program that runs on your graphics card). Specifically, it optimizes an **attention mechanism** for a language model called **Qwen3-0.6B** running on Apple Silicon (M-series chips).

Think of it like this: You have a program that works, but you want it to run faster. Instead of manually tweaking the code, OpenEvolve uses AI to automatically try different optimizations and keeps the ones that work better.

## The Big Picture

```
┌─────────────────────────────────────────────────────────────┐
│                    EVOLUTION CYCLE                          │
│                                                             │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────┐ │
│  │  1. Sample   │  →   │  2. LLM      │  →   │ 3. Test  │ │
│  │  Programs    │      │  Mutates     │      │  & Score │ │
│  │  from DB     │      │  Code        │      │  Program │ │
│  └──────────────┘      └──────────────┘      └──────────┘ │
│         ↑                                           ↓      │
│         │                                           │      │
│         │          ┌──────────────┐                │      │
│         └──────────│  4. Store    │←───────────────┘      │
│                    │  Best Ones   │                        │
│                    └──────────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Initial Program (The Starting Point)

**Location**: `examples/mlx_metal_kernel_opt/initial_program.py`

This file contains a working Metal kernel (GPU program) that computes attention for the Qwen3 model. The kernel has a special section marked with `EVOLVE-BLOCK-START` and `EVOLVE-BLOCK-END` that tells OpenEvolve: "this is the code you can modify."

**What it does**: Lines 68-197 in `initial_program.py`
- Takes query, key, and value matrices
- Computes attention scores (how much each word should pay attention to other words)
- Applies softmax (normalizes scores)
- Combines values based on attention weights

**Key details**:
- **Architecture**: Qwen3 uses "Grouped Query Attention" with 40 query heads and 8 key-value heads (5:1 ratio)
- **Target**: Apple M-series GPUs with unified memory
- **Goal**: Make it 5-15% faster than the baseline

### 2. Evaluator (The Judge)

**Location**: `examples/mlx_metal_kernel_opt/evaluator.py`

The evaluator is like a strict teacher that grades each evolved program. It checks three main things:

#### Step-by-Step Evaluation Process:

**Step 1: Extract the Code** (Line 132)
- Pulls out the custom attention code from the program text
- Validates that it's properly formatted

**Step 2: Safety Check** (Line 142)
- Makes sure the kernel won't crash the GPU
- Validates memory access patterns

**Step 3: Measure Baseline** (Line 149)
- Runs the standard MLX attention implementation
- Records how fast it performs
- This is what we're trying to beat!

**Step 4: Correctness Test** (Line 157)
- Runs the evolved kernel
- Compares output to the baseline
- Must match within 90% accuracy (some float precision differences are OK)

**Step 5: Performance Benchmark** (Line 171)
- Runs the kernel on 20 different test scenarios
- Measures speed (tokens/second) and memory usage
- Tests short sequences (16 tokens), long sequences (2048 tokens), etc.

**Step 6: Calculate Score** (Line 186)
- Combines correctness + performance
- Higher score = better program
- Only programs with scores above a threshold survive

### 3. Configuration (The Rules)

**Location**: `examples/mlx_metal_kernel_opt/config.yaml`

This file sets all the parameters for evolution:

#### LLM Settings (Lines 6-15)
```yaml
llm:
  primary_model: "gemini-2.5-flash-preview"      # 60% of mutations
  secondary_model: "gemini-2.5-pro-preview"       # 40% of mutations
  temperature: 0.6                                 # How creative the AI is
  max_tokens: 32000                                # Maximum code length
```

**Why two models?** Mixing a fast model (Flash) with a smarter model (Pro) balances speed and quality.

#### Evolution Strategy (Line 231-233)
```yaml
diff_based_evolution: true              # Make small changes, not complete rewrites
allow_full_rewrites: false              # Never start from scratch
max_code_length: 60000                  # Maximum program size
```

#### Database/Islands (Lines 216-223)
```yaml
database:
  population_size: 25                   # Total number of programs to keep
  num_islands: 3                        # Split into 3 separate populations
  elite_selection_ratio: 0.3            # Top 30% are "elite"
  exploitation_ratio: 0.65              # 65% of time, improve best programs
  exploration_ratio: 0.35               # 35% of time, try random changes
```

#### Prompt Engineering (Lines 18-211)
The system message tells the LLM **exactly** what optimizations to try:
- Vectorization (process multiple values at once)
- Memory access patterns (load data more efficiently)
- Algorithm improvements (reduce number of computation passes)
- Apple Silicon specialization (use hardware-specific features)

### 4. The Islands System

**What are islands?** Think of them as separate breeding grounds for programs.

```
Island 1          Island 2          Island 3
[Programs A-H]    [Programs I-P]    [Programs Q-X]
     ↓                 ↓                 ↓
   Evolve           Evolve            Evolve
     ↓                 ↓                 ↓
   Best A           Best I             Best Q
      ↘               ↓                 ↙
         Migration every N generations
                    ↓
           [New mixed population]
```

**Why islands?**
- Prevents all programs from becoming too similar
- Each island explores different optimization strategies
- Periodically, the best programs "migrate" between islands
- This maintains diversity and prevents getting stuck

**Implementation**: `openevolve/database.py`
- Each island maintains its own MAP-Elites grid (more on this below)
- Programs are mapped to cells based on their features
- Islands exchange their best programs occasionally

### 5. MAP-Elites Algorithm

**What is MAP-Elites?** A clever way to maintain diverse programs.

```
        Performance Dimension
        ↑
    [B] │ [C] [F]         ← Grid cells
    [A] │ [D] [E] [G]
        └─────────────→ Memory Usage Dimension
```

Each cell stores ONE program with specific characteristics:
- **Cell A**: Fast but uses lots of memory
- **Cell B**: Very fast but uses even more memory
- **Cell C**: Medium speed, low memory
- etc.

**How it works** (`openevolve/database.py`):
1. When a new program is evaluated, calculate its "features" (speed, memory, etc.)
2. Map it to a cell in the grid based on those features
3. If the cell is empty, store the program
4. If the cell has a program, keep whichever has a better score

**Why this is powerful**: You get a diverse collection of programs, not just "the fastest one."

### 6. The Evolution Loop

**Main Orchestrator**: `openevolve/controller.py`

The controller manages the entire evolution process:

```python
for iteration in range(max_iterations):
    # 1. Sample Programs
    selected_programs = database.sample_programs()

    # 2. Generate Mutations (using LLM)
    new_program = llm.mutate_code(selected_programs)

    # 3. Evaluate
    score = evaluator.evaluate(new_program)

    # 4. Store if good
    if score > threshold:
        database.add_program(new_program, score)

    # 5. Checkpoint periodically
    if iteration % checkpoint_interval == 0:
        save_checkpoint()
```

#### Detailed Steps:

**Step 1: Sampling** (`openevolve/database.py`)
- Pick programs from the database to use as "inspiration"
- Uses two selection strategies:
  - **Exploitation** (65%): Pick from the best programs
  - **Exploration** (35%): Pick random programs for diversity
- "Double selection": Programs shown to LLM differ from those used for mutations

**Step 2: LLM Mutation** (`openevolve/llm/`)
- Build a prompt with:
  - System instructions (what optimizations to try)
  - 3 top programs as examples
  - 2 diverse programs for inspiration
- Send to LLM (Gemini Flash or Pro)
- LLM suggests code changes
- Apply changes to create new program

**Step 3: Evaluation** (`openevolve/iteration.py`)
- Run in a separate process (safety!)
- Pass program to evaluator
- Get back score + metadata
- Worker process exits (clean slate for next iteration)

**Step 4: Storage**
- If program passes threshold, add to database
- MAP-Elites algorithm decides where to store it
- May replace existing program if new one is better

**Step 5: Migration** (periodic)
- After N iterations, islands exchange programs
- Best programs from Island 1 → Island 2, Island 3
- Prevents islands from becoming too isolated

### 7. What Gets Optimized?

The LLM tries various strategies to make the kernel faster:

#### Strategy 1: Vectorization
```metal
// Before: Process one element at a time
for (uint d = 0; d < HEAD_DIM; d++) {
    score += query_vec[d] * keys[k_base + d];
}

// After: Process 8 elements at once (SIMD)
vec<T, 8> query_v = load_vector(query_vec);
vec<T, 8> key_v = load_vector(keys + k_base);
score += dot(query_v, key_v);
```

#### Strategy 2: Algorithm Fusion
```metal
// Before: Three separate passes through data
// Pass 1: Find max score
// Pass 2: Compute softmax denominator
// Pass 3: Compute weighted sum

// After: Two passes (fused operations)
// Pass 1: Find max score
// Pass 2: Compute softmax AND weighted sum together
```

#### Strategy 3: Memory Access Optimization
```metal
// Before: Recalculate indices every time
uint k_base = batch_idx * ... + head_idx * ... + key_pos * ...;

// After: Pre-compute base, add offset
const uint k_base_start = batch_idx * ... + kv_head_idx * ...;
uint k_base = k_base_start + key_pos * HEAD_DIM;  // Faster!
```

### 8. Results & Scoring

**Scoring Formula** (simplified):
```python
final_score = (
    0.5 * correctness_score +           # Must be correct!
    0.3 * speed_improvement +            # Faster is better
    0.1 * memory_improvement +           # Less memory is better
    0.1 * consistency_across_tests       # Works on all tests
)
```

**Real Results** (from README.md):
- **Average decode speed improvement**: +12.5%
- **Best case**: +106% on repetitive patterns
- **Prefill speed**: +14.4% improvement
- **Memory usage**: -0.99% (slightly better)

**Key Insight**: Not all programs are faster on all workloads! Some excel at long sequences, others at short sequences.

## The Complete Flow (Putting It All Together)

```
START
  │
  ├─→ Load initial_program.py (working Metal kernel)
  │
  ├─→ Load config.yaml (evolution rules)
  │
  ├─→ Initialize 3 islands with copies of initial program
  │
  ├─→ FOR iteration 1 to 25:
  │     │
  │     ├─→ Each island samples programs
  │     │     ├─→ 65% from elite programs (best ones)
  │     │     └─→ 35% randomly (exploration)
  │     │
  │     ├─→ Build prompt:
  │     │     ├─→ System message (optimization strategies)
  │     │     ├─→ Top 3 programs (examples)
  │     │     └─→ 2 diverse programs (inspiration)
  │     │
  │     ├─→ LLM generates mutation:
  │     │     ├─→ 60% chance: Gemini Flash (fast)
  │     │     └─→ 40% chance: Gemini Pro (smart)
  │     │
  │     ├─→ Create new program with mutated code
  │     │
  │     ├─→ Evaluator tests new program:
  │     │     ├─→ ✓ Extract code
  │     │     ├─→ ✓ Safety validation
  │     │     ├─→ ✓ Measure baseline
  │     │     ├─→ ✓ Correctness test (>90% match)
  │     │     ├─→ ✓ Run 20 benchmarks
  │     │     └─→ ✓ Calculate final score
  │     │
  │     ├─→ If score > threshold:
  │     │     └─→ Add to database (MAP-Elites)
  │     │           ├─→ Map to grid cell
  │     │           └─→ Keep if better than existing
  │     │
  │     ├─→ Every 5 iterations:
  │     │     └─→ Save checkpoint (can resume later)
  │     │
  │     └─→ Every 10 iterations:
  │           └─→ Islands migrate best programs
  │
  └─→ DONE: Return best program found

```

## Key Takeaways

1. **Automatic Optimization**: No human needs to manually tweak GPU code
2. **Safety First**: Bulletproof evaluation prevents crashes
3. **Diversity Matters**: Islands + MAP-Elites maintain variety
4. **Hybrid Approach**: Mix fast LLM (Flash) with smart LLM (Pro)
5. **Real Gains**: 12.5% average improvement, up to 106% in best cases

## File References Summary

| Component | Location | Key Lines |
|-----------|----------|-----------|
| Initial kernel code | `initial_program.py` | 68-197 (EVOLVE-BLOCK) |
| Evaluator logic | `evaluator.py` | 105-200 (evaluate function) |
| Configuration | `config.yaml` | All |
| Controller | `openevolve/controller.py` | Main loop |
| Database/Islands | `openevolve/database.py` | MAP-Elites + islands |
| LLM integration | `openevolve/llm/` | Model ensemble |
| Iteration worker | `openevolve/iteration.py` | Worker process |

## Common Questions

**Q: Why not just use one best program?**
A: MAP-Elites maintains diversity. Some programs are fast on short sequences, others on long ones. You want options!

**Q: Why use islands?**
A: Prevents premature convergence. If all programs evolve together, they become too similar too quickly.

**Q: Why two LLM models?**
A: Gemini Flash is fast and cheap for quick iterations. Gemini Pro is smarter for complex optimizations. Mixing both balances cost and quality.

**Q: What if a mutation breaks the code?**
A: The evaluator catches it! Failed programs get score = 0 and are discarded.

**Q: Can I use this for other kernels?**
A: Yes! Just:
1. Write your initial kernel
2. Mark the EVOLVE-BLOCK
3. Create an evaluator
4. Configure evolution parameters
5. Run!

## Conclusion

The GPU kernel use case demonstrates OpenEvolve's power for automatic code optimization. By combining LLM creativity, robust evaluation, and evolutionary algorithms (islands + MAP-Elites), it discovers optimizations that outperform hand-tuned baselines.

The key insight: **Evolution explores a vast space of optimizations that humans might never try manually.**

---

## How Programs Are Loaded and Integrated

### Can Programs Be Part of a Larger System?

**Yes!** Programs in OpenEvolve can be either:
1. **Standalone programs** (simple cases)
2. **Modules within larger systems** (like the GPU kernel example)

The Metal kernel example is actually a **module** that integrates with MLX-LM (a complete language model inference system).

### The Loading Process

#### Step 1: Initial Program Loading

**Command Line** (`openevolve-run.py`):
```bash
python openevolve-run.py \
    examples/mlx_metal_kernel_opt/initial_program.py \
    examples/mlx_metal_kernel_opt/evaluator.py \
    --config examples/mlx_metal_kernel_opt/config.yaml
```

**What happens** (`openevolve/cli.py:22-27`):
- Takes two required arguments:
  - `initial_program`: Path to your program file
  - `evaluation_file`: Path to the evaluator

**Code Loading** (`openevolve/controller.py:211-214`):
```python
def _load_initial_program(self) -> str:
    """Load the initial program from file"""
    with open(self.initial_program_path, "r") as f:
        return f.read()
```

Simple! OpenEvolve just reads your program as **text**.

#### Step 2: Program Storage and Evolution

Throughout evolution:
- Programs are stored as **text strings** in the database
- LLMs mutate the text
- Each evolved program is also just text

**Key insight**: OpenEvolve doesn't care about your program's structure. It just treats it as text to evolve.

#### Step 3: Evaluation (Where Integration Happens)

**The Evaluator's Job** (`openevolve/evaluator.py:156-168`):
```python
# Create a temporary file for the program
with tempfile.NamedTemporaryFile(suffix=self.program_suffix, delete=False) as temp_file:
    temp_file.write(program_code.encode("utf-8"))
    temp_file_path = temp_file.name

# Run evaluation
result = await self._direct_evaluate(temp_file_path)
```

The evaluator:
1. Writes program text to a temporary file
2. Loads the evaluation function from your evaluator file
3. Calls `evaluate(program_text)` with the program

### Integration Pattern: The "Hook" System

For the Metal kernel case, the program needs to integrate with MLX-LM. Here's how:

#### The Hook Functions (Built Into Your Program)

**Location**: `initial_program.py:324-357`

Your program defines hook functions:

```python
def create_metal_qwen3_optimization_hook():
    """Create hooks to replace Qwen3's attention with optimized version."""

    def apply_optimization_hook():
        """Apply the Metal kernel optimized attention"""
        import mlx_lm.models.qwen3 as qwen3_module

        # Store original attention class
        original_attention = qwen3_module.Attention

        # Replace with optimized implementation
        qwen3_module.Attention = CustomGQAAttention  # <-- The evolved class!

        return original_attention

    def remove_optimization_hook(original_attention):
        """Remove the optimization hook"""
        import mlx_lm.models.qwen3 as qwen3_module
        qwen3_module.Attention = original_attention

    return apply_optimization_hook, remove_optimization_hook
```

**How it works**:
1. Python's module system allows replacing classes at runtime
2. We import the original MLX-LM Qwen3 module
3. Replace `qwen3_module.Attention` with our `CustomGQAAttention`
4. Now when MLX-LM loads the model, it uses YOUR optimized attention!

#### The Evaluator Uses the Hooks

**Extraction** (`evaluator.py:227-302`):
```python
def _bulletproof_extract_custom_attention(self, program_text: str):
    # Create safe execution environment
    exec_globals = {...}  # Safe globals with mlx, numpy, etc.

    # Execute program text
    exec(program_text, exec_globals)

    # Extract the custom class
    custom_class = exec_globals.get("CustomGQAAttention")

    return {"success": True, "class": custom_class}
```

**Hook Application** (`evaluator.py:865-882`):
```python
def _apply_attention_hook_safely(self, custom_attention_class):
    import mlx_lm.models.qwen3 as qwen3_module

    # Store original
    original_attention = qwen3_module.Attention

    # Apply custom attention (the hook!)
    qwen3_module.Attention = custom_attention_class

    # Now MLX-LM will use the optimized version
    return original_attention
```

**Full Evaluation Flow**:
```python
# 1. Extract custom class
custom_class = extract_custom_attention(program_text)

# 2. Apply hook (replace system module)
original = apply_hook(custom_class)

# 3. Run benchmarks (uses optimized version)
results = benchmark_suite.run()

# 4. Remove hook (restore original)
remove_hook(original)
```

### Visual Flow: Program Integration

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INITIAL LOADING                                          │
│                                                             │
│  initial_program.py (file on disk)                         │
│         ↓                                                   │
│  Controller reads entire file as text string               │
│         ↓                                                   │
│  Stored in database as TEXT                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 2. EVOLUTION                                                │
│                                                             │
│  Program text from database                                │
│         ↓                                                   │
│  LLM mutates EVOLVE-BLOCK section                          │
│         ↓                                                   │
│  New program text (still just a string)                    │
│         ↓                                                   │
│  Store back in database                                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 3. EVALUATION (Integration happens here!)                  │
│                                                             │
│  Program text                                              │
│         ↓                                                   │
│  Write to temporary file: /tmp/tmpXYZ.py                   │
│         ↓                                                   │
│  Evaluator loads and executes program:                     │
│    exec_globals = {}                                       │
│    exec(program_text, exec_globals)                        │
│         ↓                                                   │
│  Extract CustomGQAAttention class:                         │
│    custom_class = exec_globals["CustomGQAAttention"]       │
│         ↓                                                   │
│  Apply hook to system:                                     │
│    import mlx_lm.models.qwen3 as qwen3                     │
│    original = qwen3.Attention                              │
│    qwen3.Attention = custom_class  ← REPLACEMENT!          │
│         ↓                                                   │
│  Run system benchmarks:                                    │
│    model = load_model("Qwen3-0.6B")  ← Uses custom!        │
│    results = benchmark(model)                              │
│         ↓                                                   │
│  Restore original:                                         │
│    qwen3.Attention = original                              │
└─────────────────────────────────────────────────────────────┘
```

### Key Requirements for System Integration

To make your program integrate with a larger system:

#### 1. Define a Clear Interface

Your program must provide a replaceable component:
```python
class CustomGQAAttention(nn.Module):
    """Must match the interface of original Attention class"""

    def __init__(self, args):
        # Same initialization signature
        pass

    def __call__(self, x, mask=None, cache=None):
        # Same call signature
        return output
```

#### 2. Provide Hook Functions (Optional but Recommended)

```python
def create_optimization_hook():
    """Returns (apply_hook, remove_hook) functions"""

    def apply_hook():
        # Replace system module
        original = system_module.Component
        system_module.Component = YourCustomClass
        return original

    def remove_hook(original):
        # Restore system module
        system_module.Component = original

    return apply_hook, remove_hook
```

#### 3. Make Your Evaluator Handle Integration

Your evaluator (`evaluator.py`) must:

**Step A: Extract the evolved component**
```python
# Execute program to get the class
exec_globals = create_safe_environment()
exec(program_text, exec_globals)
custom_class = exec_globals["YourCustomClass"]
```

**Step B: Apply to the system**
```python
import your_system_module
original = your_system_module.Component
your_system_module.Component = custom_class
```

**Step C: Test with the full system**
```python
# Load the system (now uses your component)
system = load_system()
results = test_system(system)
```

**Step D: Clean up**
```python
your_system_module.Component = original
```

### Example: Simple vs System Integration

#### Simple Standalone Program

**initial_program.py**:
```python
# EVOLVE-BLOCK-START
def optimize_function(x):
    return x * 2 + 1
# EVOLVE-BLOCK-END
```

**evaluator.py**:
```python
def evaluate(program_text):
    exec_globals = {}
    exec(program_text, exec_globals)
    func = exec_globals["optimize_function"]

    # Test directly
    result = func(10)
    score = calculate_score(result)
    return {"score": score}
```

#### System-Integrated Program (Metal Kernel)

**initial_program.py**:
```python
import mlx.core as mx
import mlx.nn as nn

# EVOLVE-BLOCK-START
class CustomGQAAttention(nn.Module):
    def __init__(self, args):
        # ... initialization

    def __call__(self, x, mask=None, cache=None):
        # ... custom Metal kernel code
        return output
# EVOLVE-BLOCK-END

def create_metal_qwen3_optimization_hook():
    # Hook functions to integrate with MLX-LM
    # ...
```

**evaluator.py**:
```python
def evaluate(program_text):
    # 1. Extract custom class
    exec_globals = {...}
    exec(program_text, exec_globals)
    custom_class = exec_globals["CustomGQAAttention"]

    # 2. Replace in system
    import mlx_lm.models.qwen3 as qwen3
    original = qwen3.Attention
    qwen3.Attention = custom_class

    # 3. Test with full system
    model = load_qwen3_model()  # Uses custom attention!
    results = benchmark_model(model)

    # 4. Restore
    qwen3.Attention = original

    return results
```

### Compilation and Running

#### For Python Modules

No compilation needed! Python's `exec()` compiles and runs the code:
```python
exec(program_text, exec_globals)  # Compiles + executes
```

#### For Metal Kernels

The Metal kernel is compiled by MLX at runtime:

**In your program** (`initial_program.py:205-231`):
```python
kernel = mx.fast.metal_kernel(
    name="qwen3_gqa_attention_kernel",
    input_names=["queries", "keys", "values", "mask", "scale", "use_mask"],
    output_names=["output"],
    source=kernel_source,  # Metal code as string
)

# MLX compiles the Metal kernel here ↑
# Then you can execute it:
outputs = kernel(
    inputs=[queries, keys, values, mask_tensor, scale_tensor, use_mask_tensor],
    output_shapes=[(B, num_heads, L, head_dim)],
    output_dtypes=[queries.dtype],
    grid=(L, num_heads, B),
    threadgroup=(threadgroup_size, 1, 1),
)
```

**Flow**:
1. Your program defines Metal kernel as a string
2. MLX's `metal_kernel()` compiles it to GPU binary
3. Executing the kernel runs on GPU
4. If compilation fails, the program gets score 0

### Summary: Loading & Integration

| Aspect | Answer | Code Reference |
|--------|--------|----------------|
| **Input format** | Python file (`.py`) read as text | `controller.py:211-214` |
| **Storage** | Text strings in database | `database.py` |
| **Evolution** | LLM mutates text, still text | `llm/ensemble.py` |
| **Evaluation** | Write to temp file, exec, test | `evaluator.py:156-168` |
| **Standalone?** | Yes, can be standalone | Simple examples |
| **System module?** | Yes, use hook pattern | `initial_program.py:324-357` |
| **Integration** | Runtime module replacement | `evaluator.py:865-882` |
| **Compilation** | Python: exec()<br>Metal: MLX runtime | `evaluator.py`<br>`initial_program.py:205-231` |

### Tips for Your Own System Integration

1. **Keep interface compatible**: Your evolved component must match the original API
2. **Use hooks**: Define apply/remove functions for clean integration
3. **Test in isolation first**: Verify your component works standalone
4. **Handle errors gracefully**: System integration can fail in many ways
5. **Clean up**: Always restore the original module
6. **Document dependencies**: Make it clear what system you're integrating with
