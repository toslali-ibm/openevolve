#!/usr/bin/env python3
"""Quick test of Go code extraction"""

import re

# Read initial program
with open('initial_program.py', 'r') as f:
    content = f.read()

print("=" * 60)
print("Testing Go Code Extraction")
print("=" * 60)

# Try extraction
match = re.search(r'GO_ROUTING_CODE\s*=\s*"""(.*?)"""', content, re.DOTALL)
if match:
    go_code = match.group(1).strip()
    lines = go_code.split('\n')
    print(f"✓ Extraction successful!")
    print(f"  Total lines: {len(lines)}")
    print(f"  First line: {lines[0]}")
    print(f"  Last line: {lines[-1]}")
    print(f"  Contains 'EVOLVE-BLOCK': {'EVOLVE-BLOCK' in go_code}")
else:
    print("✗ Extraction failed!")
    print(f"\nContent preview (first 300 chars):")
    print(content[:300])
    print("\n" + "=" * 60)

    # Try finding GO_ROUTING_CODE
    if "GO_ROUTING_CODE" in content:
        idx = content.index("GO_ROUTING_CODE")
        print(f"Found GO_ROUTING_CODE at position {idx}")
        print(f"Context: {content[idx:idx+100]}")
    else:
        print("GO_ROUTING_CODE not found in file!")
