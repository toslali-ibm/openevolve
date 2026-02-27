#!/usr/bin/env python3
"""
Replay a stored OpenEvolve prompt against LiteLLM/Gemini to prove
that the LLM DOES produce hypothesis comments.

Usage:
    python scripts/replay_prompt.py <program_json> [--model MODEL] [--api-base URL]

Example:
    python scripts/replay_prompt.py \
      experiments/hypothesis_ab_funcmin/treatment_run_100/checkpoints/checkpoint_10/programs/a4cf3b84-b4fb-4800-aaba-56b989ef23f9.json

The script:
  1. Loads system + user prompts from the stored program JSON
  2. Sends them to LiteLLM (or any OpenAI-compatible API) via the openai SDK
  3. Prints the full LLM response
  4. Checks whether HYPOTHESIS-N / MECHANISM-N / EXPECT-N comments appear
  5. Shows what apply_diff would keep vs discard
"""

import argparse
import json
import os
import re
import sys
import textwrap


def load_prompt_from_json(path: str) -> dict:
    """Load system/user/response from a stored program JSON."""
    with open(path) as f:
        data = json.load(f)

    prompts = data.get("prompts", {})
    if not prompts:
        sys.exit(f"ERROR: No 'prompts' field in {path}")

    # Find the first prompt key (diff_user or full_rewrite_user)
    key = next(iter(prompts))
    entry = prompts[key]
    return {
        "system": entry.get("system", ""),
        "user": entry.get("user", ""),
        "stored_responses": entry.get("responses", []),
        "stored_code": data.get("code", ""),
        "program_id": data.get("id", "unknown"),
    }


def extract_hypothesis_lines(text: str) -> list[str]:
    """Pull out all HYPOTHESIS-N, MECHANISM-N, EXPECT-N lines."""
    pattern = re.compile(
        r"^(?://|#|--)\s*(HYPOTHESIS-\d+|MECHANISM-\d+|EXPECT-\d+):\s*(.+)$",
        re.MULTILINE,
    )
    return [m.group(0) for m in pattern.finditer(text)]


def extract_diffs(text: str) -> list[tuple[str, str]]:
    """Extract SEARCH/REPLACE diff blocks."""
    pattern = r"<<<<<<< SEARCH\n(.*?)=======\n(.*?)>>>>>>> REPLACE"
    blocks = re.findall(pattern, text, re.DOTALL)
    return [(s.rstrip(), r.rstrip()) for s, r in blocks]


def main():
    parser = argparse.ArgumentParser(description="Replay an OpenEvolve prompt against LiteLLM")
    parser.add_argument("program_json", help="Path to stored program .json file")
    parser.add_argument(
        "--model",
        default="GCP/gemini-2.5-flash",
        help="Model name to use (default: GCP/gemini-2.5-flash)",
    )
    parser.add_argument(
        "--api-base",
        default=os.environ.get(
            "LITELLM_API_BASE", "https://ete-litellm.ai-models.vpc-int.res.ibm.com"
        ),
        help="LiteLLM API base URL",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("OPENAI_API_KEY", os.environ.get("LITELLM_API_KEY", "dummy")),
        help="API key",
    )
    parser.add_argument(
        "--skip-call",
        action="store_true",
        help="Don't make the API call; just analyze the stored response",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature (default: 0.7)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=16000,
        help="Max tokens (default: 16000)",
    )
    args = parser.parse_args()

    # Load stored prompt
    data = load_prompt_from_json(args.program_json)
    print("=" * 80)
    print(f"PROGRAM ID: {data['program_id']}")
    print("=" * 80)

    # --- Analyze stored response first ---
    if data["stored_responses"]:
        stored = data["stored_responses"][0]
        print("\n### STORED LLM RESPONSE (from the experiment run) ###")
        print("-" * 60)

        hyp_lines = extract_hypothesis_lines(stored)
        if hyp_lines:
            print(f"\n  HYPOTHESES FOUND IN LLM RESPONSE: {len(hyp_lines)}")
            for line in hyp_lines:
                print(f"    {line}")
        else:
            print("\n  NO HYPOTHESES FOUND IN LLM RESPONSE")

        diffs = extract_diffs(stored)
        print(f"\n  DIFF BLOCKS FOUND: {len(diffs)}")
        for i, (search, replace) in enumerate(diffs):
            hyp_in_replace = extract_hypothesis_lines(replace)
            print(f"    Block {i+1}: SEARCH={len(search.splitlines())} lines, "
                  f"REPLACE={len(replace.splitlines())} lines")
            if hyp_in_replace:
                print(f"      -> Hypotheses IN the REPLACE block: YES ({len(hyp_in_replace)})")
            else:
                print(f"      -> Hypotheses IN the REPLACE block: NO  <-- THIS IS THE BUG")

        # Check stored code
        hyp_in_code = extract_hypothesis_lines(data["stored_code"])
        print(f"\n  HYPOTHESES IN FINAL STORED CODE: {len(hyp_in_code)}")
        if not hyp_in_code:
            print("    -> apply_diff() only keeps SEARCH/REPLACE content.")
            print("    -> Hypotheses in the preamble are DISCARDED.")
            print("    -> parse_hypotheses() finds nothing -> ledger stays empty.")

        print("-" * 60)

    # --- Show prompt structure ---
    print("\n### PROMPT STRUCTURE ###")
    sys_msg = data["system"]
    usr_msg = data["user"]
    print(f"  System message length: {len(sys_msg)} chars")
    print(f"  User message length:   {len(usr_msg)} chars")
    has_hyp_instructions = "HYPOTHESIS" in sys_msg.upper()
    print(f"  System msg contains HYPOTHESIS instructions: {has_hyp_instructions}")

    # Show relevant excerpt from system message
    for keyword in ["HYPOTHESIS REQUIREMENTS", "HYPOTHESIS_INSTRUCTIONS"]:
        idx = sys_msg.find(keyword)
        if idx >= 0:
            snippet = sys_msg[max(0, idx - 20) : idx + 200]
            print(f"\n  System message excerpt (near '{keyword}'):")
            for line in snippet.splitlines()[:8]:
                print(f"    | {line}")
            print("    | ...")
            break

    if args.skip_call:
        print("\n(--skip-call: skipping API call)")
        return

    # --- Make the actual API call ---
    print("\n### CALLING LiteLLM API ###")
    print(f"  Model:    {args.model}")
    print(f"  API Base: {args.api_base}")
    print(f"  Temp:     {args.temperature}")

    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("ERROR: 'openai' package not installed. Run: pip install openai")

    client = OpenAI(
        api_key=args.api_key,
        base_url=f"{args.api_base.rstrip('/')}/v1",
    )

    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": usr_msg},
    ]

    print("  Sending request...")
    response = client.chat.completions.create(
        model=args.model,
        messages=messages,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    llm_text = response.choices[0].message.content
    print(f"\n### FRESH LLM RESPONSE ({len(llm_text)} chars) ###")
    print("-" * 60)
    # Print first 3000 chars
    print(llm_text[:3000])
    if len(llm_text) > 3000:
        print(f"\n... ({len(llm_text) - 3000} more chars)")
    print("-" * 60)

    # Analyze
    hyp_lines = extract_hypothesis_lines(llm_text)
    if hyp_lines:
        print(f"\n  HYPOTHESES IN FRESH RESPONSE: {len(hyp_lines)}")
        for line in hyp_lines:
            print(f"    {line}")
    else:
        print("\n  NO HYPOTHESES IN FRESH RESPONSE")

    diffs = extract_diffs(llm_text)
    print(f"  DIFF BLOCKS: {len(diffs)}")
    for i, (search, replace) in enumerate(diffs):
        hyp_in_replace = extract_hypothesis_lines(replace)
        print(f"    Block {i+1}: hypotheses in REPLACE: {'YES' if hyp_in_replace else 'NO'}")

    # Verdict
    print("\n" + "=" * 80)
    if hyp_lines:
        print("VERDICT: Gemini DOES generate hypotheses when instructed.")
        if diffs and not any(extract_hypothesis_lines(r) for _, r in diffs):
            print("BUT: Hypotheses are placed OUTSIDE the SEARCH/REPLACE blocks.")
            print("     apply_diff() only keeps REPLACE content -> hypotheses lost.")
            print("     FIX: Extract hypotheses from LLM response before diff application")
            print("          and inject them into the evolved code.")
    else:
        print("VERDICT: Gemini did NOT generate hypotheses in this response.")
        print("         Check the system message and prompt format.")
    print("=" * 80)


if __name__ == "__main__":
    main()
