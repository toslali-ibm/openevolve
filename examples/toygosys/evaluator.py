"""
Evaluator for Go System

This evaluator:
1. Takes evolved Go code
2. Writes it to strategy.go
3. Rebuilds the Go system
4. Runs the system
5. Parses the score output
"""

import os
import re
import subprocess
import sys
from typing import Dict, Any


def evaluate(program_text: str) -> Dict[str, Any]:
    """
    Evaluate a Go strategy program

    Args:
        program_text: The program text (can be file path or code)

    Returns:
        Dictionary with score and metrics
    """
    print("\n" + "=" * 60)
    print("Evaluating Go Strategy")
    print("=" * 60)

    # Handle file path vs direct text
    if program_text.startswith("/") and "\n" not in program_text:
        if os.path.exists(program_text):
            with open(program_text, "r") as f:
                program_text = f.read()
        else:
            return {"combined_score": 0.0, "error": "File not found"}

    # Extract Go code from Python string
    go_code = extract_go_code(program_text)
    if not go_code:
        return {"combined_score": 0.0, "error": "Failed to extract Go code"}

    # Validate Go syntax
    if not validate_go_syntax(go_code):
        return {"combined_score": 0.0, "error": "Invalid Go syntax"}

    # Get path to Go system
    current_dir = os.path.dirname(os.path.abspath(__file__))
    go_system_dir = os.path.join(current_dir, "gosystem")
    strategy_file = os.path.join(go_system_dir, "strategy.go")

    # Backup original strategy
    backup_file = strategy_file + ".backup"
    if os.path.exists(strategy_file):
        with open(strategy_file, "r") as f:
            original_code = f.read()
        with open(backup_file, "w") as f:
            f.write(original_code)

    try:
        # Write evolved strategy
        print(f"Writing strategy to {strategy_file}")
        with open(strategy_file, "w") as f:
            f.write(go_code)

        # Build the Go system
        print("Building Go system...")
        build_result = subprocess.run(
            ["go", "build", "-o", "toygosys"],
            cwd=go_system_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if build_result.returncode != 0:
            print(f"Build failed: {build_result.stderr}")
            return {"combined_score": 0.0, "error": f"Build failed: {build_result.stderr}"}

        print("✓ Build successful")

        # Run the system
        print("Running Go system...")
        run_result = subprocess.run(
            ["./toygosys"],
            cwd=go_system_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if run_result.returncode != 0:
            print(f"Run failed: {run_result.stderr}")
            return {"combined_score": 0.0, "error": f"Run failed: {run_result.stderr}"}

        # Parse score from output
        output = run_result.stdout
        print(f"System output:\n{output}")

        score = parse_score(output)
        if score is None:
            return {"combined_score": 0.0, "error": "Failed to parse score"}

        print(f"✓ Score: {score}")

        # Normalize score to 0-1 range (max possible score is 300)
        normalized_score = min(score / 300.0, 1.0)

        return {
            "combined_score": normalized_score,
            "raw_score": score,
            "max_possible_score": 300,
        }

    except subprocess.TimeoutExpired:
        return {"combined_score": 0.0, "error": "Timeout"}

    except Exception as e:
        print(f"Error: {e}")
        return {"combined_score": 0.0, "error": str(e)}

    finally:
        # Restore original strategy
        if os.path.exists(backup_file):
            with open(backup_file, "r") as f:
                original = f.read()
            with open(strategy_file, "w") as f:
                f.write(original)
            os.remove(backup_file)


def extract_go_code(program_text: str) -> str:
    """Extract Go code from Python program text"""

    # Look for GO_STRATEGY_CODE variable
    match = re.search(r'GO_STRATEGY_CODE\s*=\s*"""(.*?)"""', program_text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # If no Python wrapper, assume it's raw Go code
    if "package main" in program_text:
        return program_text

    return ""


def validate_go_syntax(go_code: str) -> bool:
    """Basic Go syntax validation"""

    # Check for required elements
    required = ["package main", "func GetStrategy", "[]int", "return"]
    for req in required:
        if req not in go_code:
            print(f"Missing required element: {req}")
            return False

    # Check for EVOLVE-BLOCK markers
    if "EVOLVE-BLOCK-START" not in go_code or "EVOLVE-BLOCK-END" not in go_code:
        print("Missing EVOLVE-BLOCK markers")
        return False

    return True


def parse_score(output: str) -> int:
    """Parse score from program output"""

    # Look for "SCORE: <number>" pattern
    match = re.search(r"SCORE:\s*(\d+)", output)
    if match:
        return int(match.group(1))

    return None


if __name__ == "__main__":
    # Test the evaluator
    test_program = os.path.join(os.path.dirname(__file__), "initial_program.py")
    result = evaluate(test_program)
    print(f"\nEvaluation result: {result}")
