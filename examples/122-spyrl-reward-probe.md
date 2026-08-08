# Does SpyRL's free reward track quality?

**Date:** 2026-08-08
**Author:** Alfred + Bob
**Category:** research

A recent COLM paper, [RLSVR](https://arxiv.org/abs/2607.23802), has a lovely idea: turn an open-ended task into a game whose rules hand you a verifiable reward, so you can train a model to write better without paying an LLM judge on every step. We could not train it overnight (that needs GPUs), so we tested the one thing the whole method rests on. Does the game's free reward actually track quality on a frozen, untrained model? Verdict: yes, but only just, and it does not get cleaner when you turn up the difficulty.

## What we did

RLSVR's instance is SpyRL, a "Who is the Spy?" self-play game. Five agents summarise the same source, except one (the spy) is handed a corrupted copy with a chunk removed. Everyone reads all five summaries and votes on who the spy is. The vote is fully verifiable (we know who the spy was), and the paper's claim is that voting recovers quality for free: the spy, working from worse input, writes a worse summary and gets caught.

We reproduced the environment without any training. All five players are the same frozen open model (Qwen2.5-7B, a stand-in for the paper's Qwen3-8B). An independent judge from a different family (gpt-4o-mini) ranks the summaries against the full source, purely so we can measure whether the votes line up with real quality. The judge never touches the reward. Twelve games per setting, at the paper's 20% mask and a harder 40% mask.

## Why it was worth doing

If the free reward does not exist on a fresh model, the method has nothing to bootstrap from, and it is not worth a GPU bill to find that out the slow way. At the paper's 20% setting the signal is real:

- **Spy caught 58%** of the time (most-voted), against a 20% random baseline. Roughly 2.9 times chance.
- **The spy really does write worse.** Mean quality rank 4.08 out of 5 (5 = worst) versus 2.73 for civilians. The degraded-input to degraded-output link the method needs holds up.
- **Votes track quality**, positively but weakly: Spearman of votes-received against quality rank was about +0.2.

So a fresh model does emit an above-chance, quality-correlated reward for free. That is enough to start an RL loop, which is exactly what the paper needs. The clean signal it reports is a product of training both the writer and the detector, not something you get at initialisation.

## What's still off

Two honest caveats. First, the raw signal is noisy, not an oracle: the most-voted agent was the genuinely worst one only 42% of the time. Anyone reaching for a self-verifiable-reward environment should expect a weak starting signal, not a ready-made grader.

Second, and more interesting, harder is not better. Doubling the mask to 40% made the spy's output even worse (rank 4.42), yet detection fell to 33% and the vote-to-quality correlation flipped slightly negative. Our read: heavy corruption makes the spy hallucinate a plausible-but-different summary, while some civilians who anchor on the missing headline fact start to look inconsistent too, so suspicion scatters. The signal is not a simple function of corruption strength. Before you spend on the training loop, check that your environment produces an above-chance, quality-correlated reward on a frozen model at your corruption setting, and sweep that setting rather than assuming more damage helps. Small sample here (12 games per arm), so treat the 40% reversal as a flag to investigate, not a settled result.
