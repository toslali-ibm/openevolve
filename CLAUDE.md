# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

OpenEvolve is an open-source implementation of Google DeepMind's AlphaEvolve system - an evolutionary coding agent that uses LLMs to optimize code through iterative evolution. The framework can evolve code in multiple languages (Python, R, Rust, etc.) for tasks like scientific computing, optimization, and algorithm discovery.

### Documentation

- **GPU Kernel Use Case Guide** (`GPU_KERNEL_USECASE_EXPLAINED.md`): Comprehensive explanation of the Metal kernel optimization example, including how programs are loaded, integrated with larger systems, and evolved. Simple language with code references and diagrams.

- **Toy Go System Demo** (`examples/toygosys/`): Simple working example showing OpenEvolve with a Go system. Demonstrates cross-language integration, build/run pipeline, and score-based evolution. Includes README and ARCHITECTURE documentation.

## Essential Commands

### Development Setup
```bash
# Install in development mode with all dependencies
pip install -e ".[dev]"

# Or use Makefile
make install
```

### Running Tests
```bash
# Run all tests
python -m unittest discover tests

# Or use Makefile
make test
```

### Code Formatting
```bash
# Format with Black
python -m black openevolve examples tests scripts

# Or use Makefile
make lint
```

### Running OpenEvolve
```bash
# Basic evolution run
python openevolve-run.py path/to/initial_program.py path/to/evaluator.py --config path/to/config.yaml --iterations 1000

# Resume from checkpoint
python openevolve-run.py path/to/initial_program.py path/to/evaluator.py \
  --config path/to/config.yaml \
  --checkpoint path/to/checkpoint_directory \
  --iterations 50
```

### Visualization
```bash
# View evolution tree
python scripts/visualizer.py --path examples/function_minimization/openevolve_output/checkpoints/checkpoint_100/
```

## High-Level Architecture

### Core Components

1. **Controller (`openevolve/controller.py`)**: Main orchestrator that manages the evolution process using ProcessPoolExecutor for parallel iteration execution.

2. **Database (`openevolve/database.py`)**: Implements MAP-Elites algorithm with island-based evolution:
   - Programs mapped to multi-dimensional feature grid
   - Multiple isolated populations (islands) evolve independently
   - Periodic migration between islands prevents convergence
   - Tracks absolute best program separately

3. **Evaluator (`openevolve/evaluator.py`)**: Cascade evaluation pattern:
   - Stage 1: Quick validation
   - Stage 2: Basic performance testing  
   - Stage 3: Comprehensive evaluation
   - Programs must pass thresholds at each stage

4. **LLM Integration (`openevolve/llm/`)**: Ensemble approach with multiple models, configurable weights, and async generation with retry logic.

5. **Iteration (`openevolve/iteration.py`)**: Worker process that samples from islands, generates mutations via LLM, evaluates programs, and stores artifacts.

### Key Architectural Patterns

- **Island-Based Evolution**: Multiple populations evolve separately with periodic migration
- **MAP-Elites**: Maintains diversity by mapping programs to feature grid cells
- **Artifact System**: Side-channel for programs to return debugging data, stored as JSON or files
- **Process Worker Pattern**: Each iteration runs in fresh process with database snapshot
- **Double-Selection**: Programs for inspiration differ from those shown to LLM
- **Lazy Migration**: Islands migrate based on generation counts, not iterations

### Code Evolution Markers

Mark code sections to evolve using:
```python
# EVOLVE-BLOCK-START
# Code to evolve goes here
# EVOLVE-BLOCK-END
```

### Configuration

YAML-based configuration with hierarchical structure:
- LLM models and parameters
- Evolution strategies (diff-based vs full rewrites)
- Database and island settings
- Evaluation parameters

### Important Patterns

1. **Checkpoint/Resume**: Automatic saving of entire system state with seamless resume capability
2. **Parallel Evaluation**: Multiple programs evaluated concurrently via TaskPool
3. **Error Resilience**: Individual failures don't crash system - extensive retry logic and timeout protection
4. **Prompt Engineering**: Template-based system with context-aware building and evolution history

### Experimental Features

Two experimental features can be toggled independently via config flags:

1. **Hypothesis-Driven Evolution** (`hypothesis_driven: true`): LLM writes structured HYPOTHESIS/EXPECT comments; RESULT verdicts auto-injected after evaluation.
2. **Threshold Tuning v2** (`tuning.enabled: true`): LLM marks numeric parameters with `@TUNE`; Optuna optimizes via tiered rescue (5 trials), checkpoint polish (10 trials), and final polish (20 trials). `@TUNED` feedback is **never** shown to the LLM.

### Running A/B Experiments

**Read `docs/AB_EXPERIMENT_HOWTO.md` before running any experiment.** It covers hypothesis, tuning, and combined experiments.

**Critical rules:**
- **NEVER run experiments in parallel** — always `--condition both` (sequential)
- **Always clean state first** — `rm -rf experiments/<dir>` before re-running
- **One variable at a time** — tuning A/B: both configs set `hypothesis_driven: false`; hypothesis A/B: both set `tuning.enabled: false`
- **Monitor during runs** — tail logs and verify expected log lines appear (see monitoring section in AB doc)

**Quick reference:**
```bash
# Tuning A/B
python scripts/run_experiment.py --task function_minimization_tuning --condition both --runs 2 --seed-start 300 --iterations 25 --output-dir experiments/tuning_ab_funcmin

# Hypothesis A/B
python scripts/run_experiment.py --task blis_router --condition both --runs 2 --seed-start 300 --iterations 25 --output-dir experiments/hypothesis_ab_blis

# Analyze
python scripts/analyze_experiment.py --data experiments/<dir>/convergence.csv --output experiments/<dir>
```

### Development Notes

- Python >=3.10 required
- Uses OpenAI-compatible APIs for LLM integration
- Tests use unittest framework
- Black for code formatting
- Artifacts threshold: Small (<10KB) stored in DB, large saved to disk
- Process workers load database snapshots for true parallelism