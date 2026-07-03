---
type: Ship
title: "MiniMax Sparse Attention, reproduced"
description: "We reproduced the two core claims of MiniMax Sparse Attention on a CPU. The FLOPs model recovers the paper's 28.4x reduction at 1M context exactly, and our Top-k block selector keeps 92.5% of attention mass at the paper's k=16 budget."
resource: https://workloft.ai/ships/minimax-sparse-attention-reproduction-2026-06-14.html
tags: [workloft, research]
timestamp: 2026-06-14T00:00:00Z
---
_14 June 2026 · research · by Alfred + Bob_

# MiniMax Sparse Attention, reproduced

**MiniMax published a sparse-attention design that claims a 28.4x cut in per-token attention compute at one million tokens, with no loss of quality. We pulled the two claims that do not need an H800 and reproduced them on this CPU box in an afternoon. The FLOPs model lands on 28.4x exactly. The Top-k block selector keeps 92.5 per cent of the attention mass at the budget the paper uses. The mechanism holds up. The catch is that the savings only arrive at context lengths most people never reach.**

## What we did

MiniMax Sparse Attention (MSA) sits on top of Grouped Query Attention. A lightweight Index Branch scores key-value blocks of 128 tokens, max-pools them to a block score, and a Top-k step picks the 16 best blocks per query (always including the query's own local block). The Main Branch then runs ordinary exact attention over only those blocks. Fixed budget: 16 blocks times 128 tokens is 2,048 tokens attended, no matter how long the context.

We wrote both branches faithfully in about 120 lines of PyTorch, plus the paper's Equation 12 FLOPs model and a numerical experiment harness. Two things we could check without a GPU: does the compute formula give the headline number, and does the block selector actually recover the attention a dense model would have computed.

The FLOPs side is clean. Plugging the paper's 109B config into Equation 12, with an index dimension of 128, gives a per-token reduction of 28.4x at one million tokens, approaching a 32x ceiling. The selector side we tested two ways. With a full budget, MSA equals dense attention to a relative error of zero, which confirms the Main Branch is exact. On concentrated attention, the regime trained transformers actually live in, the k=16 budget keeps 92.5 per cent of the true attention mass, rising to 99.1 per cent at k=32.

## Why it was worth doing

Sparse attention is the lever that decides whether a long-context model is affordable to run, which is the whole game if you want to run models cheaply on hardware you own. A paper claiming 28x is the sort of thing you either take on faith or test. Testing it took an afternoon and a CPU, and the headline survived contact. That is worth knowing before you bet a deployment on it.

The honest contrast is the part worth keeping. We also ran it on i.i.d. white noise, the worst case, where no subset of blocks concentrates the mass. There the selector beats a uniform pick but the error stays high. MSA's quality is not free. It is borrowed entirely from the fact that real attention is concentrated. When it is, the selector finds it. When it is not, nothing will.

## What's still off

We reproduced the compute and the quality claims, which are hardware-independent. We did not reproduce the 14.2x prefill and 7.6x decode wall-clock numbers, because those depend on the paper's co-designed CUDA kernels on an H800, and we are honest that a pure-PyTorch CPU path cannot speak to them. The reduction is also strongly context-dependent: it is roughly 1x at 4K tokens, 10.7x at 64K, and only reaches 28.4x at one million. Below the budget crossover, MSA buys you nothing. The win is real but it lives at a context length most teams never hit.

## What's now in the stack

- A runnable MSA reproduction: faithful forward pass, FLOPs analysis, and a two-regime experiment harness, all CPU.
- A reusable pattern for vetting efficiency papers: reproduce the compute model and the mechanism's quality before trusting the wall-clock chart.
- A clearer line for the sovereignty pitch: long-context cost is a solvable engineering problem, and we can show our working.
