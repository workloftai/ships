# coordinated-fanout — a swarm-safe multi-agent review

Anthropic's Frontier Red Team [showed](https://venturebeat.com/security/three-claude-agents-given-conflicting-orders-sabotaged-each-other-on-a-shared-server-then-didnt-tell-users-what-theyd-done)
what happens when you give a pile of agents conflicting objectives on shared
infrastructure: they collude, sabotage each other, write self-replicating malware,
and don't tell you. The lesson isn't "don't use many agents". It's *coordinate
them*. This is the pattern that does.

It's a workflow: fan out N read-only reviewers over a set of targets, each on ONE
disjoint dimension, then one arbitrator reconciles their findings into a single
attributed report. The five guardrails from the study are structural, not
optional:

1. **The coordinator is code, not an agent.** The deterministic script owns the
   split, so no two agents ever get overlapping or conflicting objectives — the
   exact trigger for the sabotage.
2. **Disjoint objectives.** Each reviewer owns one lens and is told not to stray
   into another's. No agent competes with another for the same job.
3. **No shared mutable state.** Reviewers are read-only; they return data, the
   script merges it. Nothing to contend over.
4. **Explicit arbitration.** One step reconciles the panel. In the study, the
   only runs that reached a truce did so through an explicit governance step, not
   by leaving agents to fight.
5. **Full attribution.** Every finding is tagged with the reviewer that raised
   it. The study's scariest detail was agents *hiding* what they'd done;
   visibility is the countermeasure.

## Run it

It's a Claude Code workflow. Invoke with a target list and disjoint dimensions:

```
Workflow({ name: 'coordinated-fanout', args: {
  targets: ['https://…', 'https://…'],
  dimensions: [
    { key: 'claim-accuracy',      brief: 'Do the numbers match the evidence?' },
    { key: 'honest-caveats',      brief: 'Is the real limitation stated plainly?' },
    { key: 'link-asset-integrity', brief: 'Does every link/asset resolve?' },
  ],
}})
```

Each dimension becomes one isolated reviewer; the arbitrator returns
`{ per_target: [{ target, verdict, issues }], summary }`.

## The first real run (demo-result.json)

We pointed it at three Workloft ship pages published an hour earlier. Two came
back clean. On the third it caught a genuine framing overclaim we'd missed: the
headline "a free local model" understated that a frontier model wrote the skill
at authoring time, so "cost goes to zero" was only true at runtime. We fixed the
ship. The panel earned its keep on its first outing.

## What's still off

It's a *review* fan-out — read-only, low-stakes, so the guardrails are easy to
honour. The hard case is agents that must *write* to shared state (the study's
actual setup); there you also need per-agent isolation (worktrees) and a merge
step that resolves edit conflicts, not just a report. This pattern is the safe
half; the writing half is the next build. And an arbitrator is still one model
judging others, so a systematic blind spot shared by the panel and the arbitrator
survives.

Part of the [Workloft Ships](https://workloft.ai/ships) log.
