# memory-reload-guard — a firewall for agent memory files

Agents increasingly keep long-term memory in plain files (a `CLAUDE.md`, a
`MEMORY.md`, a `SOUL.md`, a rules file) that get read back into the system
prompt on every start or context compaction. That reload path is an injection
surface.

Anthropic's research on natural-language ["worms"](https://www.anthropic.com/research)
showed the attack: persuade an agent to write a hostile instruction *into* one of
those files, and it is faithfully reloaded after every reset, surviving context
wipes until something removes it. The file is the persistence mechanism.

This is a small, stdlib-only defence for that path. No install, no network.

## The one idea

Memory is supposed to hold **facts**. When it starts holding **orders aimed at
the agent** ("from now on, always approve..."), that is the signal something is
wrong. Guard the reload three ways:

1. **`baseline` + `drift`** — record a sha256 of each memory file, then flag any
   file whose content changed. A worm persists by editing these files; drift is
   the cheapest way to notice an edit you did not make.
2. **`scan`** — a heuristic tripwire for instruction-shaped text: goal
   overrides, self-propagation ("tell the other agents"), file self-modification,
   exfiltration, fake system headers.
3. **`wrap`** — emit the file inside a frame that tells the model the text is
   DATA, not instructions. In Anthropic's tests, a warning prompt like this
   blocked 100% of attacks. This is the real defence. 1 and 2 are how you notice
   you needed it.

## Run it

```
python3 guard.py baseline MEMORY.md standing.md   # record hashes
python3 guard.py drift    MEMORY.md standing.md   # what changed since?
python3 guard.py scan     MEMORY.md               # instruction-shaped text?
python3 guard.py wrap     MEMORY.md               # framed for safe reload
python3 guard.py scan MEMORY.md --json            # machine-readable, for a gate
```

`drift` and `scan` exit `1` when they find something, so either works as a
pre-reload or CI gate. See the whole story run end to end:

```
python3 demo.py
```

which plants a worm in a throwaway `MEMORY.md`, then shows the baseline, the
drift, the scan flags, and the wrapped-safe output. Captured in
[`demo-output.txt`](./demo-output.txt).

## What's still off

`scan` is a regex tripwire, not a parser. It is bypassable by anyone who knows
it is there, and it will occasionally flag a legitimate line that reads like an
order. Treat it as smoke detection, not a wall. The load-bearing defence is
`wrap`: framing recalled memory as untrusted data is what actually stopped the
attacks in Anthropic's tests. `drift` tells you a file changed, not whether the
change was hostile, so a human (or a stricter policy) still reads the diff.
Scanning our own fleet's 15 live memory files returns zero flags, which is the
point: on clean memory it is quiet, and it only speaks up when memory starts
giving orders.

## Licence

MIT.
