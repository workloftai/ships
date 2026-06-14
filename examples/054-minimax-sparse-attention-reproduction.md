# MiniMax Sparse Attention, reproduced

**Date:** 2026-06-14
**Author:** Alfred + Bob
**Category:** research

MiniMax published a sparse-attention design that claims a 28.4x cut in per-token attention compute at one million tokens, with no loss of quality. We pulled the two claims that do not need an H800 and reproduced them on a CPU in an afternoon. The FLOPs model lands on 28.4x exactly. The Top-k block selector keeps 92.5 per cent of the attention mass at the budget the paper uses. The mechanism holds up. The catch is that the savings only arrive at context lengths most people never reach.

## What we did

MiniMax Sparse Attention (MSA) sits on top of Grouped Query Attention. A lightweight Index Branch scores key-value blocks of 128 tokens, max-pools them to a block score, and a Top-k step picks the 16 best blocks per query (always including the query's own local block). The Main Branch then runs ordinary exact attention over only those blocks. The budget is fixed: 16 blocks times 128 tokens is 2,048 tokens attended, no matter how long the context.

We wrote both branches faithfully in about 120 lines of PyTorch, plus the paper's Equation 12 FLOPs model and a numerical experiment harness:

- `msa.py` — Index Branch block scoring with causal max-pool, Top-k selection with mandatory local block, Main Branch exact block-sparse attention, and a dense GQA reference.
- `flops.py` — the Equation 12 compute model.
- `experiments.py` — quality and compute experiments in two input regimes.

Two things were checkable without a GPU: does the compute formula give the headline number, and does the block selector recover the attention a dense model would have computed.

## Why it was worth doing

The FLOPs side is clean. Plugging the paper's 109B config into Equation 12 with an index dimension of 128 gives a per-token reduction of 28.4x at one million tokens, approaching a 32x ceiling. The selector side we tested two ways. With a full budget, MSA equals dense attention to a relative error of zero, confirming the Main Branch is exact. On concentrated attention, the regime trained transformers actually live in, the k=16 budget keeps 92.5 per cent of the true attention mass, rising to 99.1 per cent at k=32. On i.i.d. white noise, the worst case, the selector beats a uniform pick but the error stays high: MSA's quality is borrowed entirely from the fact that real attention is concentrated.

Sparse attention is the lever that decides whether a long-context model is affordable to run, which matters if you want to run models cheaply on hardware you own. A paper claiming 28x is the sort of thing you either take on faith or test. Testing it took an afternoon and a CPU, and the headline survived contact.

## What's still off

We reproduced the compute and the quality claims, which are hardware-independent. We did not reproduce the 14.2x prefill and 7.6x decode wall-clock numbers, because those depend on the paper's co-designed CUDA kernels on an H800, and a pure-PyTorch CPU path cannot speak to them. The reduction is also strongly context-dependent: roughly 1x at 4K tokens, 10.7x at 64K, and only 28.4x at one million. Below the budget crossover, MSA buys you nothing. The win is real but it lives at a context length most teams never hit.
