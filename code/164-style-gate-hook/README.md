# style-gate-hook

A rule you write in a prompt is probabilistic. The model follows it most of the
time and forgets it under load. If a rule is genuinely non-negotiable, put it in
a **hook at the tool boundary**, where enforcement is deterministic and the model
cannot talk its way past it.

This is the hook that made one house-style rule stick after repeated reminders
failed. The concrete rule here is trivial (no em-dashes in anything a human
sees). The pattern is not.

## What happened

A hard style rule was stated in the project instructions, repeated in person
several times, and even had a narrow enforcement gate. It still leaked. Two
reasons, both worth stealing:

1. **The literal character was only half the problem.** Generated HTML and PDF
   copy carried HTML entity forms (the `mdash` named entity, plus its decimal and
   hex numeric character references, all listed in `BANNED` in `style_gate.py`)
   that render as the banned glyph even though the source had no literal
   character. A gate that checks only the literal char passes the write and ships
   the glyph anyway.
2. **The gate only watched file writes.** A lot of copy leaves through the
   chat/reply tool, which the gate never inspected. So a message drafted straight
   to the user sailed through untouched.

The fix broadened one deterministic gate to the actual points of egress: the
reply tool **and** generated copy files, matching both the literal character and
the entity forms. It caught its own author mid-send within minutes.

## The general lesson

- **Reminders are not controls.** "Please always or never X" in a prompt is a
  soft constraint. Under enough context it will be dropped. That is not a model
  failing to try, it is the nature of probabilistic instruction following.
- **Put non-negotiables where they cannot be forgotten:** a hook at the tool
  boundary. Deterministic, unskippable, and it reports the reason back to the
  model so the next attempt is corrected, not retried blind.
- **Enforce at the point of egress, in every form.** Cover every tool that emits
  to a human (reply and chat, not just file writes), and every representation of
  the banned thing (literal glyph and its entity or encoded forms), or it leaks
  through the surface you forgot.
- **Fail open.** A guard that wedges all work when it breaks is worse than the
  bug. Any internal error exits 0.
- **Exempt where the rule does not apply.** Notes that document the rule must be
  free to contain the banned form, or the gate blocks its own documentation.
  (This README hit exactly that: the live gate blocked the first draft for
  quoting the entity strings. The prose above is the fix.)

## Use it

1. Drop `style_gate.py` somewhere executable (`chmod +x`).
2. Register it in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__your__reply|Write|Edit|MultiEdit",
        "hooks": [{ "type": "command", "command": "/abs/path/style_gate.py", "timeout": 5 }]
      }
    ]
  }
}
```

3. Edit `BANNED`, `REPLY_TOOLS`, and `is_copy_file()` for your own rule and stack.

Exit 2 blocks the tool call and shows the model the reason. Exit 0 passes.

MIT, same as the rest of this repo.
