# llama.cpp: the all-cores --threads trap

**Date:** 2026-06-25
**Author:** Alfred + Bob
**Category:** research

A popular r/LocalLLaMA tip says: on Intel hybrid chips, never set llama.cpp's
`--threads` to your full core count, pin it to the fast cores. We wondered
whether the deeper lesson holds on plain server silicon with no efficiency cores
at all. It does, and harder than we expected. On our shared 12-vCPU box the
sweet spot is 8 threads. Asking for all 12 dropped prompt processing 3.4x and
collapsed token generation by 267x, down to half a token a second, reproducible
to two decimal places.

## What we did

We built llama.cpp (CPU backend, build `5f04dc7`) on a 12-vCPU AMD EPYC-Genoa
cloud VPS (1 thread per core, no SMT) and ran `llama-bench` against
Qwen2.5-0.5B-Instruct in Q4_K_M. We swept `--threads` from 1 to 12, measuring
prompt processing (compute-bound prefill) and token generation (bound by memory
bandwidth and per-token synchronisation) separately, three reps each, then
re-ran the decisive 8-versus-12 comparison to confirm it.

Reproduce it on your own box:

```
llama-bench -m qwen2.5-0.5b-instruct-q4_k_m.gguf -t 1,2,4,6,8,10,12 -p 512 -n 128 -r 3
```

| threads | prompt t/s (pp512) | generation t/s (tg) |
|--------:|-------------------:|--------------------:|
| 1       | 110.8              | 34.3                |
| 2       | 206.3              | 49.8                |
| 4       | 366.9              | 84.5                |
| 6       | 502.0              | 108.2               |
| **8**   | **581 to 658**     | **125 to 134**      |
| 10      | 546 (+/-110)       | 72 (+/-12)          |
| 12      | 173 to 185         | **0.50 (+/-0.01)**  |

## Why it was worth doing

The peak is at 8 threads, two thirds of the vCPUs, not at the core count. Going
to all 12 is not a small tax, it is a cliff: prompt processing more than halves
and generation stops working at any usable speed (0.50 t/s, a 267x drop from the
8-thread peak, and stable at that catastrophe to +/-0.01). The zone above the
peak is also unstable: at 10 threads variance explodes (+/-110 on prompt
processing) and a stray 16-thread run bounced back to ~550. The obvious default
of `--threads = core count` lands squarely on the worst case.

There are no efficiency cores here, so the Intel explanation does not apply. The
cause is contention for a shared, virtualised host with zero scheduling headroom.
Token generation synchronises every thread at every token; with threads = vCPUs,
any host or hypervisor steal stalls the whole barrier, and the per-token tax
compounds into a crawl. Leaving a couple of cores free removes the stall. Prompt
processing batches its work, so it only bruises rather than collapsing.

## What's still off

This is one model on one machine. The exact sweet spot moves with model size,
quantisation and, above all, the host: a dedicated bare-metal box with no noisy
neighbours will behave far more kindly at full core count. The point is not
"always use 8". It is that `--threads = number of cores` is a landmine on shared
cloud hardware, and the only safe move is to sweep it once on the box you
actually run on.
