# The agent passed along five papers it never opened.

**Date:** 2026-06-26
**Author:** Alfred + Bob
**Category:** tooling

This morning the agent handed over five research papers worth a look, then added
a line to its own message: it had not actually checked the IDs were real. Honest,
and exactly the wrong place to be. A draft should not reach a human carrying
citations nobody has opened. We had a rule against it. We did not have a guard.
So we built the guard.

## The slip

A research feed surfaced five arXiv papers, each tagged with an identifier like
2606.21959. An arXiv ID is the catalogue number for a paper; it either points at
a real paper or it does not. Language models are good at producing ones that look
right and point at nothing. The agent relayed all five, and to its credit flagged
that it had not resolved them. But "I have not checked" is not a state you ship
from. It is a to-do you handed to the reader.

We already had rules for this: verify every URL, never invent an identifier. The
trouble with a rule is that it lives in a prompt and leans on the agent to
remember it under load. A rule a human, or an agent, has to remember is not a
control. It is a wish. The fix is to make the check something the copy cannot get
past, not something anyone has to recall.

## What we built

cite-check reads a draft, pulls out every link and every arXiv ID, and fetches
each one to confirm it is real. Links get a lightweight request, falling back to a
fuller fetch when a server refuses the quick one, which plenty do. A status under
400 passes; a dead page fails. arXiv IDs are a special case: the page for a
made-up ID can still return a normal "all fine" response, so checking the page is
not enough. cite-check asks the arXiv catalogue directly instead, and a fabricated
ID comes back with no matching entry. That fails.

The whole thing is a small command line tool with one job and a clear verdict. It
exits clean when every citation resolves and errors when any do not, so it drops
straight into a publish step as a gate: if a citation is not real, the publish
stops. No model call, no judgement, no latency to speak of. Either the source
exists or it does not.

```
cite-check draft.md            # check a file
cat draft.md | cite-check       # check stdin
cite-check draft.md || exit 1   # gate a publish step
```

## What it found

We pointed it at the exact five IDs from the morning. All five resolved. Real
papers, every one. Which is the point, not against it: the agent had no way to
know that when it relayed them, and neither did we. The guard turned "I have not
checked" into a definite yes in about two seconds. Then we fed it a control, an ID
we made up, and it failed it cleanly: no such paper. Real links pass, dead links
fail, invented papers fail. That is the whole contract, and it holds.

## The hard half, shipped the same day

Resolving a citation is the easy half. The harder half is misattribution: a real
paper cited for something it never says. That sails past a resolve check because
the link is fine. So we built the second half too (`cite-check-claims`): decompose
a draft into atomic claims, fetch the actual source text, and check whether the
source backs the claim. Four-shade verdict (supported / partly / unsupported /
unverifiable); only "supported" auto-passes.

We proved it on one real paper cited two ways: the accurate claim passed, and "the
same paper shows this is a text-to-image model" was flagged unsupported (entailment
0.00) on a source that resolves perfectly. The resolve check waved both through;
the support check caught the lie.

Engine note: the 7B fact-checker the research pointed at was accurate but took
~200s per call on our CPU-only box. Unusable. We swapped in an NLI cross-encoder
that does the same job in ~150ms, a thousandfold faster, same verdicts on our
tests. The right tool is the one your hardware can run on the publish path.

## What it still does not do

NLI is chunk-local, so a claim that only holds across two distant parts of a source
lands in "partly" for a human, rather than passing. A fully paywalled source comes
back "unverifiable", not a pass. Both deliberate: when unsure, it asks a person.

## The lesson worth keeping

If your agent writes anything outward facing, it will eventually cite something
that is not there. The defence is not a smarter model or a sterner prompt. It is a
dumb, certain check that the copy cannot route around, sitting on the publish
path, failing the send when a source does not resolve. Move the discipline out of
the agent's memory and into the plumbing. A rule you have to remember is one you
will eventually forget at the worst moment. A gate does not forget.

Code: `code/080-cite-check/`
