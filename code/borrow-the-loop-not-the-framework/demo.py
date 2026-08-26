"""Reference demo for the self-tuning loop in optimize.py.

The loop itself (optimize.py) is provider-agnostic: it only needs a `chat_fn`
that maps chat messages to text. This file supplies one backed by the OpenAI API
as a reference, then runs the proof: a deliberately bad, chatty system prompt
scores 0 on an exact-match yes/no set, and the loop rewrites it to 100.

Run it:
    pip install openai
    export OPENAI_API_KEY=sk-...
    python3 demo.py

To run it on a local open-weight model instead, point the OpenAI client at any
OpenAI-compatible endpoint (base_url) and swap the model name. Nothing else changes.
The loop does not know or care where the tokens come from.
"""
import os
import sys

from optimize import optimize, exact_match


def make_openai_chat_fn(model: str = "gpt-4o-mini"):
    """Return a chat_fn(messages, max_tokens, temperature) -> str backed by OpenAI."""
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("pip install openai  (or wire optimize() to any other model call)")
    client = OpenAI()  # reads OPENAI_API_KEY; set base_url here for a local endpoint

    def chat_fn(messages, max_tokens, temperature):
        resp = client.chat.completions.create(
            model=model, messages=messages,
            max_tokens=max_tokens, temperature=temperature)
        return resp.choices[0].message.content or ""

    return chat_fn


DEMO_DATASET = [
    {"input": "Is the sky blue on a clear day?", "expected": "yes"},
    {"input": "Can fish breathe on land?", "expected": "no"},
    {"input": "Do humans need water to survive?", "expected": "yes"},
    {"input": "Is the sun a planet?", "expected": "no"},
    {"input": "Is ice colder than boiling water?", "expected": "yes"},
    {"input": "Is two greater than five?", "expected": "no"},
]


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set OPENAI_API_KEY first (or edit make_openai_chat_fn for a local model).")

    # A deliberately bad prompt: it invites a verbose explanation, so a bare
    # exact-match against 'yes'/'no' fails.
    bad_prompt = "You are a helpful assistant. Answer the user's question with a brief explanation."

    print("=== self-tuning loop demo: the idea, without the framework ===")
    print(f"starting prompt: {bad_prompt!r}\n")

    best, score, hist = optimize(
        task_prompt=bad_prompt, dataset=DEMO_DATASET,
        chat_fn=make_openai_chat_fn(), scorer=exact_match,
        max_rounds=3, target=100)

    print("\n--- result ---")
    print("score trajectory: " + " -> ".join(f"{h['score']:.0f}" for h in hist))
    print(f"final best score: {score:.0f}")
    print(f"final prompt    : {best!r}")


if __name__ == "__main__":
    main()
