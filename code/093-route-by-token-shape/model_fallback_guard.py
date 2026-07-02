#!/usr/bin/env python3
"""UserPromptSubmit hook: catch Fable 5's sticky silent fallback to Opus.

Fable's safety classifiers can reroute a request to Opus 4.8 and the session
then STAYS on Opus until manually switched back. This hook compares the model
that actually produced the last assistant turn (from the transcript) with the
model configured in settings.json, and warns in-context on mismatch.
Silent + fail-open by design: any error exits 0 with no output.
"""
import json
import sys

SETTINGS = "/home/workloft/.claude/settings.json"


def last_used_model(transcript_path):
    used = None
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") == "assistant":
                    m = (entry.get("message") or {}).get("model")
                    if m:
                        used = m
    except OSError:
        return None
    return used


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    transcript = payload.get("transcript_path")
    if not transcript:
        return 0
    try:
        expected = json.load(open(SETTINGS)).get("model", "")
    except Exception:
        return 0
    used = last_used_model(transcript)
    if not used or not expected:
        return 0
    # exact-id vs versioned-id tolerant: expected "claude-fable-5" should
    # match used "claude-fable-5" or "claude-fable-5-20260609"
    if not used.startswith(expected):
        print(f"<system-reminder>MODEL FALLBACK DETECTED: settings expect "
              f"'{expected}' but the last assistant turn was served by "
              f"'{used}'. This is likely Fable's sticky safety fallback to "
              f"Opus. Tell Alfred, and note that the session will stay on "
              f"'{used}' until restarted or switched.</system-reminder>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
