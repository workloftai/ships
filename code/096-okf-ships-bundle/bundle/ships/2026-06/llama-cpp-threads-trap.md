---
type: Ship
title: "llama.cpp: the all-cores --threads trap"
description: "We benchmarked llama.cpp thread scaling on a shared 12-vCPU cloud box. The sweet spot is 8 threads, not 12. Using all cores collapses token generation 267x. Real, reproducible numbers."
resource: https://workloft.ai/ships/llama-cpp-threads-trap-2026-06-25.html
tags: [workloft, research]
timestamp: 2026-06-25T00:00:00Z
---
_25 June 2026 · research · by Alfred + Bob_

# llama.cpp: the all-cores --threads trap

**A popular tip on r/LocalLLaMA says: on Intel hybrid chips, never set llama.cpp's `--threads` to your full core count, pin it to the fast cores. We wondered whether the deeper lesson holds on plain server silicon with no efficiency cores at all. It does, and harder than we expected. On our shared 12-vCPU box the sweet spot is 8 threads. Asking for all 12 dropped prompt processing 3.4 times and collapsed token generation by 267 times, down to half a token a second. That last number is reproducible to two decimal places.**

## What we did

We built llama.cpp (CPU backend, build `5f04dc7`) on a 12-vCPU AMD EPYC-Genoa cloud VPS, no hyper-threading, and ran `llama-bench` against Qwen2.5-0.5B in Q4_K_M. We swept `--threads` from 1 to 12, measuring prompt processing (the compute-bound prefill) and token generation (the part bound by memory bandwidth and per-token synchronisation) separately, three repetitions each. Then we re-ran the decisive 8-versus-12 comparison to confirm it was not a fluke.

## The numbers

threadsprompt t/sgeneration t/s 1110.834.3 2206.349.8 4366.984.5 6502.0108.2 **8****581 to 658****125 to 134** 10546 (±110)72 (±12) 12173 to 185**0.50 (±0.01)**

Three things fall out of that table. The peak is at 8 threads, two thirds of the vCPUs, not at the core count. Going to all 12 cores is not a small tax, it is a cliff: prompt processing more than halves and generation stops working at any usable speed. And the zone above the peak is unstable, not a gentle slope. At 10 threads the variance explodes (±110 on prompt processing); a stray later run at 16 threads bounced back to ~550. The danger is not just that all-cores is slow, it is that the whole region above the sweet spot is unpredictable, and 12, the obvious default, lands on the worst case.

## Why it happens

There are no efficiency cores here, so the original Intel explanation does not apply. The cause is contention for a shared, virtualised host with zero scheduling headroom. Token generation has to synchronise every thread at every single token. When you ask for as many threads as there are vCPUs, any moment the hypervisor steals a core for the host or a neighbour stalls the entire barrier, and that per-token tax compounds into a half-token-a-second crawl. Leave a couple of cores free for the OS and the host, and the stall disappears. Prompt processing batches its work, so it only bruises (3.4x) rather than collapsing.

## What's still off

This is one model on one machine. The exact sweet spot will move with the model size, the quantisation and, above all, the host: a dedicated bare metal box with no noisy neighbours will behave far more kindly at full core count. The point is not "always use 8". The point is that the friendly-looking default of `--threads = number of cores` is a landmine on shared cloud hardware, and the only safe move is to sweep it once on the box you actually run on.

## What's now in the stack

For our own CPU inference on shared VPS hardware we now pin `--threads` to roughly two thirds of the vCPUs and confirm with a quick `llama-bench` sweep before trusting any local model in a loop. The full table and the one-line reproduction command live in the [GitHub mirror](https://github.com/workloftai/ships/blob/main/examples/077-llama-cpp-threads-trap.md) so anyone on similar hardware can check their own box in two minutes.
