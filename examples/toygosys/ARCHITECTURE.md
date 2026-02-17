# Toy Go System - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         OPENEVOLVE                              │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐      │
│  │   Database   │   │  LLM Engine  │   │  Evaluator   │      │
│  │  (Programs)  │   │   (GPT-4o)   │   │   (Python)   │      │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘      │
│         │                  │                   │               │
│         │  1. Sample       │  2. Mutate        │  3. Evaluate  │
│         ↓                  ↓                   ↓               │
└─────────┼──────────────────┼───────────────────┼───────────────┘
          │                  │                   │
          │                  │                   │ Writes Go code
          │                  │                   ↓
┌─────────┼──────────────────┼───────────────────┼───────────────┐
│         │                  │                   │               │
│         │              GO SYSTEM               │               │
│         │                                      ↓               │
│  ┌──────┴──────────────────────────────────────────────┐      │
│  │  gosystem/                                           │      │
│  │                                                      │      │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │      │
│  │  │   main.go    │  │   game.go    │  │ strategy  │ │      │
│  │  │  (Entry pt)  │  │  (Scoring)   │  │   .go     │←┼──────┘
│  │  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │ EVOLVED!
│  │         │                 │                 │       │
│  │         │  Calls          │  Evaluates      │       │
│  │         ↓                 ↓                 ↓       │
│  │    PlayGame() ──→ EvaluateStrategy(GetStrategy())  │
│  │                                                     │
│  │  Output: "SCORE: 210"                              │
│  └─────────────────────────────────────────────────────┘
│         ↓
│    Parsed by evaluator → Score: 0.70
│         │
└─────────┼────────────────────────────────────────────────────┘
          │ 4. Return to OpenEvolve
          ↓
      Store if score improves
```

## Component Details

### OpenEvolve Components

#### 1. Database
- Stores program texts as strings
- Maintains population of 10 programs
- Uses 2 islands for diversity
- Tracks scores and metrics

#### 2. LLM Engine
- Model: GPT-4o-mini
- Temperature: 0.7 (creative but stable)
- Receives system prompt with game rules
- Generates improved Go code

#### 3. Evaluator (`evaluator.py`)
- Extracts Go code from Python wrapper
- Writes to `strategy.go`
- Builds Go system
- Runs and parses output
- Returns normalized score

### Go System Modules

#### Module 1: `main.go` (Fixed)
```go
func main() {
    score := PlayGame()
    fmt.Printf("SCORE: %d\n", score)
}
```
Entry point that runs the game.

#### Module 2: `game.go` (Fixed)
```go
func EvaluateStrategy(guesses []int) int {
    targets := []int{25, 50, 75}
    score := 0
    for i := 0; i < len(guesses); i++ {
        distance := abs(guesses[i] - targets[i])
        score += (100 - distance)
    }
    return score
}
```
Scoring logic - awards points for closeness to targets.

#### Module 3: `strategy.go` (Evolved)
```go
func GetStrategy() []int {
    // EVOLVE-BLOCK-START
    guesses := []int{10, 20, 30}  // ← OpenEvolve modifies this
    // EVOLVE-BLOCK-END
    return guesses
}
```
The strategy that OpenEvolve optimizes.

## Evolution Flow (Step by Step)

### Iteration 0: Initial State
```
Database: [initial_program with score 0.70]
Strategy: []int{10, 20, 30}
Score: 210/300 = 0.70
```

### Iteration 1: First Evolution

**Step 1: Sample**
```
Database samples: initial_program (0.70)
```

**Step 2: LLM Mutation**
```
LLM receives:
  - System prompt (game rules)
  - Initial strategy code
  - Score: 0.70

LLM generates:
  guesses := []int{20, 45, 70}  // Closer to targets!
```

**Step 3: Evaluator Integration**
```python
# evaluator.py
go_code = extract_go_code(mutated_program)
write_file("gosystem/strategy.go", go_code)
run("go build -o toygosys")
output = run("./toygosys")
score = parse("SCORE: 235")
return {"combined_score": 235/300}  # 0.78
```

**Step 4: Store**
```
Database: [
  initial_program (0.70),
  mutated_v1 (0.78)  ← New best!
]
```

### Iteration 2: Refinement

**Sample**: `mutated_v1` (0.78)

**LLM sees improvement**, tries to get even closer:
```go
guesses := []int{24, 49, 74}  // Very close!
```

**Score**: 297/300 = 0.99

### Iteration 3: Perfection

**LLM figures out exact targets**:
```go
guesses := []int{25, 50, 75}  // Perfect!
```

**Score**: 300/300 = 1.00 ✓

## Data Flow

```
┌─────────────────────────────────────────────────────────┐
│ 1. PROGRAM REPRESENTATION IN OPENEVOLVE                │
│                                                         │
│ initial_program.py:                                     │
│   GO_STRATEGY_CODE = """                                │
│   package main                                          │
│   func GetStrategy() []int {                            │
│       // EVOLVE-BLOCK-START                             │
│       guesses := []int{10, 20, 30}                      │
│       // EVOLVE-BLOCK-END                               │
│       return guesses                                    │
│   }                                                     │
│   """                                                   │
└─────────────────────────────────────────────────────────┘
            │
            │ Stored as TEXT in database
            ↓
┌─────────────────────────────────────────────────────────┐
│ 2. LLM MUTATION                                         │
│                                                         │
│ LLM modifies EVOLVE-BLOCK:                              │
│   guesses := []int{10, 20, 30}                          │
│               ↓                                         │
│   guesses := []int{20, 45, 70}  // Better!             │
└─────────────────────────────────────────────────────────┘
            │
            │ New program text
            ↓
┌─────────────────────────────────────────────────────────┐
│ 3. EVALUATOR EXTRACTS GO CODE                           │
│                                                         │
│ evaluator.py:extract_go_code()                          │
│   Extracts from Python string wrapper                   │
│   Returns pure Go code                                  │
└─────────────────────────────────────────────────────────┘
            │
            │ Pure Go code
            ↓
┌─────────────────────────────────────────────────────────┐
│ 4. WRITE TO GO FILE                                     │
│                                                         │
│ gosystem/strategy.go:                                   │
│   package main                                          │
│   func GetStrategy() []int {                            │
│       // EVOLVE-BLOCK-START                             │
│       guesses := []int{20, 45, 70}  ← Updated!          │
│       // EVOLVE-BLOCK-END                               │
│       return guesses                                    │
│   }                                                     │
└─────────────────────────────────────────────────────────┘
            │
            │ File on disk
            ↓
┌─────────────────────────────────────────────────────────┐
│ 5. BUILD AND RUN                                        │
│                                                         │
│ $ go build -o toygosys                                  │
│ $ ./toygosys                                            │
│ → SCORE: 235                                            │
└─────────────────────────────────────────────────────────┘
            │
            │ Terminal output
            ↓
┌─────────────────────────────────────────────────────────┐
│ 6. PARSE SCORE                                          │
│                                                         │
│ evaluator.py:parse_score("SCORE: 235")                  │
│   → 235                                                 │
│   → 235 / 300 = 0.78                                    │
│   → {"combined_score": 0.78}                            │
└─────────────────────────────────────────────────────────┘
            │
            │ Return to OpenEvolve
            ↓
┌─────────────────────────────────────────────────────────┐
│ 7. UPDATE DATABASE                                      │
│                                                         │
│ If score > threshold:                                   │
│   database.add(program, score=0.78)                     │
│   → Stored for future iterations                        │
└─────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Why Go Code in Python String?

**Reason**: OpenEvolve works with Python programs
- LLMs are good at generating text
- Easier to manipulate as strings
- Python has better AI tooling

**Alternative**: Could use pure Go files, but would need Go code parser/generator.

### 2. Why Rebuild Every Time?

**Reason**: Ensure code correctness
- Go compiler catches syntax errors
- Build failures = invalid program = score 0
- Clean slate each iteration

**Trade-off**: Slower (0.5-1s per build) but safer.

### 3. Why Simple Scoring?

**Reason**: Easy to verify and debug
- Clear optimal solution (25, 50, 75)
- LLM can understand the goal
- Fast evaluation (<0.1s to run)

**Production**: Use real metrics (latency, accuracy, etc.)

### 4. Why 3 Modules?

**Reason**: Demonstrate system integration
- Shows fixed vs evolved code
- Realistic structure (entry, engine, module)
- Easy to extend

**Extension**: Add more modules (tactics.go, heuristics.go)

## File Structure

```
toygosys/
│
├── README.md              # User documentation
├── ARCHITECTURE.md        # This file
├── run.sh                 # Quick start script
│
├── initial_program.py     # Starting Go code
├── evaluator.py           # Integration logic
├── config.yaml            # Evolution parameters
│
└── gosystem/              # The Go system
    ├── go.mod             # Go module definition
    ├── main.go            # Entry point (fixed)
    ├── game.go            # Scoring engine (fixed)
    └── strategy.go        # Evolved module
```

## Execution Timeline

```
T=0: User runs: ./run.sh
  ├─ T=0.1s: Verify Go installed
  ├─ T=0.2s: Check API key
  ├─ T=0.3s: Test initial build
  └─ T=0.5s: Start OpenEvolve

T=0.5s: OpenEvolve initialization
  ├─ Load config.yaml
  ├─ Load initial_program.py
  ├─ Initialize database
  └─ Evaluate initial program
      ├─ Build: 0.5s
      ├─ Run: 0.05s
      └─ Score: 0.70

T=2s: Iteration 1
  ├─ Sample from database: 0.01s
  ├─ LLM mutation: 1.5s
  ├─ Evaluate:
  │   ├─ Extract: 0.01s
  │   ├─ Write: 0.01s
  │   ├─ Build: 0.5s
  │   └─ Run: 0.05s
  └─ Store: 0.01s
  Total: ~2s per iteration

T=20s: Iteration 10 complete
  └─ Best program found

Total: ~20 seconds for 10 iterations
```

## Extending the Demo

### Add Complexity to Strategy

```go
// Simple (current)
guesses := []int{25, 50, 75}

// With computation
guesses := []int{}
for i := 0; i < 3; i++ {
    target := (i + 1) * 25
    guesses = append(guesses, target)
}

// With helper function
func calculateGuess(index int) int {
    return (index + 1) * 25
}
```

### Add More Modules

```
gosystem/
├── strategy.go      # Number selection (evolved)
├── tactics.go       # Move ordering (evolved)
├── heuristics.go    # Evaluation (evolved)
└── game.go          # Engine (fixed)
```

Each needs its own initial_program.py and evolves separately.

### Different Games

**Sorting**: Evolve comparison function
**Pathfinding**: Evolve heuristic
**Game AI**: Evolve decision tree

## Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Go build | 0.5s | Could cache if code unchanged |
| Go run | 0.05s | Very fast for simple program |
| LLM call | 1-2s | Depends on model and API |
| Evaluation total | 2-3s | Dominated by LLM |
| Full evolution (10 iter) | 20-30s | Scales linearly |

## Conclusion

This toy demo shows all key concepts:
1. ✓ Multi-module system
2. ✓ Cross-language integration (Python ↔ Go)
3. ✓ Build and run pipeline
4. ✓ Score extraction
5. ✓ Iterative improvement

Simple but complete!
