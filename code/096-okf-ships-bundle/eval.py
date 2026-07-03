#!/usr/bin/env python3
"""Spot-check: does an agent answer better over the OKF bundle than over
the raw ships directory?

Three questions with known answers, each asked twice via a fresh headless
Claude session: once with cwd = the raw workloft-site/ships directory
(95 .md siblings mixed in with 95 .html pages and assets), once with
cwd = the OKF bundle. The agent is told to answer only from files in the
current directory and to list the files it read. We record the answer,
the files-read count and wall-clock seconds.

n=3 and one run per condition: this is a spot check, not a benchmark.
"""

import json
import subprocess
import time
from pathlib import Path

RAW = "/home/workloft/workloft-site/ships"
BUNDLE = "/home/workloft/okf-ships/bundle"
OUT = Path("/home/workloft/okf-ships/eval-results.json")

QUESTIONS = [
    {
        "q": "According to this knowledge base, what share of Workloft's LLM tokens turned out to be cache reads, and which build measured it?",
        "expect": "96%",
    },
    {
        "q": "What is Murmur, and roughly what does it cost to run per month?",
        "expect": "£1-£2/month hold-to-talk dictation",
    },
    {
        "q": "Which ships in this knowledge base are about the Vera agent, and what does Vera do? List the ship titles you found.",
        "expect": "multiple vera-* ships; Vera = quality judge/scorer",
    },
]

PROMPT = """You are answering from a knowledge base on disk. Use ONLY files under the current working directory. Explore however you like (list files, read files), then answer.

Question: {q}

End your reply with exactly two lines:
FILES_READ: <number of distinct files you read>
ANSWER: <one-sentence answer>"""


def run(cwd: str, q: str) -> dict:
    t0 = time.time()
    r = subprocess.run(
        ["claude", "--print"], input=PROMPT.format(q=q),
        capture_output=True, text=True, timeout=10 * 60, cwd=cwd,
    )
    out = r.stdout.strip()
    files_read = answer = ""
    for line in out.splitlines():
        if line.startswith("FILES_READ:"):
            files_read = line.split(":", 1)[1].strip()
        elif line.startswith("ANSWER:"):
            answer = line.split(":", 1)[1].strip()
    return {"seconds": round(time.time() - t0, 1),
            "files_read": files_read, "answer": answer, "raw_tail": out[-400:]}


def main() -> None:
    results = []
    for i, item in enumerate(QUESTIONS, 1):
        for label, cwd in (("raw", RAW), ("okf", BUNDLE)):
            print(f"[{i}/{len(QUESTIONS)}] {label}: {item['q'][:60]}…", flush=True)
            res = run(cwd, item["q"])
            results.append({"question": item["q"], "expect": item["expect"],
                            "condition": label, **res})
            print(f"    {res['seconds']}s, files_read={res['files_read']}, "
                  f"answer={res['answer'][:100]}", flush=True)
    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
