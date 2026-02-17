#!/bin/bash
# Quick start script for toygosys demo

set -e

echo "====================================="
echo "  Toy Go System - OpenEvolve Demo"
echo "====================================="
echo

# Check Go is installed
if ! command -v go &> /dev/null; then
    echo "❌ Error: Go is not installed"
    echo "Install from: https://go.dev/dl/"
    exit 1
fi
echo "✓ Go installed: $(go version)"

# Check OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ Error: OPENAI_API_KEY not set"
    echo "Set it with: export OPENAI_API_KEY='your-key'"
    exit 1
fi
echo "✓ OPENAI_API_KEY is set"

# Get the OpenEvolve root directory (3 levels up)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
OPENEVOLVE_ROOT="$( cd "$SCRIPT_DIR/../../.." && pwd )"

echo "✓ OpenEvolve root: $OPENEVOLVE_ROOT"
echo

# Test Go system first
echo "Testing Go system..."
cd "$SCRIPT_DIR/gosystem"
go build -o toygosys
INITIAL_SCORE=$(./toygosys | grep -oP 'SCORE: \K\d+')
echo "✓ Initial score: $INITIAL_SCORE"
echo

# Run OpenEvolve
echo "Starting evolution..."
echo "This will run 10 iterations and should find the optimal solution"
echo

cd "$OPENEVOLVE_ROOT"
python openevolve-run.py \
  "$SCRIPT_DIR/initial_program.py" \
  "$SCRIPT_DIR/evaluator.py" \
  --config "$SCRIPT_DIR/config.yaml" \
  --iterations 10

echo
echo "====================================="
echo "  Evolution Complete!"
echo "====================================="
echo
echo "View results:"
echo "  Best program: $SCRIPT_DIR/openevolve_output/best_program.py"
echo "  Logs: $SCRIPT_DIR/openevolve_output/evolution.log"
