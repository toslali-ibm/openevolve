# Toy Go System - OpenEvolve Demo

A simple demonstration of using OpenEvolve to evolve a Go program module.

## The Evolution Loop (Simple!)

```
1. LLM improves Go strategy code
   ↓
2. Write to strategy.go
   ↓
3. go build (compile Go system)
   ↓
4. ./toygosys (run system, get score)
   ↓
5. If score improves → keep it
   ↓
6. Repeat (10 iterations)
```

**Goal**: Find numbers [25, 50, 75] to maximize score
**Start**: [10, 20, 30] → Score 210
**End**: [25, 50, 75] → Score 300 ✓

## What This Demo Does

This demo shows how OpenEvolve can optimize a Go strategy module by:
1. Taking the current strategy code
2. Using LLM to improve the logic
3. Rebuilding the Go system
4. Running it to get a score
5. Keeping improvements that score higher

## The System

### Go System (3 modules)

```
gosystem/
├── main.go       - Entry point, runs the game
├── game.go       - Game engine (scoring logic) - FIXED
└── strategy.go   - Strategy module - EVOLVED BY OPENEVOLVE
```

**The Game**: A simple number guessing optimization
- Strategy picks 3 numbers
- Goal: Get close to targets [25, 50, 75]
- Score: Each guess gets (100 - distance) points
- Maximum possible score: 300 (perfect guesses)

**Initial Strategy**: `[10, 20, 30]` → Score: ~120
**Optimal Strategy**: `[25, 50, 75]` → Score: 300

## Setup

### Prerequisites

1. **Go** (version 1.21+)
   ```bash
   go version
   ```

2. **Python** (version 3.10+)
   ```bash
   python --version
   ```

3. **OpenEvolve installed**
   ```bash
   cd /path/to/openevolve
   pip install -e .
   ```

4. **LLM API Key**
   ```bash
   export OPENAI_API_KEY="your-key-here"
   ```

### Test the Go System

First, verify the Go system works:

```bash
cd examples/toygosys/gosystem

# Build
go build -o toygosys

# Run
./toygosys
```

Expected output:
```
SCORE: 120
```

## Running OpenEvolve

### Quick Start

From the OpenEvolve root directory:

```bash
python openevolve-run.py \
  examples/toygosys/initial_program.py \
  examples/toygosys/evaluator.py \
  --config examples/toygosys/config.yaml \
  --iterations 10
```

### What Happens

**Iteration 1:**
```
1. Sample programs from database
2. LLM suggests: guesses := []int{20, 45, 70}
3. Write to strategy.go
4. Run: go build && ./toygosys
5. Output: SCORE: 235
6. Normalized score: 0.78
7. Store in database
```

**Iteration 2:**
```
1. Sample best programs (includes score 0.78)
2. LLM sees previous attempt, improves
3. Suggests: guesses := []int{25, 50, 75}
4. Build and run
5. Output: SCORE: 300
6. Normalized score: 1.0 (perfect!)
7. Store as best program
```

**Evolution continues...**
- Tries variations
- Explores different strategies
- Maintains best solution

## Understanding the Code

### Initial Program (`initial_program.py`)

```python
GO_STRATEGY_CODE = """package main

func GetStrategy() []int {
	// EVOLVE-BLOCK-START
	guesses := []int{10, 20, 30}
	// EVOLVE-BLOCK-END
	return guesses
}
"""
```

Only the code between `EVOLVE-BLOCK-START` and `EVOLVE-BLOCK-END` is modified.

### Evaluator (`evaluator.py`)

The evaluator handles the Go integration:

```python
def evaluate(program_text: str) -> Dict[str, Any]:
    # 1. Extract Go code from Python wrapper
    go_code = extract_go_code(program_text)

    # 2. Write to strategy.go
    with open("gosystem/strategy.go", "w") as f:
        f.write(go_code)

    # 3. Build Go system
    subprocess.run(["go", "build", "-o", "toygosys"])

    # 4. Run system
    result = subprocess.run(["./toygosys"])

    # 5. Parse score from output
    score = parse_score(result.stdout)  # "SCORE: 235"

    # 6. Return normalized score
    return {"combined_score": score / 300.0}
```

### Configuration (`config.yaml`)

Key settings:
- `max_iterations: 10` - Run 10 evolution iterations
- `primary_model: "gpt-4o-mini"` - Use GPT-4o-mini
- `population_size: 10` - Keep 10 programs in database
- `num_islands: 2` - Use 2 islands for diversity

## Viewing Results

### During Evolution

Watch the terminal output:
```
Iteration 1/10
  Sample: 2 programs
  LLM generates mutation
  Evaluating Go Strategy
  Building Go system...
  ✓ Build successful
  Running Go system...
  ✓ Score: 235
  Normalized: 0.78
  Added to database
```

### Best Program

After evolution finishes:
```bash
# View best program
cat examples/toygosys/openevolve_output/best_program.py
```

### Checkpoints

Evolution saves checkpoints every 5 iterations:
```bash
ls examples/toygosys/openevolve_output/checkpoints/
```

## Extending This Demo

### Change the Game

Edit `gosystem/game.go`:
```go
func EvaluateStrategy(guesses []int) int {
    // Add your own scoring logic
    // Example: maximize product, minimize variance, etc.
}
```

### More Complex Strategy

Evolve more complex logic:
```go
// EVOLVE-BLOCK-START
guesses := []int{}
for i := 0; i < 3; i++ {
    guess := calculateOptimal(i)  // Evolve this function
    guesses = append(guesses, guess)
}
// EVOLVE-BLOCK-END
```

### Multiple Modules

Add more Go files to evolve:
- `strategy.go` - Number selection
- `tactics.go` - Move ordering
- `heuristics.go` - Evaluation function

Just create separate initial programs and evaluators for each.

## Troubleshooting

### "go: command not found"

Install Go from https://go.dev/dl/

### "Build failed: syntax error"

The LLM generated invalid Go code. This is normal - the program gets score 0 and evolution tries again.

### "No improvement after many iterations"

The problem might be too simple (already optimal) or too hard. Try:
- Increase iterations
- Adjust temperature (higher = more creative)
- Improve system prompt with more guidance

### API Rate Limits

Use a smaller model or reduce parallel evaluations:
```yaml
evaluator:
  parallel_evaluations: 1  # Already set to 1
```

## Expected Evolution Path

```
Initial:    [10, 20, 30]  → Score: 120 (0.40)
Iteration 1: [15, 35, 55]  → Score: 185 (0.62)
Iteration 2: [20, 45, 70]  → Score: 235 (0.78)
Iteration 3: [24, 49, 74]  → Score: 297 (0.99)
Iteration 4: [25, 50, 75]  → Score: 300 (1.00) ← Perfect!
```

The LLM should figure out the targets by analyzing the code and scores!

## Key Takeaways

1. **OpenEvolve works with any language** - Just wrap it in Python and provide an evaluator
2. **Evaluator does the integration** - Writes files, builds, runs, parses output
3. **Evolution is iterative** - Each iteration builds on previous successes
4. **Simple systems work best for learning** - This toy example demonstrates the core concepts

## Next Steps

- Try changing the target numbers in `game.go`
- Add constraints (e.g., numbers must be even)
- Evolve multiple modules simultaneously
- Build a more complex system (sorting algorithm, path finding, etc.)
