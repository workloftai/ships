# self-tamper-guard

A Claude Code hook that stops an agent disabling its own guardrails.

CVE-2026-82533, in an AI coding tool called DeepSeek Harness, let the agent
switch off its own sandbox. That is the whole category of bug this guards
against: if a control lives somewhere the agent can write to, it is not a
control. An agent with a shell and a file editor can delete a hook, rewrite a
settings file, or flush a firewall, because those are just files and commands.

So this sits at the tool boundary and refuses the calls that would tamper with
the controls themselves.

This is one stdlib-only Python file. It reads a tool-call event and exits 0 to
allow or 2 to block, the standard Claude Code PreToolUse contract.

## What it blocks

- **Edit / Write / NotebookEdit** whose target is `settings.json`,
  `settings.local.json`, anything under `.claude/hooks/`, or this guard's own
  directory. Reading those files is fine, rewriting them is not.
- **Bash** that deletes, moves, chmods, truncates or redirects into any of those
  protected paths. Because the guard lives in the hooks directory it protects, a
  command to delete it is one the guard sees first and refuses.
- **Bash egress** to a host not on the allowlist, but only in enforce mode
  (`SELF_TAMPER_EGRESS=enforce`), which is off by default.

## The one design decision that matters

There is **no in-band override**. A magic comment the agent can append would let
the agent wave the guard away, which is the exact failure the CVE demonstrates.
The only way past is out of band, where the agent has no handle:

```bash
SELF_TAMPER_UNLOCK=1 claude   # human sets this in the parent shell, on purpose
```

The off switch has to live where the agent cannot reach it.

## Run it

```bash
bash demo.sh                      # fire a row of tool calls at it, see each verdict
python3 test_self_tamper_guard.py # 15 cases, all pass
```

## Wire it in

Add it to `~/.claude/settings.json` as a PreToolUse hook:

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Edit|Write|NotebookEdit|Bash",
        "hooks": [ { "type": "command",
          "command": "python3 /absolute/path/to/self_tamper_guard.py" } ] }
    ]
  }
}
```

Edit `protected.txt` to add your own protected paths, and `allowlist.txt` for
egress mode.

## Honest limits

It runs in the same process tree as the agent, so a determined agent could in
principle set the unlock variable itself. The genuinely robust version enforces
this one level down, in the harness or the OS, in a trust domain the agent has
no handle on. This is the pragmatic ninety percent: it stops the accidental, the
prompt-injected and the over-eager, which is most of how this actually goes
wrong, in one file you can read in a sitting. A guard is a floor, not a ceiling.

Part of the [Workloft Ships](https://workloft.ai/ships) log. Steal what you want.
