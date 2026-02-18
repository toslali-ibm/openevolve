"""
Utilities for comparing and visualizing program differences.
"""

import re
from difflib import unified_diff
from typing import Optional


def extract_evolve_block(code: str) -> Optional[str]:
    """
    Extract EVOLVE-BLOCK section from code.

    Args:
        code: Source code containing EVOLVE-BLOCK markers

    Returns:
        Content between markers, or None if not found
    """
    # Try multiple marker patterns
    patterns = [
        r'//\s*EVOLVE-BLOCK-START(.*?)//\s*EVOLVE-BLOCK-END',  # Go
        r'#\s*EVOLVE-BLOCK-START(.*?)#\s*EVOLVE-BLOCK-END',    # Python
    ]

    for pattern in patterns:
        match = re.search(pattern, code, re.DOTALL)
        if match:
            return match.group(1).strip()

    return None


def print_diff(
    initial_code: str,
    evolved_code: str,
    max_lines: int = 50,
    show_full: bool = False
) -> bool:
    """
    Print colored diff between initial and evolved code.

    Args:
        initial_code: Initial program code
        evolved_code: Evolved program code
        max_lines: Maximum lines to show (0 = unlimited)
        show_full: Show full code diff, not just EVOLVE-BLOCK

    Returns:
        True if differences found, False if identical
    """
    # Extract EVOLVE-BLOCK if not showing full diff
    if not show_full:
        initial_block = extract_evolve_block(initial_code)
        evolved_block = extract_evolve_block(evolved_code)

        if not initial_block or not evolved_block:
            # Fall back to full diff if blocks not found
            initial_compare = initial_code
            evolved_compare = evolved_code
        else:
            initial_compare = initial_block
            evolved_compare = evolved_block
    else:
        initial_compare = initial_code
        evolved_compare = evolved_code

    # Generate diff
    initial_lines = initial_compare.splitlines(keepends=True)
    evolved_lines = evolved_compare.splitlines(keepends=True)

    diff = list(unified_diff(
        initial_lines,
        evolved_lines,
        fromfile='Initial',
        tofile='Evolved',
        lineterm=''
    ))

    if not diff:
        return False

    # Print diff with colors
    print("\n" + "─" * 70)
    print("📝 MUTATION DIFF")
    print("─" * 70)

    lines_shown = 0
    for line in diff:
        if max_lines > 0 and lines_shown >= max_lines:
            remaining = len(diff) - lines_shown
            print(f"... ({remaining} more lines, use --show-full-diff to see all)")
            break

        line = line.rstrip()

        if line.startswith('---') or line.startswith('+++'):
            print(f"\033[1m{line}\033[0m")  # Bold
        elif line.startswith('-'):
            print(f"\033[91m{line}\033[0m")  # Red
        elif line.startswith('+'):
            print(f"\033[92m{line}\033[0m")  # Green
        elif line.startswith('@@'):
            print(f"\033[94m{line}\033[0m")  # Blue
        else:
            print(line)

        lines_shown += 1

    # Summary
    removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
    added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))

    print("─" * 70)
    print(f"📊 {removed} lines removed, {added} lines added")
    print("─" * 70 + "\n")

    return True


def print_compact_diff(initial_code: str, evolved_code: str) -> bool:
    """
    Print a very compact diff summary (single line).

    Args:
        initial_code: Initial program code
        evolved_code: Evolved program code

    Returns:
        True if differences found, False if identical
    """
    initial_block = extract_evolve_block(initial_code)
    evolved_block = extract_evolve_block(evolved_code)

    if not initial_block or not evolved_block:
        return False

    initial_lines = initial_block.splitlines()
    evolved_lines = evolved_block.splitlines()

    diff = list(unified_diff(initial_lines, evolved_lines, lineterm=''))

    if not diff:
        return False

    removed = sum(1 for line in diff if line.startswith('-') and not line.startswith('---'))
    added = sum(1 for line in diff if line.startswith('+') and not line.startswith('+++'))

    print(f"   📝 Mutation: \033[91m-{removed}\033[0m / \033[92m+{added}\033[0m lines")

    return True
