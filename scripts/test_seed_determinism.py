#!/usr/bin/env python3
"""Test whether LiteLLM seed parameter produces deterministic responses."""

import os
import openai

API_BASE = "https://ete-litellm.ai-models.vpc-int.res.ibm.com"
MODEL = "Azure/gpt-4o" # "aws/claude-opus-4-6"
SEED = 66
TEMPERATURE = 0.7
PROMPT = "Write a single short sentence about a cat."
N_CALLS = 10

client = openai.OpenAI(base_url=API_BASE, api_key=os.environ["OPENAI_API_KEY"])

responses = []
for i in range(N_CALLS):
    # SEED = SEED + 1
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "Reply with exactly one sentence."},
            {"role": "user", "content": PROMPT},
        ],
        temperature=TEMPERATURE,
        seed=SEED,
        max_tokens=50,
    )
    text = resp.choices[0].message.content.strip()
    responses.append(text)
    print(f"  Call {i+1:2d}: {text}")

unique = set(responses)
print(f"\n{'='*60}")
print(f"Model: {MODEL}")
print(f"Seed: {SEED}, Temperature: {TEMPERATURE}")
print(f"Total calls: {N_CALLS}, Unique responses: {len(unique)}")
if len(unique) == 1:
    print("DETERMINISTIC - seed works!")
else:
    print("NON-DETERMINISTIC - seed is ignored by this provider")
