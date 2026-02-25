#!/usr/bin/env python3
"""Summarize what the evolved program optimized compared to the initial program.

Usage:
    python examples/blis_router/scripts/summarize_diff.py <experiment_name>

Example:
    python examples/blis_router/scripts/summarize_diff.py openevolve_output_fixedprompt_llama_opus_20iter

This reads:
    examples/blis_router/initial_program.py
    examples/blis_router/<experiment_name>/best/best_program.py

Creates a unified diff, sends it to LiteLLM (aws/claude-opus-4-6), and prints
a structured summary of what was optimized.

Saves to the experiment directory:
    examples/blis_router/<experiment_name>/best_vs_initial.diff
    examples/blis_router/<experiment_name>/explained.md

Requires:
    OPENAI_API_KEY environment variable set for LiteLLM auth.
"""

import argparse
import difflib
import os
import sys

import openai

BLIS_ROUTER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LITELLM_BASE_URL = "https://ete-litellm.ai-models.vpc-int.res.ibm.com"
MODEL = "aws/claude-opus-4-6"


def create_diff(initial_path, best_path):
    with open(initial_path) as f:
        initial_lines = f.readlines()
    with open(best_path) as f:
        best_lines = f.readlines()

    diff = difflib.unified_diff(
        initial_lines,
        best_lines,
        fromfile="initial_program.py",
        tofile="best_program.py",
    )
    return "".join(diff)


def summarize(diff_text, api_key):
    client = openai.OpenAI(base_url=LITELLM_BASE_URL, api_key=api_key)

    prompt = (
        "Below is a unified diff between an initial LLM inference router program "
        "and the best evolved version produced by an evolutionary optimization system.\n\n"
        "Your output is a Markdown file that will be screenshotted for a presentation. "
        "It must be SHORT, SIMPLE, and VISUALLY CLEAN.\n\n"
        "Rules:\n"
        "- List each change as a numbered item.\n"
        "- For each change: first write ONE short plain-English sentence explaining what changed.\n"
        "- Then immediately below it show a TINY code/pseudocode snippet (2-4 lines max) illustrating the key change. Use a ```python fenced code block.\n"
        "- No long explanations. No paragraphs. No sub-bullets. No 'Why' sections.\n"
        "- Maximum 6-8 changes total. Merge related small changes into one.\n"
        "- Use a single `# Optimizations` heading at the top.\n\n"
        f"```diff\n{diff_text}\n```"
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
        temperature=0,
    )
    return response.choices[0].message.content


def main():
    parser = argparse.ArgumentParser(description="Summarize optimizations in evolved program")
    parser.add_argument("experiment", help="Experiment directory name (e.g. openevolve_output_fixedprompt_llama_opus_20iter)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Error: OPENAI_API_KEY environment variable not set")

    initial_path = os.path.join(BLIS_ROUTER_DIR, "initial_program.py")
    best_path = os.path.join(BLIS_ROUTER_DIR, args.experiment, "best", "best_program.py")

    if not os.path.exists(initial_path):
        sys.exit(f"Error: {initial_path} not found")
    if not os.path.exists(best_path):
        sys.exit(f"Error: {best_path} not found")

    experiment_dir = os.path.join(BLIS_ROUTER_DIR, args.experiment)
    diff_text = create_diff(initial_path, best_path)
    if not diff_text.strip():
        print("No differences found between initial and best program.")
        return

    # Save diff to experiment directory
    diff_path = os.path.join(experiment_dir, "best_vs_initial.diff")
    with open(diff_path, "w") as f:
        f.write(diff_text)
    print(f"Saved diff to {diff_path}")

    print(f"Diff size: {len(diff_text)} chars — sending to {MODEL} for summarization...\n")
    summary = summarize(diff_text, api_key)
    print(summary)

    # Save explanation to experiment directory
    explained_path = os.path.join(experiment_dir, "explained.md")
    with open(explained_path, "w") as f:
        f.write(summary)
    print(f"\nSaved explanation to {explained_path}")


if __name__ == "__main__":
    main()
