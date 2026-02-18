#!/usr/bin/env python3
"""
Minimal utility to compare evolved program against initial program.
Shows only the differences in the EVOLVE-BLOCK section.

Usage:
    python compare_program.py <evolved_program.py>
    python compare_program.py openevolve_output/best_program.py
"""

import sys
import re
from difflib import unified_diff
from pathlib import Path


def extract_evolve_block(code: str) -> str:
    """Extract only the EVOLVE-BLOCK section from Go code."""
    pattern = r'// EVOLVE-BLOCK-START(.*?)// EVOLVE-BLOCK-END'
    match = re.search(pattern, code, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def get_go_code(python_file: str) -> str:
    """Extract GO_ROUTING_CODE from Python file."""
    # Read and execute the Python file to get GO_ROUTING_CODE
    with open(python_file, 'r') as f:
        content = f.read()

    # Extract the Go code string
    match = re.search(r'GO_ROUTING_CODE\s*=\s*"""(.*?)"""', content, re.DOTALL)
    if match:
        return match.group(1)
    return ""


def compare_programs(initial_file: str, evolved_file: str):
    """Compare evolved program against initial, showing only differences."""

    # Extract Go code from both files
    initial_go = get_go_code(initial_file)
    evolved_go = get_go_code(evolved_file)

    if not initial_go:
        print(f"❌ Could not extract Go code from {initial_file}")
        return

    if not evolved_go:
        print(f"❌ Could not extract Go code from {evolved_file}")
        return

    # Extract EVOLVE-BLOCK sections
    initial_block = extract_evolve_block(initial_go)
    evolved_block = extract_evolve_block(evolved_go)

    if not initial_block:
        print("❌ No EVOLVE-BLOCK found in initial program")
        return

    if not evolved_block:
        print("❌ No EVOLVE-BLOCK found in evolved program")
        return

    # Compare
    initial_lines = initial_block.splitlines(keepends=True)
    evolved_lines = evolved_block.splitlines(keepends=True)

    diff = list(unified_diff(
        initial_lines,
        evolved_lines,
        fromfile='Initial (baseline)',
        tofile='Evolved (mutated)',
        lineterm=''
    ))

    if not diff:
        print("✅ No differences - evolved program is identical to initial")
        return

    # Print clean diff
    print("=" * 70)
    print("DIFFERENCES IN EVOLVE-BLOCK")
    print("=" * 70)
    print()

    for line in diff:
        line = line.rstrip()
        if line.startswith('---') or line.startswith('+++'):
            print(f"\033[1m{line}\033[0m")  # Bold
        elif line.startswith('-'):
            print(f"\033[91m{line}\033[0m")  # Red for removed
        elif line.startswith('+'):
            print(f"\033[92m{line}\033[0m")  # Green for added
        elif line.startswith('@@'):
            print(f"\033[94m{line}\033[0m")  # Blue for context
        else:
            print(line)

    print()
    print("=" * 70)

    # Summary
    removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
    added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))
    print(f"Summary: {removed} lines removed, {added} lines added")
    print("=" * 70)


def main():
    if len(sys.argv) != 2:
        print("Usage: python compare_program.py <evolved_program.py>")
        print()
        print("Examples:")
        print("  python compare_program.py openevolve_output/best_program.py")
        print("  python compare_program.py openevolve_output/checkpoints/checkpoint_25/best_program.py")
        sys.exit(1)

    evolved_file = sys.argv[1]
    initial_file = "initial_program.py"

    if not Path(initial_file).exists():
        print(f"❌ Initial program not found: {initial_file}")
        print("   Run this script from examples/blis_router/ directory")
        sys.exit(1)

    if not Path(evolved_file).exists():
        print(f"❌ Evolved program not found: {evolved_file}")
        sys.exit(1)

    compare_programs(initial_file, evolved_file)


if __name__ == "__main__":
    main()
